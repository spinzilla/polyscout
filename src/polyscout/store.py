"""Append-only JSONL evidence plus bounded excerpt files, never content mirrors."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from polyscout.models import Evidence, Observation


class EvidenceStore:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.run_dir = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:12])
        self.run_dir.mkdir(exist_ok=False)
        (self.run_dir / "raw").mkdir()
        self.path = self.run_dir / "evidence.jsonl"
        self.path.touch(exist_ok=False)
        self.records: list[Evidence] = []

    def add(self, observation: Observation) -> Evidence:
        identifier = f"E{len(self.records) + 1:04d}"
        raw_path, digest = None, None
        if observation.status == "retrieved":
            raw_path = f"raw/{identifier}.txt"
            data = observation.excerpt.encode("utf-8")
            digest = hashlib.sha256(data).hexdigest()
            with (self.run_dir / raw_path).open("xb") as stream:
                stream.write(data)
        record = Evidence(**observation.model_dump(), id=identifier, raw_path=raw_path, excerpt_sha256=digest)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(record.model_dump_json() + "\n")
        self.records.append(record)
        return record

    @staticmethod
    def read(run_dir: Path) -> list[Evidence]:
        records = [Evidence.model_validate_json(line) for line in (run_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
        seen = set()
        for record in records:
            if record.id in seen:
                raise ValueError("Duplicate evidence ID")
            seen.add(record.id)
            if record.status == "retrieved":
                if record.raw_path != f"raw/{record.id}.txt":
                    raise ValueError("Invalid excerpt path")
                data = (run_dir / record.raw_path).read_bytes()
                if hashlib.sha256(data).hexdigest() != record.excerpt_sha256 or data.decode("utf-8") != record.excerpt:
                    raise ValueError("Excerpt integrity check failed")
        return records

    def manifest(self, **values) -> None:
        (self.run_dir / "run.json").write_text(json.dumps({"schema_version": "1.0", **values}, indent=2, ensure_ascii=False), encoding="utf-8")
