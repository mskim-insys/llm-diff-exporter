# Worklog: llm-diff-exporter
Spec: specs/llm-diff-exporter.md
Status: in progress

## Handover
- Current milestone: M2 Web UI done (criteria in the spec checked); no further milestone defined.
- Done and verified: M1 core and M2 UI; encoding and identical-binary fixes and earlier Git, untracked, and UI fixes; Python 3.9 and 3.13 suites pass. Browser click-through verified both modes, selections, stale guard, and server-saved exports.
- Not done / partial: The browser download opened a Save dialog, so the user should complete a download and verify the resulting file manually. The real-symlink test was skipped because Windows denied symlink creation. Optional plain `.diff` output is not built.
- First step next session: Ask the user to verify browser download and, if available, the real-symlink test on a machine allowing symlink creation.
- Read first: specs/llm-diff-exporter.md, DECISIONS.md
- Traps: Keep inputs read-only; server is loopback-only with Host/Origin checks ([llm_diff_web.py](../llm_diff_web.py)). PowerShell 5.1 `>` writes UTF-16; use `-o` or the web UI. After inputs change, old size and saved-path text remain visible until Preview; Export is disabled.
- Open questions: Whether to address the stale UI text issue later.

## Sessions
### 2026-11-19 · Encoding and identical binaries
- Changed: Added BOM, UTF-8, CP949, and replacement decoding, per-line Git patch decoding, encoding summary notes, UTF-8 CLI stdout, and unchanged handling for identical binary files; see [DECISIONS.md](../DECISIONS.md#2026-11-19-02-decode-legacy-text-without-dependencies).
- Verified: `uv run --python 3.9 -m unittest discover -s tests` and `uv run --python 3.13 -m unittest discover -s tests` pass (33 tests each, one real-symlink test skipped). Manual Windows CLI checks confirmed Korean CP949 and BOM-marked UTF-16 files produce Korean text and the encoding note in UTF-8 output. UTF-8 LF and CRLF exports matched the previous implementation; a regression test also verifies CRLF is preserved in the saved diff body without newline translation.
- Risks / open: The real-symlink and browser download checks remain as described in Handover.

### 2026-11-19 · Bug fixes and R6 follow-up
- Changed: Fixed Git HEAD comparisons and option-shaped path filters; included non-ignored untracked files in working-tree mode; handled binary file comparisons and stale UI previews; added regression and CLI tests. A follow-up filled in the pre-existing R6 CLI heading and its acceptance criteria in the spec.
- Verified: `uv run --python 3.9 -m unittest discover -s tests` and `uv run --python 3.13 -m unittest discover -s tests` both pass (22 tests, one real-symlink test skipped; non-regular handling also tested with a mocked file type). Manual isolated Git repro listed staged and unstaged files, and `--output=` as a path created no file. Browser click-through covered Git, two files, Preview, unticking, changing patterns, re-preview, re-ticking, and Export; saved copies contained the expected selections.
- Correction: The earlier checked criterion "Git mode supports working tree vs HEAD and staged vs HEAD" was checked too early; it is now verified by `test_working_tree_includes_staged_and_unstaged_while_staged_does_not` and `test_working_tree_combines_staged_and_later_edits_against_head`.
- R6 follow-up: `test_file_cli_writes_markdown_to_output`, `test_git_cli_working_tree_includes_staged_and_unstaged`, and `test_git_cli_ref_comparison_matches_export` verify CLI output against the corresponding exporters; the focused export test module passes.
- Risks / open: The browser download Save dialog requires the user's manual confirmation; the server-saved copies were verified. The actual symlink test requires Windows symlink permission. Old size and saved-path text remain visible after input changes; the CLI stdout encoding issue is noted in Handover.

### 2026-11-19 · M2 Web UI
- Changed: Added [llm_diff_web.py](../llm_diff_web.py) (stdlib `http.server`, single embedded page), `serve` subcommand, `--exclude`, `collect_*`/`render_collected` split in [llm_diff_exporter.py](../llm_diff_exporter.py) (output format unchanged unless files are excluded, which adds one "Excluded from this export" line), `.gitignore`, [tests/test_web.py](../tests/test_web.py), README/AGENTS/spec updates.
- Verified: `uv run --python 3.13 -m unittest discover -s tests` and `--python 3.9` both OK (12 tests); started `serve`, curl returned the page and preview JSON, `Get-NetTCPConnection` showed 127.0.0.1 only.
- Risks / open: none against the spec; the optional `.diff` format is skipped.

### 2026-11-18 · M1 Export core
- Changed: Selected Python stdlib + system Git in [DECISIONS.md](../DECISIONS.md); added the export CLI/core and focused tests.
- Verified: `uv run --python 3.9 -m unittest discover -s tests` and `uv run --python 3.13 -m unittest discover -s tests` pass; `uv run --python 3.13 -m llm_diff_exporter --help` displays both modes.
- Risks / open: M2 web UI remains; see the M2 exit criteria in [specs/llm-diff-exporter.md](../specs/llm-diff-exporter.md).
