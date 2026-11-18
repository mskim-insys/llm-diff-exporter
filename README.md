# llm-diff-exporter

Pick two things to compare in a small local web page, and get one file that is ready to attach to an LLM chat. Supports git commit/ref comparison and plain two-file comparison.

## Usage
Start the web UI (binds to `127.0.0.1` only, opens your browser):

```powershell
uv run python -m llm_diff_exporter serve
```

Options: `--port N` (default 8765, `0` = any free port), `--out-dir PATH`, `--no-browser`. Stop with Ctrl+C.

In the page, choose **Git** (enter the repository folder, click *Load commits / branches*, then pick refs or type any ref/hash; or compare working tree / staged against HEAD) or **Two files** (enter both paths; quotes from "Copy as path" are accepted). *Preview* lists the changed files with their size in characters and estimated tokens; untick a file to leave it out (size updates). Exclude patterns (one glob per line, defaults cover lockfiles, `*.min.js`, `*.map`) are applied at preview. *Export* downloads the Markdown and saves a copy to the output folder (default `out/` in the current directory, git-ignored; folders inside the compared repository are refused). Recently used repository paths are remembered in the browser only.

The M1 command-line exporter also works without the UI. It writes Markdown to stdout unless `--output` is supplied.

```powershell
# Compare two text files
uv run python -m llm_diff_exporter files "C:\path\before.txt" "C:\path\after.txt" -o ".\files.md"

# Compare two commits
uv run python -m llm_diff_exporter git "C:\path\repo" <ref-a> <ref-b> -o ".\commits.md"

# Compare staged changes or the working tree against HEAD
uv run python -m llm_diff_exporter git "C:\path\repo" --staged
uv run python -m llm_diff_exporter git "C:\path\repo" --working-tree
```

Use `--context N` to change the default three context lines, repeat `--path PATH` to restrict Git mode to repository-relative paths, and repeat `--exclude GLOB` to leave files out. `--help` lists all options. The output includes a summary, per-file unified diffs, and approximate character/token counts. Binary files are listed but omitted from diff sections. Invalid UTF-8 bytes in text files are replaced safely.

## Build and run
- Build: No build step; the implementation uses the Python standard library and system Git.
- Test: `uv run python -m unittest discover -s tests`
- Runtime: Python 3.9 or 3.13 with `uv`, plus the system `git` executable.

## Current behavior and limits
Export core, CLI, and the local web UI are implemented. The server accepts only `127.0.0.1`/`localhost` Host and Origin headers, makes no outbound network calls, and only reads the compared inputs (it writes only to the output folder). Output is Markdown only; there is no plain `.diff` option and no folder-vs-folder or merge support.
