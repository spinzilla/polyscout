"""Offline preparation and scoring for the manual, two-judge release gate."""

import argparse
import json
import random
from pathlib import Path


QUESTIONS = {
    "T1": "Design an STM32 periodic-signal measurement instrument for an electronics competition; compare timer methods and cite implementation evidence.",
    "T2": "Select an IoT RTOS for a constrained MCU; compare licensing, maintenance and implementation tradeoffs with primary evidence.",
    "T3": "Select an open-source Deep Research framework; verify current repository maintenance and deployment requirements.",
    "T4": "Compare embedded GUI libraries for an STM32 display; verify licenses and current repository status.",
    "T5": "Choose a local speech-transcription stack for Chinese engineering videos; compare hardware requirements, licensing and evidence quality.",
}
WEIGHTS = {"penetration": 30, "detail": 30, "actionability": 20, "auditability": 15, "accuracy": 5}


def prepare(source: Path, destination: Path, seed: int = 0) -> Path:
    """Read T1-A.md/T1-B.md etc.; never call a provider or overwrite a package."""
    reports = {(qid, arm): (source / f"{qid}-{arm}.md").read_text(encoding="utf-8")
               for qid in QUESTIONS for arm in ("A", "B")}
    destination.mkdir(parents=True, exist_ok=False)
    blind = destination / "blind"
    blind.mkdir()
    rng, mapping = random.Random(seed), {}
    for qid, question in QUESTIONS.items():
        arms = ["A", "B"]
        rng.shuffle(arms)
        mapping[qid] = dict(zip(("X", "Y"), arms))
        for label, arm in mapping[qid].items():
            (blind / f"{qid}-{label}.md").write_text(reports[qid, arm], encoding="utf-8")
    (destination / "private-mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    prompt = (
        "Independently review each anonymized X/Y pair. Do not guess the authors. "
        "Use two judges from different model families in separate sessions, with no access to "
        "the private mapping or the other judge's scores. Evaluate only evidence actually present. "
        "Give each criterion points from zero to its maximum, with reasons quoting the report. "
        "Text style may reveal identity; anonymity is imperfect. No statistical significance is implied.\n\n"
        + json.dumps({"questions": QUESTIONS, "criterion_maxima": WEIGHTS}, indent=2)
        + '\n\nReturn JSON: {"judge_family":"...", "scores":{"T1":{"X":{"penetration":0,"detail":0,"actionability":0,"auditability":0,"accuracy":0},"Y":{...}},...}, "reasons":{"T1":{"X":"...","Y":"..."},...}}\n'
    )
    (blind / "JUDGE_INSTRUCTIONS.md").write_text(prompt, encoding="utf-8")
    return blind


def score(mapping: dict, judges: list[dict]) -> dict:
    if len(judges) != 2 or len({j.get("judge_family") for j in judges}) != 2:
        raise ValueError("Exactly two judges from distinct model families are required")
    outcomes = []
    for judge in judges:
        if not judge.get("judge_family"):
            raise ValueError("Missing judge family")
        margins, penetration = [], []
        for qid in QUESTIONS:
            points = {}
            for label in ("X", "Y"):
                item = judge["scores"][qid][label]
                if not judge["reasons"][qid][label].strip():
                    raise ValueError("Every score needs a written rationale")
                if set(item) != set(WEIGHTS):
                    raise ValueError("Unexpected scoring criteria")
                for criterion, maximum in WEIGHTS.items():
                    value = item[criterion]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= maximum:
                        raise ValueError("Scores must be finite and within criterion maxima")
                points[mapping[qid][label]] = item
            margins.append(sum(points["A"].values()) - sum(points["B"].values()))
            penetration.append(points["A"]["penetration"] - points["B"]["penetration"])
        outcomes.append({"judge_family": judge["judge_family"], "mean_margin": sum(margins) / len(margins),
                         "all_topics_ahead": all(m > 0 for m in margins),
                         "mean_penetration_margin": sum(penetration) / len(penetration)})
    return {"judges": outcomes, "release_gate": all(j["mean_margin"] >= 15 and j["mean_penetration_margin"] > 0 and j["all_topics_ahead"] for j in outcomes),
            "limitation": "Manual judge identities and semantic scoring are not independently verified by this script."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("source", type=Path)
    prep.add_argument("destination", type=Path)
    prep.add_argument("--seed", type=int, default=0)
    grading = sub.add_parser("score")
    grading.add_argument("mapping", type=Path)
    grading.add_argument("judges", nargs=2, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        print(prepare(args.source, args.destination, args.seed))
    else:
        print(json.dumps(score(json.loads(args.mapping.read_text(encoding="utf-8")),
                               [json.loads(p.read_text(encoding="utf-8")) for p in args.judges]), indent=2))


if __name__ == "__main__":
    main()
