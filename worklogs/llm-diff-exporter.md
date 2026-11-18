# Worklog: llm-diff-exporter
Spec: specs/llm-diff-exporter.md
Status: in progress

## Handover
- Current milestone: M1 Export core
- Done and verified: M1 file/Git export core, including special Git modes and binary handling; all three fixture tests pass on Python 3.9 and 3.13.
- Not done / partial: M2 web UI and remaining acceptance criteria.
- First step next session: Run or inspect the M1 test results, then begin M2.
- Read first: specs/llm-diff-exporter.md, DECISIONS.md
- Traps: Keep file/repository inputs local and read-only; bind any future server to `127.0.0.1`.
- Open questions: None.

## Sessions
### 2026-11-18 · M1 Export core
- Changed: Selected Python stdlib + system Git in [DECISIONS.md](../DECISIONS.md); added the export CLI/core and focused tests.
- Verified: `uv run --python 3.9 -m unittest discover -s tests` and `uv run --python 3.13 -m unittest discover -s tests` pass; `uv run --python 3.13 -m llm_diff_exporter --help` displays both modes.
- Risks / open: M2 web UI remains; see the M2 exit criteria in [specs/llm-diff-exporter.md](../specs/llm-diff-exporter.md).
