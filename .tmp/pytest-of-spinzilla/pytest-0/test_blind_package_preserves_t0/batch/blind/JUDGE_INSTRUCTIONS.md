Independently review each anonymized X/Y pair. Do not guess the authors. Use two judges from different model families in separate sessions, with no access to the private mapping or the other judge's scores. Evaluate only evidence actually present. Give each criterion points from zero to its maximum, with reasons quoting the report. Text style may reveal identity; anonymity is imperfect. No statistical significance is implied.

{
  "questions": {
    "T1": "Design an STM32 periodic-signal measurement instrument for an electronics competition; compare timer methods and cite implementation evidence.",
    "T2": "Select an IoT RTOS for a constrained MCU; compare licensing, maintenance and implementation tradeoffs with primary evidence.",
    "T3": "Select an open-source Deep Research framework; verify current repository maintenance and deployment requirements.",
    "T4": "Compare embedded GUI libraries for an STM32 display; verify licenses and current repository status.",
    "T5": "Choose a local speech-transcription stack for Chinese engineering videos; compare hardware requirements, licensing and evidence quality."
  },
  "criterion_maxima": {
    "penetration": 30,
    "detail": 30,
    "actionability": 20,
    "auditability": 15,
    "accuracy": 5
  }
}

Return JSON: {"judge_family":"...", "scores":{"T1":{"X":{"penetration":0,"detail":0,"actionability":0,"auditability":0,"accuracy":0},"Y":{...}},...}, "reasons":{"T1":{"X":"...","Y":"..."},...}}
