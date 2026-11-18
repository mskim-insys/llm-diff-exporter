# Worklog: llm-diff-exporter
Spec: specs/llm-diff-exporter.md
Status: in progress

## Handover
- Current milestone: M2 Web UI done (criteria in the spec checked); no further milestone defined.
- Done and verified: M1 core; M2 UI server, preview/size, export + save, R5 patterns and per-file exclusion; 12 tests pass on Python 3.9 and 3.13; server smoke-tested (listens on 127.0.0.1:8765 only).
- Not done / partial: Plain `.diff` output option (optional in R2) not built; the browser page itself was not clicked through in a browser, only its API was exercised.
- First step next session: Open `serve` in a browser and try a real repo; fix any UI rough edges.
- Read first: specs/llm-diff-exporter.md, DECISIONS.md
- Traps: Keep inputs read-only; server is loopback-only with Host/Origin checks ([llm_diff_web.py](../llm_diff_web.py)). `__pycache__` was untracked from git.
- Open questions: None.

## Sessions
### 2026-11-19 · M2 Web UI
- Changed: Added [llm_diff_web.py](../llm_diff_web.py) (stdlib `http.server`, single embedded page), `serve` subcommand, `--exclude`, `collect_*`/`render_collected` split in [llm_diff_exporter.py](../llm_diff_exporter.py) (output format unchanged unless files are excluded, which adds one "Excluded from this export" line), `.gitignore`, [tests/test_web.py](../tests/test_web.py), README/AGENTS/spec updates.
- Verified: `uv run --python 3.13 -m unittest discover -s tests` and `--python 3.9` both OK (12 tests); started `serve`, curl returned the page and preview JSON, `Get-NetTCPConnection` showed 127.0.0.1 only.
- Risks / open: none against the spec; the optional `.diff` format is skipped.

### 2026-11-18 · M1 Export core
- Changed: Selected Python stdlib + system Git in [DECISIONS.md](../DECISIONS.md); added the export CLI/core and focused tests.
- Verified: `uv run --python 3.9 -m unittest discover -s tests` and `uv run --python 3.13 -m unittest discover -s tests` pass; `uv run --python 3.13 -m llm_diff_exporter --help` displays both modes.
- Risks / open: M2 web UI remains; see the M2 exit criteria in [specs/llm-diff-exporter.md](../specs/llm-diff-exporter.md).
