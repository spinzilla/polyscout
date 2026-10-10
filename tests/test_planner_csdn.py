import asyncio
import json

import httpx

from polyscout.config import Settings
from polyscout.planner import research
from polyscout.store import EvidenceStore


def test_csdn_query_flows_through_planner_to_adapter(tmp_path):
    settings = Settings(llm_base_url="https://llm.example/v1", llm_api_key="llm-secret",
                        llm_model="mock", search_endpoint="https://search.example/api")

    async def handler(request):
        if request.url.host == "llm.example":
            body = json.loads(request.content)
            prompt_data = json.loads(body["messages"][1]["content"])
            if "round" in prompt_data:
                plan = {"subquestions": ["csdn"], "queries": [
                    {"adapter": "csdn", "query": "python", "purpose": "CSDN article"}]}
                return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(plan)}}]})
            synthesis = {"claims": [], "gaps": ["CSDN is best-effort"]}
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(synthesis)}}]})
        if request.url.host == "so.csdn.net":
            return httpx.Response(200, text='<a href="https://blog.csdn.net/u/article/details/123">Result</a>')
        if request.url.host == "blog.csdn.net":
            return httpx.Response(200, text='<meta name="description" content="CSDN excerpt">')
        raise AssertionError(f"unexpected host: {request.url.host}")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await research("python", settings, tmp_path, client=client, max_rounds=1)

    result = asyncio.run(run())
    records = EvidenceStore.read(result.run_dir)
    assert any(record.adapter == "csdn" and record.status == "retrieved" for record in records)
