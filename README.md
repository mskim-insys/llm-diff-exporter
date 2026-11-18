# llm-diff-exporter

Pick two things to compare in a small local web page, and get one file that is ready to attach to an LLM chat. Supports git commit/ref comparison and plain two-file comparison.

## Usage
The M1 command-line exporter accepts local file paths or a local Git repository. It writes Markdown to stdout unless `--output` is supplied.

```powershell
# Compare two text files
uv run python -m llm_diff_exporter files "C:\path\before.txt" "C:\path\after.txt" -o ".\files.md"

# Compare two commits
uv run python -m llm_diff_exporter git "C:\path\repo" <ref-a> <ref-b> -o ".\commits.md"

# Compare staged changes or the working tree against HEAD
uv run python -m llm_diff_exporter git "C:\path\repo" --staged
uv run python -m llm_diff_exporter git "C:\path\repo" --working-tree
```

Use `--context N` to change the default three context lines and repeat `--path PATH` to restrict Git mode to repository-relative paths. `--help` lists all options. The output includes a summary, per-file unified diffs, and approximate character/token counts. Binary files are listed but omitted from diff sections. Invalid UTF-8 bytes in text files are replaced safely.

## Build and run
- Build: No build step; the implementation uses the Python standard library and system Git.
- Test: `uv run python -m unittest discover -s tests`
- Runtime: Python 3.9 or 3.13 with `uv`, plus the system `git` executable.

## Current behavior and limits
M1 export logic and CLI are implemented. The browser UI, output-folder defaults, recent repositories, and other M2 interactions are not available yet. Inputs are read-only; the exporter does not call external services.
