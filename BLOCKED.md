# Resolved: offline acceptance dependencies and execution sandbox

Date: 2026-10-04
Task: PolyScout architecture and v0.1 implementation
Status: RESOLVED. The user authorized repository-local dependency downloads and
the execution environment was restored. The package and tests are implemented;
current acceptance evidence is generated under `docs/validation/` by
`docs/validate.ps1`. The observations below describe the earlier blocked attempt,
not the current dependency or implementation state.

## Resolution

- A project-local `.venv` was created with uv using the existing Python 3.11.
- Runtime dependencies are httpx, pydantic and typer; pytest is development-only.
  Their transitive dependencies and setuptools build tooling were installed locally.
- `UV_CACHE_DIR`, `PIP_CACHE_DIR`, `TMP` and `TEMP` were set inside this checkout;
  automatic Python downloads were disabled. No system installation was performed.
  During final artifact inspection, an inherited system `TMPDIR` was found to
  override Python's temporary directory selection. The first four pytest runs
  therefore wrote temporary test artifacts outside the authorized project scope.
  This was an execution deviation. `docs/validate.ps1` and Quick Start now also
  set `TMPDIR` and `PYTEST_DEBUG_TEMPROOT` inside the project. Final acceptance is
  rerun with these settings. External temporary files are not deleted; cleanup
  would require separate authorization. Any earlier dependency-build temporary
  location affected by TMPDIR has not been independently established.
- A Windows restricted-token sandbox error temporarily prevented execution and
  even updating this file. The user restored the environment before work resumed.
- No live research API or paid LLM calls, account actions, delegation, Git commits
  or pushes were performed. Existing project documents and LICENSE were preserved.
- Real-provider behavior and the manual two-judge research-quality gate remain
  unverified; these are distinct from the now-resolved installation blocker.

## Observed evidence

- The existing `docs/REQUIREMENTS.md` and `docs/SPIKE.md` were read as UTF-8.
- The initial Git working tree was clean.
- `uv --version` returned `uv 0.12.7`; `python --version` returned `Python 3.11.16`.
- The selected Python executable is `D:\codex\hermes-agent-main\venv\Scripts\python.exe`.
- Import discovery found `httpx` and `pydantic`, but not `pytest` or `setuptools`; an actual import failed with `ModuleNotFoundError: No module named 'typer'`.
- The inspected uv wheel cache contains Typer and setuptools entries. No pytest package directory was found in that wheel cache. Searches of the inspected uv cache, local program directories, `D:\codex`, and `.codex` did not find a pytest wheel or executable. This is not proof that pytest is absent from every location on the machine.
- No dependency installation or package-index request was attempted.

## Authorization boundary

The task permits network access for read-only documentation HTTP GETs. Downloading project and test dependencies from a package index is not explicitly within that network scope. The mandatory acceptance command `uv run pytest` cannot currently be executed with the discovered dependencies.

Closing this blocker requires either authorization to download project/build/test dependencies into this repository, or provision of a local dependency source containing pytest and its required dependencies. No global installation is needed.

If downloads are authorized, keep the virtual environment, uv cache, temporary files, and test artifacts under `D:\polyscout`, disable automatic Python downloads, and use the existing Python 3.11 interpreter. Acceptance tests must still run offline with mocked HTTP; downloading dependencies does not authorize live research API calls.

## Work and verification status

- Code review: no v0.1 code or architecture deliverable has been created.
- Controlled environment: acceptance tests and CLI help checks have not run.
- Real environment: no GitHub, search, or LLM research API calls; unverified.
- Authorization: only repository-local files may be changed; no delegation, account operations, Git commits/pushes, or system installations were performed.
- This file is the only repository change made during this attempt.

## Requests and cost

- Two direct documentation GETs returned HTTP 200: GitHub repository REST documentation and Tavily search documentation.
- One documentation browser-tool invocation failed with HTTP 405; its underlying request count is unavailable.
- Paid research/model API requests made by the implementation: zero.
- Session token usage and session cost are not exposed to this agent; no numeric estimate is claimed.

## Next permitted stage after closure

Implement architecture, package, offline tests, and bilingual Quick Start; then execute and record `uv run pytest`, `uv run polyscout --help`, and `uv run polyscout research --help`. Preserve the frozen requirements, including explicit unavailable evidence, hard-wall circuit breaking, excerpt-only retention, and the deferred v0.2/v0.3 roadmap.
