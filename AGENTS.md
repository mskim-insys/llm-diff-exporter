# llm-diff-exporter

A small local tool for one user (Windows). A rough web UI lets the user pick what to compare (two commits of a git repo, or two plain files), and saves the diff as a single file that is easy for an LLM to read and can be attached to a chat as-is.

## Read first
- `specs/llm-diff-exporter.md` for requirements, constraints, acceptance criteria, and milestones. It is the only source of truth for what to build.
- `DECISIONS.md` (create it when the first decision is made) before changing the stack or retrying a rejected approach.
- `README.md` for current usage and behavior (only what already works).

## Start here (first session)
1. Read the spec fully. Merge is out of scope for now.
2. Pick the stack (see "Stack" in the spec): fewest dependencies, easiest to run on Windows, reuse existing libraries instead of writing diff logic. Record the choice and the rejected options as the first `DECISIONS.md` entry.
3. Fill in the Commands section below, then start M1.

## Commands
- Build: No build step (Python standard library only).
- Test: `uv run python -m unittest discover -s tests`
- Run: `uv run python -m llm_diff_exporter --help`
- Run (web UI, one command): `uv run python -m llm_diff_exporter serve`

## Boundaries
- Do not send file or diff contents anywhere off this machine (no network calls, no telemetry, no LLM API calls). The tool only produces a file.
- Do not add native or unsigned binary dependencies without asking first. Windows Smart App Control on the user's machine has blocked a native tool before; prefer pure-JS/pure-Python packages and the system `git` CLI.
- Ask first: adding a dependency that is large or poorly maintained, changing the output format after M1 is accepted, or starting any merge feature.
- Do not edit the user's repositories or files being compared. The tool is read-only on its inputs.

## Workspace docs
- Rules for these files: `WORKSPACE.md`
- Create `DECISIONS.md`, `worklogs/`, and `archive/` when their triggers fire. Follow the session start/end protocol in the guide.
