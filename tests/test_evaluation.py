import json

import pytest

from polyscout.evaluation import QUESTIONS, WEIGHTS, prepare, score


def test_blind_package_preserves_text_and_keeps_mapping_outside(tmp_path):
    source = tmp_path / "inputs"
    source.mkdir()
    for qid in QUESTIONS:
        for arm in ("A", "B"):
            (source / f"{qid}-{arm}.md").write_text(f"Exact report {qid} {arm}", encoding="utf-8")
    blind = prepare(source, tmp_path / "batch", 42)
    mapping = json.loads((blind.parent / "private-mapping.json").read_text())
    assert len(list(blind.glob("T*.md"))) == 10
    assert not (blind / "private-mapping.json").exists()
    for qid, labels in mapping.items():
        for label, arm in labels.items():
            assert (blind / f"{qid}-{label}.md").read_text() == f"Exact report {qid} {arm}"
    with pytest.raises(FileExistsError):
        prepare(source, blind.parent)


def test_two_independent_judge_gate_and_invalid_scores():
    mapping = {qid: {"X": "A", "Y": "B"} for qid in QUESTIONS}
    judges = [{"judge_family": family, "scores": {qid: {"X": dict(WEIGHTS), "Y": dict.fromkeys(WEIGHTS, 0)} for qid in QUESTIONS},
               "reasons": {qid: {"X": "Cites actual source evidence", "Y": "Unsupported statements"} for qid in QUESTIONS}}
              for family in ("family-one", "family-two")]
    assert score(mapping, judges)["release_gate"] is True
    judges[1]["judge_family"] = "family-one"
    with pytest.raises(ValueError):
        score(mapping, judges)
    judges[1]["judge_family"] = "family-two"
    judges[0]["scores"]["T1"]["X"]["accuracy"] = 100
    with pytest.raises(ValueError):
        score(mapping, judges)
