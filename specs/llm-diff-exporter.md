# Spec: llm-diff-exporter
Status: active
Last updated: 2026-11-18

## Goal
A local tool with a rough web UI. The user picks what to compare, and the tool saves the result as a single file in a form an LLM reads easily, so the user can attach it to a chat right away. The overriding priority is a fast, low-effort implementation: reuse existing libraries and the system `git` CLI rather than writing diff logic. A polished UI is not a goal.

## Requirements

### R1. Two comparison modes
- **Git mode.** The user gives a repository path and two refs (commit hash, branch, or tag), and gets the diff between them. Also support "working tree vs HEAD" and "staged vs HEAD". Optionally limit to given paths.
- **File mode.** The user picks two files (A and B), like a simple WinMerge comparison, and gets the diff of A against B.
- Folder-vs-folder comparison is not required for v1 (see Out of scope).

### R2. LLM-friendly single-file output
One output file per export. Default format is Markdown (`.md`); a plain `.diff`/`.txt` option is welcome if it is cheap. Contents, in this order:
1. A short header: what was compared (mode, repo path or file names, the two refs with short hashes and commit subjects in git mode), generation date, and context-line count used.
2. A summary: number of files changed, lines added and removed, and a one-line-per-file list with status (added, modified, deleted, renamed, binary).
3. One section per changed file with its unified diff in a fenced code block tagged `diff`.

The file must make sense to an LLM that has never seen the repo. Rules:
- The code fence must be longer than any run of backticks inside the diff, so the Markdown never breaks.
- Binary files are listed in the summary and skipped in the body, with a note.
- Show an approximate size (characters and an estimated token count) in the UI and in the header, so the user knows whether it fits a chat. A rough estimate (for example characters / 4) is enough.
- Context lines are configurable, default 3.

### R3. Selecting inputs in the web UI
- A browser file picker does not reveal real paths, so the design must handle this explicitly. Decide in M1/M2 and log it in `DECISIONS.md`. Acceptable options: a path text box with server-side validation plus a recent-paths list; browser upload of the two files in file mode; a simple server-side folder browser.
- In git mode, list recent commits and branches of the chosen repo so refs can be picked without typing hashes.

### R4. Output handling
- The UI offers a download of the generated file and also saves a copy to a configurable output folder (default: an `out/` folder in the workspace, git-ignored).
- File names are descriptive, for example `diff_<repo>_<shortA>..<shortB>_<date>.md`.

### R5. Reduce noise (small, optional options)
- Exclude patterns for lockfiles and generated files (default list is editable), and a per-file checkbox to leave a file out before exporting.

## Constraints
- Runs locally on Windows only; no server deployment, no authentication, no accounts.
- Fully offline: no network calls, no API keys, no telemetry.
- Read-only on the user's repositories and files.
- Prefer the system `git` CLI (called without a shell, arguments passed as a list) for git mode, and an existing diff library for file mode, instead of a git library or custom diff code.
- Prefer pure-JS/pure-Python dependencies. Avoid unsigned native binaries (Windows Smart App Control has blocked such tools on this machine).
- Handle Windows paths with spaces and non-ASCII characters, CRLF line endings, and UTF-8 files (with a safe fallback for undecodable bytes).
- Bind the web server to `127.0.0.1` only.

## Stack
Open. Choose the option with the fewest dependencies and the easiest Windows startup, and record it as the first decision. Two reasonable candidates:
- Node/TypeScript: `git` CLI + the `diff` package (jsdiff) for file mode + a minimal HTTP server with a single static page.
- Python 3: `git` CLI + stdlib `difflib` for file mode + a minimal server (stdlib `http.server`, or Flask/FastAPI if clearly easier).

A single command to start the tool and open the page is the target. Avoid a build step for the front end if possible (one HTML file with plain JS is enough).

## Out of scope (for now)
- Merge, three-way diff, applying patches, or editing files. Do not design against it, but do not build it.
- Folder-vs-folder comparison, syntax highlighting, side-by-side view, and any polished UI.
- Calling an LLM API or summarizing the diff.

## Acceptance criteria
- [x] Git mode exports the diff between two commits of a real repository, including added, deleted, renamed, and binary files.
- [x] Git mode supports working tree vs HEAD and staged vs HEAD.
- [x] File mode exports the diff of two arbitrary text files.
- [x] The output file has the header, summary, and per-file diff sections defined in R2, and renders correctly in Markdown even when the diff contains triple backticks.
- [ ] The UI shows the size and estimated token count before download.
- [x] Paths with spaces, non-ASCII names, and CRLF files work on Windows.
- [ ] The server listens on `127.0.0.1` only, and no outbound network call is made.
- [ ] The tool starts with one documented command, and `README.md` explains usage.
- [x] Automated tests cover the export logic for both modes (using small fixture repos/files created by the tests).

## Milestones
### M1 Export core
- Exit criteria: git mode and file mode produce the R2 output file from a function or script call (no UI yet); the acceptance criteria for both modes, the Markdown fence safety, the binary handling, and the tests are checked.
### M2 Web UI
- Exit criteria: the UI selects inputs (R3), shows the size/token estimate, and downloads or saves the file (R4); the Windows path, localhost-only, and one-command-start criteria are checked; `README.md` is updated with real usage. R5 noise options are added here if cheap.

## Plan
Keep it small: do M1 in one session, then M2. If a choice comes up that this spec does not settle (for example the input-selection approach in R3), decide the simplest option that works, record it in `DECISIONS.md`, and move on.
