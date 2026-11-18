"""Generate Markdown diffs for local files and Git revisions."""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence


class DiffExportError(Exception):
    """Raised when an input cannot be compared or Git reports an error."""


@dataclass
class FileChange:
    path: str
    status: str
    diff: str
    added: int
    removed: int
    binary: bool = False
    key_path: str = ""


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except OSError as exc:
        raise DiffExportError("Cannot read {}: {}".format(path, exc)) from exc


def _line_counts(diff: str) -> tuple[int, int]:
    added = 0
    removed = 0
    for line in diff.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def _format_path(path: str) -> str:
    return path.replace("\r", "\\r").replace("\n", "\\n")


@dataclass
class Collected:
    """Changes found for one comparison, before exclusions are applied."""

    mode: str
    description: str
    label: str
    changes: list
    context: int


DEFAULT_EXCLUDES = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "uv.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "composer.lock",
    "*.min.js",
    "*.min.css",
    "*.map",
)


def _is_excluded(change: FileChange, patterns: Sequence[str], files: Sequence[str]) -> bool:
    if change.path in files:
        return True
    target = (change.key_path or change.path).replace("\\", "/")
    base = target.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatch(target, pattern) or fnmatch.fnmatch(base, pattern)
        for pattern in patterns
        if pattern
    )


def apply_exclusions(
    changes: Sequence[FileChange],
    patterns: Sequence[str] = (),
    files: Sequence[str] = (),
) -> tuple[list, list]:
    """Split changes into (kept, excluded) by glob patterns and exact display paths."""
    kept = []
    excluded = []
    for change in changes:
        (excluded if _is_excluded(change, patterns, files) else kept).append(change)
    return kept, excluded


def render_collected(
    collected: Collected,
    patterns: Sequence[str] = (),
    files: Sequence[str] = (),
) -> str:
    kept, excluded = apply_exclusions(collected.changes, patterns, files)
    return _build_markdown(
        collected.mode, collected.description, kept, collected.context, excluded
    )


def _build_markdown(
    mode: str,
    description: str,
    changes: Sequence[FileChange],
    context: int,
    excluded: Sequence[FileChange] = (),
) -> str:
    added = sum(change.added for change in changes)
    removed = sum(change.removed for change in changes)
    date = datetime.now().astimezone().date().isoformat()
    summary = [
        "- Files changed: {}".format(len(changes)),
        "- Lines added: {}".format(added),
        "- Lines removed: {}".format(removed),
        "",
        "### Files",
    ]
    for change in changes:
        summary.append("- `{}` — {}".format(_format_path(change.path), change.status))
    if any(change.binary for change in changes):
        summary.extend(["", "Binary files are listed above and omitted from the diff body."])
    if excluded:
        summary.extend(
            ["", "Excluded from this export: {}".format(
                ", ".join("`{}`".format(_format_path(c.path)) for c in excluded)
            )]
        )

    sections = []
    for change in changes:
        if change.binary:
            continue
        longest_run = max(
            (len(run) for run in re.findall(r"`+", change.diff)),
            default=0,
        )
        fence = "`" * max(3, longest_run + 1)
        sections.extend(
            [
                "## {}".format(_format_path(change.path)),
                "",
                fence + "diff",
                change.diff.rstrip("\n"),
                fence,
                "",
            ]
        )

    def render(characters: int) -> str:
        tokens = (characters + 3) // 4
        return "\n".join(
            [
                "# Diff export",
                "",
                "- Mode: {}".format(mode),
                "- Compared: {}".format(description),
                "- Generated: {}".format(date),
                "- Context lines: {}".format(context),
                "- Approximate size: {} characters (~{} tokens)".format(characters, tokens),
                "",
                "## Summary",
                "",
            ]
            + summary
            + ([""] + sections if sections else [])
        ).rstrip() + "\n"

    result = render(0)
    for _ in range(10):
        updated = render(len(result))
        if len(updated) == len(result):
            return updated
        result = updated
    return result


def collect_files(
    file_a: str | os.PathLike[str],
    file_b: str | os.PathLike[str],
    context: int = 3,
) -> Collected:
    if context < 0:
        raise DiffExportError("Context lines cannot be negative.")
    path_a = Path(file_a)
    path_b = Path(file_b)
    text_a = _read_text(path_a)
    text_b = _read_text(path_b)
    diff = "".join(
        difflib.unified_diff(
            text_a.splitlines(keepends=True),
            text_b.splitlines(keepends=True),
            fromfile="a/{}".format(path_a.name),
            tofile="b/{}".format(path_b.name),
            n=context,
        )
    )
    added, removed = _line_counts(diff)
    change = FileChange(
        path="{} → {}".format(path_a.name, path_b.name),
        status="modified" if diff else "unchanged",
        diff=diff,
        added=added,
        removed=removed,
        key_path=path_b.name,
    )
    return Collected(
        "files",
        "{} and {}".format(path_a, path_b),
        "{}_{}".format(path_a.stem, path_b.stem),
        [change] if diff else [],
        context,
    )


def export_files(
    file_a: str | os.PathLike[str],
    file_b: str | os.PathLike[str],
    context: int = 3,
    exclude: Sequence[str] = (),
) -> str:
    """Return a Markdown diff for two UTF-8 text files."""
    return render_collected(collect_files(file_a, file_b, context), exclude)


def _git(
    repo: Path,
    args: Sequence[str],
) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false"] + list(args),
            cwd=str(repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise DiffExportError("Cannot run git: {}".format(exc)) from exc
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise DiffExportError(message or "git exited with status {}".format(result.returncode))
    return result.stdout


def _resolve_commit(repo: Path, ref: str) -> tuple[str, str, str]:
    resolved = _git(repo, ["rev-parse", "--verify", "--end-of-options", ref + "^{commit}"])
    commit = resolved.decode("ascii").strip()
    subject = _git(repo, ["show", "-s", "--format=%s", commit]).decode(
        "utf-8", errors="replace"
    ).strip()
    return commit, commit[:7], subject


def _parse_name_status(output: bytes) -> list[tuple[str, str, str]]:
    fields = output.decode("utf-8", errors="replace").split("\0")
    changes = []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index]
        index += 1
        if status.startswith(("R", "C")):
            old_path, new_path = fields[index], fields[index + 1]
            index += 2
        else:
            old_path = ""
            new_path = fields[index]
            index += 1
        changes.append((status, old_path, new_path))
    return changes


def _parse_numstat(output: bytes) -> dict[str, tuple[int, int, bool]]:
    fields = output.decode("utf-8", errors="replace").split("\0")
    result = {}
    index = 0
    while index < len(fields) and fields[index]:
        added_text, removed_text, path = fields[index].split("\t", 2)
        index += 1
        if not path:
            index += 2
            path = fields[index - 1]
        binary = added_text == "-" or removed_text == "-"
        added = 0 if binary else int(added_text)
        removed = 0 if binary else int(removed_text)
        result[path] = (added, removed, binary)
    return result


def _git_diff_args(
    ref_a: Optional[str],
    ref_b: Optional[str],
    staged: bool,
    context: int,
    output_format: str,
) -> list[str]:
    args = ["diff", "--no-ext-diff", "--no-color", "--unified={}".format(context)]
    if staged:
        args.append("--cached")
    if ref_a is not None and ref_b is not None:
        args.extend([ref_a, ref_b])
    args.append("--find-renames")
    if output_format in ("--name-status", "--numstat"):
        args.append("-z")
    args.append(output_format)
    return args


def list_git_refs(repo_path: str | os.PathLike[str], limit: int = 30) -> dict:
    """Return recent commits, branches, and tags of a repository (read-only)."""
    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise DiffExportError("Repository path is not a directory: {}".format(repo))
    log = _git(repo, ["log", "-n", str(limit), "--format=%H%x00%h%x00%s%x00%cs"])
    commits = []
    for line in log.decode("utf-8", errors="replace").splitlines():
        parts = line.split("\0")
        if len(parts) == 4:
            commits.append(
                {"hash": parts[0], "short": parts[1], "subject": parts[2], "date": parts[3]}
            )

    def names(pattern: str) -> list:
        out = _git(repo, ["for-each-ref", "--format=%(refname:short)", pattern])
        return [n for n in out.decode("utf-8", errors="replace").splitlines() if n]

    return {
        "commits": commits,
        "branches": names("refs/heads"),
        "tags": names("refs/tags"),
    }


def collect_git(
    repo_path: str | os.PathLike[str],
    ref_a: Optional[str] = None,
    ref_b: Optional[str] = None,
    context: int = 3,
    paths: Optional[Sequence[str]] = None,
    staged: bool = False,
    working_tree: bool = False,
) -> Collected:
    if context < 0:
        raise DiffExportError("Context lines cannot be negative.")
    if staged and working_tree:
        raise DiffExportError("Choose either staged or working-tree mode, not both.")
    if (ref_a is None) != (ref_b is None):
        raise DiffExportError("Provide both refs, or neither.")
    if ref_a is not None and (staged or working_tree):
        raise DiffExportError("Refs cannot be combined with staged or working-tree mode.")

    repo = Path(repo_path).resolve()
    if not repo.is_dir():
        raise DiffExportError("Repository path is not a directory: {}".format(repo))

    if staged or working_tree:
        left_commit, short_head, subject_head = _resolve_commit(repo, "HEAD")
        left_ref = "HEAD ({}, {})".format(short_head, subject_head)
        right_ref = "staged changes" if staged else "working tree"
        right_commit = None
        description = "{}: {} vs {}".format(repo, right_ref, left_ref)
    else:
        requested_a = ref_a or "HEAD"
        requested_b = ref_b or "HEAD"
        left_commit, short_a, subject_a = _resolve_commit(repo, requested_a)
        right_commit, short_b, subject_b = _resolve_commit(repo, requested_b)
        left_ref = "{} ({}, {})".format(requested_a, short_a, subject_a)
        right_ref = "{} ({}, {})".format(requested_b, short_b, subject_b)
        description = "{}: {} to {}".format(repo, left_ref, right_ref)

    name_args = _git_diff_args(left_commit, right_commit, staged, context, "--name-status")
    numstat_args = _git_diff_args(left_commit, right_commit, staged, context, "--numstat")
    selected_paths = list(paths or [])
    if selected_paths:
        name_args.extend(selected_paths)
        numstat_args.extend(selected_paths)
    named_changes = _parse_name_status(_git(repo, name_args))
    numstats = _parse_numstat(_git(repo, numstat_args))

    changes = []
    for status_code, old_path, new_path in named_changes:
        status = {
            "A": "added",
            "D": "deleted",
            "M": "modified",
            "R": "renamed",
            "C": "copied",
            "T": "modified",
            "U": "modified",
        }.get(status_code[0], "modified")
        display_path = new_path
        if status_code.startswith("R"):
            display_path = "{} → {}".format(old_path, new_path)
        added, removed, binary = numstats.get(new_path, (0, 0, False))
        file_paths = [new_path]
        if old_path:
            file_paths.insert(0, old_path)
        diff_args = _git_diff_args(
            left_commit,
            right_commit,
            staged,
            context,
            "--",
        )
        diff_args.extend(file_paths)
        diff = "" if binary else _git(repo, diff_args).decode("utf-8", errors="replace")
        changes.append(
            FileChange(
                path=display_path,
                status="binary" if binary else status,
                diff=diff,
                added=added,
                removed=removed,
                binary=binary,
                key_path=new_path,
            )
        )

    if staged or working_tree:
        label = "{}_{}_vs_HEAD".format(repo.name, "staged" if staged else "working")
    else:
        label = "{}_{}..{}".format(repo.name, short_a, short_b)
    return Collected("git", description, label, changes, context)


def export_git(
    repo_path: str | os.PathLike[str],
    ref_a: Optional[str] = None,
    ref_b: Optional[str] = None,
    context: int = 3,
    paths: Optional[Sequence[str]] = None,
    staged: bool = False,
    working_tree: bool = False,
    exclude: Sequence[str] = (),
) -> str:
    """Return a Markdown diff for two commits or a working/staged tree and HEAD."""
    collected = collect_git(
        repo_path, ref_a, ref_b, context, paths, staged, working_tree
    )
    return render_collected(collected, exclude)


def _write_output(content: str, output: Optional[str]) -> None:
    if output:
        try:
            with Path(output).open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
        except OSError as exc:
            raise DiffExportError("Cannot write {}: {}".format(output, exc)) from exc
    else:
        sys.stdout.write(content)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export local diffs as LLM-friendly Markdown.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    files_parser = subparsers.add_parser("files", help="Compare two text files.")
    files_parser.add_argument("file_a")
    files_parser.add_argument("file_b")
    files_parser.add_argument("--context", type=int, default=3)
    files_parser.add_argument("--output", "-o")

    git_parser = subparsers.add_parser("git", help="Compare Git refs, staged changes, or worktree.")
    git_parser.add_argument("repo")
    git_parser.add_argument("refs", nargs="*")
    git_parser.add_argument("--staged", action="store_true")
    git_parser.add_argument("--working-tree", action="store_true")
    git_parser.add_argument("--context", type=int, default=3)
    git_parser.add_argument("--path", action="append", dest="paths")
    git_parser.add_argument("--exclude", action="append", default=[], help="Glob to leave out (repeatable).")
    git_parser.add_argument("--output", "-o")

    serve_parser = subparsers.add_parser("serve", help="Start the local web UI and open it.")
    serve_parser.add_argument("--port", type=int, default=8765, help="Port on 127.0.0.1 (0 = any free port).")
    serve_parser.add_argument("--out-dir", help="Default output folder (default: ./out).")
    serve_parser.add_argument("--no-browser", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "serve":
        from llm_diff_web import serve

        return serve(args.port, args.out_dir, open_browser=not args.no_browser)
    try:
        if args.command == "files":
            content = export_files(args.file_a, args.file_b, args.context)
        else:
            if len(args.refs) not in (0, 2):
                parser.error("git mode accepts either two refs or no refs")
            content = export_git(
                args.repo,
                args.refs[0] if args.refs else None,
                args.refs[1] if args.refs else None,
                context=args.context,
                paths=args.paths,
                staged=args.staged,
                working_tree=args.working_tree,
                exclude=args.exclude,
            )
        _write_output(content, args.output)
    except DiffExportError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
