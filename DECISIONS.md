# Decisions

## 2026-11-18-01 Python standard library for M1
- Context: M1 needs git and file diffs with the fewest dependencies and easy Windows startup.
- Decision: Use Python 3 with the standard-library `difflib`, `subprocess`, and `http.server`-ready structure, and invoke the system `git` CLI for repository diffs. M1 has no third-party dependencies or build step.
- Alternatives considered and rejected: Node/TypeScript with jsdiff and a minimal HTTP server was also reasonable, but adds a dependency and uses a separate runtime when Python is already available. A Python diff package or Git library adds dependencies without helping this small core.
- Impact / follow-ups: Run with `uv`; verify the core against Python 3.9 and 3.13. Keep the web UI in M2 on the same Python server unless evidence shows a simpler option.

## 2026-11-18-02 File inputs are local paths
- Context: The browser file picker does not expose usable absolute paths, and file mode needs to compare arbitrary local files.
- Decision: Use explicit path text fields in the future UI, with server-side validation. M1 accepts paths directly in its CLI.
- Alternatives considered and rejected: Uploading files avoids path entry but adds upload handling and duplicates files; a server-side browser is more UI work than needed for a single-user local tool.
- Impact / follow-ups: M2 must validate entered paths and keep the server bound to `127.0.0.1`.

## 2026-11-19-01 Include untracked working-tree files
- Context: Working tree vs HEAD should also show newly created, non-ignored files; the user approved this small output change.
- Decision: List untracked regular files after tracked changes, generating text diffs with `difflib`. List binary files without bodies and files over 1 MiB as omitted; skip symlinks and non-regular files.
- Alternatives considered and rejected: Omitting untracked files hides new work; staging intent-to-add would modify the index and violate the read-only constraint.
- Impact / follow-ups: Git's ignore rules, path filters, exclusions, and per-file selection apply. Staged and ref comparisons remain unchanged; the index is not modified.

## 2026-11-19-02 Decode legacy text without dependencies
- Context: Korean CP949 text and BOM-marked UTF-16 text were misread, and Git patches can mix UTF-8 paths with file content in another encoding.
- Decision: Recognize UTF-8 and UTF-16 BOMs first, then try strict UTF-8, strict CP949, and finally UTF-8 with replacement. Decode Git patches line by line so CP949 content does not corrupt UTF-8 headers and paths. Report CP949 and UTF-16 files in the summary; write CLI stdout as UTF-8.
- Alternatives considered and rejected: Chardet-style detection libraries add dependencies against the no-new-dependencies rule; decoding a whole Git patch with one codec cannot preserve mixed encodings.
- Impact / follow-ups: Detection is heuristic and UTF-8 wins when bytes are valid in both encodings. Git can still classify tracked UTF-16 files as binary.
