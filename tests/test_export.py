import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm_diff_exporter import collect_git, export_files, export_git


class ExportFilesTests(unittest.TestCase):
    def test_utf8_output_matches_existing_format(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b = root / "a", root / "b"
            path_a.write_bytes(b"before\n")
            path_b.write_bytes(b"after\n")
            with patch("llm_diff_exporter.datetime") as clock:
                clock.now.return_value.astimezone.return_value.date.return_value.isoformat.return_value = "2026-11-19"
                output = export_files(path_a, path_b)
            size = len(output)
            expected = (
                "# Diff export\n\n"
                "- Mode: files\n"
                "- Compared: {} and {}\n"
                "- Generated: 2026-11-19\n"
                "- Context lines: 3\n"
                "- Approximate size: {} characters (~{} tokens)\n\n"
                "## Summary\n\n"
                "- Files changed: 1\n"
                "- Lines added: 1\n"
                "- Lines removed: 1\n\n"
                "### Files\n"
                "- `a → b` — modified\n\n"
                "## a → b\n\n"
                "```diff\n"
                "--- a/a\n"
                "+++ b/b\n"
                "@@ -1 +1 @@\n"
                "-before\n"
                "+after\n"
                "```\n"
            ).format(path_a, path_b, size, (size + 3) // 4)
        self.assertEqual(output, expected)

    def test_output_file_preserves_crlf_in_diff_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b, output_path = root / "a", root / "b", root / "result.md"
            path_a.write_bytes(b"before\r\n")
            path_b.write_bytes(b"after\r\n")
            subprocess.check_call([
                sys.executable, "-m", "llm_diff_exporter", "files",
                str(path_a), str(path_b), "-o", str(output_path),
            ])
            output = output_path.read_bytes()
        self.assertFalse(output.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"-before\r\n+after\r\n", output)
        self.assertNotIn(b"\r\r\n", output)

    def test_utf8_bom_is_stripped_and_output_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b = root / "a", root / "b"
            path_a.write_bytes(b"before\n")
            path_b.write_bytes(b"after\n")
            expected = export_files(path_a, path_b)
            path_b.write_bytes(b"\xef\xbb\xbfafter\n")
            output = export_files(path_a, path_b)
        self.assertEqual(output, expected)
        self.assertNotIn("\ufeff", output)
        self.assertNotIn("Decoded as", output)

    def test_utf16_bom_is_text_and_is_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b = root / "a", root / "b"
            path_a.write_bytes(b"before\n")
            path_b.write_bytes(b"\xff\xfe" + "한글\n".encode("utf-16-le"))
            output = export_files(path_a, path_b)
        self.assertIn("+한글", output)
        self.assertIn("Decoded as utf-16: `b`", output)
        self.assertNotIn("— binary", output)
        self.assertNotIn("\ufeff", output)

    def test_cp949_is_decoded_and_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b = root / "a", root / "b"
            path_a.write_bytes(b"before\n")
            path_b.write_bytes(b"\xc7\xd1\xb1\xdb\n")
            output = export_files(path_a, path_b)
        self.assertIn("+한글", output)
        self.assertIn("Decoded as cp949: `b`", output)
        self.assertNotIn("\ufffd", output)

    def test_utf16_be_and_unrecognized_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b = root / "a", root / "b"
            path_a.write_bytes(b"\xfe\xff" + "before\n".encode("utf-16-be"))
            path_b.write_bytes(b"\xff\n")
            output = export_files(path_a, path_b)
        self.assertIn("-before", output)
        self.assertIn("+\ufffd", output)
        self.assertIn("Decoded as utf-16: `a`", output)
        self.assertNotIn("Decoded as cp949", output)

    def test_identical_binary_files_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b = root / "a", root / "b"
            path_a.write_bytes(b"\x00\x01")
            path_b.write_bytes(b"\x00\x01")
            output = export_files(path_a, path_b)
        self.assertIn("- Files changed: 0", output)
        self.assertNotIn("— binary", output)

    def test_cli_stdout_is_utf8_with_cp949_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a, path_b = root / "a", root / "b"
            path_a.write_bytes(b"before\n")
            path_b.write_bytes("한글\n".encode("utf-8"))
            environment = os.environ.copy()
            environment["PYTHONIOENCODING"] = "cp949"
            result = subprocess.run(
                [sys.executable, "-m", "llm_diff_exporter", "files", str(path_a), str(path_b)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("+한글", result.stdout.decode("utf-8"))
        self.assertNotIn(b"\r\n", result.stdout)

    def test_binary_file_is_listed_without_diff_body(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a = root / "a"
            path_b = root / "b"
            path_a.write_bytes(b"hello\n")
            path_b.write_bytes(b"hello\x00world\n")
            output = export_files(path_a, path_b)

        self.assertIn("a → b` — binary", output)
        self.assertIn("Binary files are listed above", output)
        self.assertNotIn("```diff", output)

    def test_file_cli_writes_markdown_to_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a = root / "a.txt"
            path_b = root / "b.txt"
            output_path = root / "result.md"
            path_a.write_bytes(b"before\n")
            path_b.write_bytes(b"after\n")
            subprocess.check_call([
                sys.executable, "-m", "llm_diff_exporter", "files",
                str(path_a), str(path_b), "-o", str(output_path),
            ])
            output = output_path.read_text(encoding="utf-8")
            self.assertEqual(output, export_files(path_a, path_b))

    def test_file_diff_handles_crlf_and_fence_longer_than_backtick_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path_a = root / "alpha file.txt"
            path_b = root / "βeta.txt"
            path_a.write_bytes(b"before\r\n```python\r\n")
            path_b.write_bytes("after\r\n````python\r\n".encode("utf-8"))

            output = export_files(path_a, path_b, context=0)

        self.assertIn("Lines added: 2", output)
        self.assertIn("Lines removed: 2", output)
        self.assertIn("```diff", output)
        self.assertIn("`````diff", output)
        size = re.search(r"Approximate size: (\d+) characters \(~(\d+) tokens\)", output)
        self.assertIsNotNone(size)
        self.assertEqual(int(size.group(1)), len(output))
        self.assertEqual(int(size.group(2)), (len(output) + 3) // 4)


class ExportGitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo with spaces"
        self.repo.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Test User")
        self._git("config", "user.email", "test@example.invalid")
        (self.repo / "keep.txt").write_text("one\n", encoding="utf-8")
        (self.repo / "old name.txt").write_text("rename contents\n", encoding="utf-8")
        (self.repo / "remove.txt").write_text("remove me\n", encoding="utf-8")
        (self.repo / "binary.bin").write_bytes(b"\x00\x01")
        self._git("add", ".")
        self._git("commit", "-qm", "initial")
        self.first = self._git("rev-parse", "HEAD").strip()

        (self.repo / "keep.txt").write_text("one\ntwo\n", encoding="utf-8")
        (self.repo / "old name.txt").rename(self.repo / "new name.txt")
        (self.repo / "remove.txt").unlink()
        (self.repo / "added-추가.txt").write_text("new file\n", encoding="utf-8")
        (self.repo / "binary.bin").write_bytes(b"\x00\x02")
        self._git("add", "-A")
        self._git("commit", "-qm", "second")
        self.second = self._git("rev-parse", "HEAD").strip()

    def tearDown(self):
        self.temporary.cleanup()

    def _git(self, *args):
        return subprocess.check_output(["git"] + list(args), cwd=str(self.repo), text=True)

    def test_tracked_cp949_with_utf8_korean_path(self):
        path = self.repo / "한글.txt"
        path.write_bytes(b"before\n")
        self._git("add", path.name)
        self._git("commit", "-qm", "add legacy")
        path.write_bytes(b"\xc7\xd1\xb1\xdb\n")
        output = export_git(self.repo, working_tree=True)
        self.assertIn("diff --git a/한글.txt b/한글.txt", output)
        self.assertIn("+한글", output)
        self.assertIn("Decoded as cp949: `한글.txt`", output)
        self.assertNotIn("\ufffd", output)
        excluded = export_git(self.repo, working_tree=True, exclude=["한글.txt"])
        self.assertNotIn("Decoded as", excluded)

    def test_untracked_cp949_and_utf16(self):
        (self.repo / "legacy.txt").write_bytes(b"\xc7\xd1\xb1\xdb\n")
        (self.repo / "powershell.txt").write_bytes(b"\xff\xfe" + "한글\n".encode("utf-16-le"))
        output = export_git(self.repo, working_tree=True)
        self.assertIn("Decoded as cp949: `legacy.txt`", output)
        self.assertIn("Decoded as utf-16: `powershell.txt`", output)
        self.assertEqual(output.count("+한글"), 2)
        self.assertNotIn("\ufffd", output)
        self.assertNotIn("— binary", output)

    def test_commit_diff_reports_statuses_binary_and_safe_output(self):
        output = export_git(self.repo, self.first, self.second)

        self.assertIn("initial", output)
        self.assertIn("second", output)
        self.assertIn(self.first[:7], output)
        self.assertIn(self.second[:7], output)
        self.assertIn("added-추가.txt` — added", output)
        self.assertIn("remove.txt` — deleted", output)
        self.assertIn("old name.txt → new name.txt` — renamed", output)
        self.assertIn("binary.bin` — binary", output)
        self.assertIn("Binary files are listed above", output)
        self.assertIn("Lines added: 2", output)
        self.assertIn("Lines removed: 1", output)

    def test_working_tree_and_staged_modes(self):
        (self.repo / "keep.txt").write_text("one\nworking\n", encoding="utf-8")
        working = export_git(self.repo, working_tree=True)
        self.assertIn("working tree vs HEAD", working)
        self.assertIn("+working", working)

        self._git("add", "keep.txt")
        staged = export_git(self.repo, staged=True)
        self.assertIn("staged changes vs HEAD", staged)
        self.assertIn("+working", staged)

    def test_working_tree_includes_staged_and_unstaged_while_staged_does_not(self):
        (self.repo / "keep.txt").write_text("staged\n", encoding="utf-8")
        self._git("add", "keep.txt")
        (self.repo / "added-추가.txt").write_text("unstaged\n", encoding="utf-8")
        (self.repo / "untracked.txt").write_text("untracked\n", encoding="utf-8")

        working = export_git(self.repo, working_tree=True)
        staged = export_git(self.repo, staged=True)
        self.assertIn("keep.txt` — modified", working)
        self.assertIn("+staged", working)
        self.assertIn("added-추가.txt` — modified", working)
        self.assertIn("+unstaged", working)
        self.assertIn("Lines added: 3", working)
        self.assertIn("keep.txt` — modified", staged)
        self.assertNotIn("added-추가.txt", staged)
        self.assertNotIn("untracked.txt", staged)

    def test_working_tree_combines_staged_and_later_edits_against_head(self):
        (self.repo / "keep.txt").write_text("one\ntwo\nstaged\n", encoding="utf-8")
        self._git("add", "keep.txt")
        (self.repo / "keep.txt").write_text("one\ntwo\nstaged\nlater\n", encoding="utf-8")
        working = export_git(self.repo, working_tree=True)
        self.assertIn("+staged", working)
        self.assertIn("+later", working)
        self.assertIn("Lines added: 2", working)

    def test_path_filter_does_not_interpret_git_options(self):
        (self.repo / "keep.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "added-추가.txt").write_text("changed\n", encoding="utf-8")
        (self.repo / "새 tracked.txt").write_text("added\n", encoding="utf-8")
        self._git("add", "새 tracked.txt")
        pwned = Path(self.temporary.name) / "pwned.txt"
        export_git(self.repo, working_tree=True, paths=["--output=" + str(pwned)])
        self.assertFalse(pwned.exists())
        filtered = export_git(self.repo, working_tree=True, paths=["keep.txt"])
        self.assertIn("keep.txt` — modified", filtered)
        self.assertNotIn("added-추가.txt", filtered)
        filtered = export_git(self.repo, working_tree=True, paths=["새 tracked.txt"])
        self.assertIn("새 tracked.txt` — added", filtered)
        self.assertNotIn("keep.txt", filtered)

    def test_untracked_files_are_filtered_limited_and_leave_index_unchanged(self):
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (self.repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        (self.repo / "새 file.txt").write_text("first\nsecond\n", encoding="utf-8")
        (self.repo / "binary-new.bin").write_bytes(b"binary\x00data")
        (self.repo / "big.txt").write_bytes(b"x" * (1024 * 1024 + 1))
        (self.repo / "keep.txt").write_text("staged\n", encoding="utf-8")
        self._git("add", "keep.txt")
        status_before = self._git("status", "--porcelain")
        index_before = self._git("diff", "--cached")

        output = export_git(self.repo, working_tree=True)
        self.assertIn("새 file.txt` — added (untracked)", output)
        self.assertIn("--- /dev/null\n+++ b/새 file.txt", output)
        self.assertIn("+first\n+second", output.replace("\r\n", "\n"))
        self.assertIn("binary-new.bin` — binary", output)
        self.assertNotIn("## binary-new.bin", output)
        self.assertIn("big.txt` — omitted (too large)", output)
        self.assertNotIn("## big.txt", output)
        self.assertNotIn("`ignored.txt`", output)
        self.assertNotIn("## ignored.txt", output)
        self.assertEqual(self._git("status", "--porcelain"), status_before)
        self.assertEqual(self._git("diff", "--cached"), index_before)
        filtered = export_git(self.repo, working_tree=True, paths=["새 file.txt"])
        self.assertIn("Lines added: 2", filtered)
        self.assertIn("새 file.txt` — added (untracked)", filtered)
        self.assertNotIn("big.txt", filtered)
        excluded = export_git(self.repo, working_tree=True, exclude=["새*"])
        self.assertIn("Excluded from this export: `새 file.txt`", excluded)
        self.assertNotIn("## 새 file.txt", excluded)

    def test_untracked_size_limit_includes_exactly_one_mib(self):
        (self.repo / "limit.txt").write_bytes(b"x" * (1024 * 1024))
        changes = collect_git(self.repo, working_tree=True).changes
        self.assertEqual(changes[0].status, "added (untracked)")
        self.assertEqual(changes[0].added, 1)

    def test_untracked_symlink_is_skipped(self):
        link = self.repo / "link.txt"
        try:
            link.symlink_to(self.repo / "keep.txt")
        except OSError as exc:
            self.skipTest("Cannot create symlink: {}".format(exc))
        output = export_git(self.repo, working_tree=True)
        self.assertNotIn("`link.txt`", output)

    def test_untracked_non_regular_entry_is_skipped(self):
        path = self.repo / "not-regular.txt"
        path.write_text("content\n", encoding="utf-8")
        original_lstat = Path.lstat

        def fake_lstat(candidate):
            if candidate == path:
                return os.stat_result((stat.S_IFLNK,) + (0,) * 9)
            return original_lstat(candidate)

        with patch.object(Path, "lstat", fake_lstat):
            output = export_git(self.repo, working_tree=True)
        self.assertNotIn("`not-regular.txt`", output)

    def test_git_cli_working_tree_includes_staged_and_unstaged(self):
        (self.repo / "keep.txt").write_text("staged\n", encoding="utf-8")
        self._git("add", "keep.txt")
        (self.repo / "new name.txt").write_text("unstaged\n", encoding="utf-8")
        output_path = Path(self.temporary.name) / "result.md"
        subprocess.check_call([
            sys.executable, "-m", "llm_diff_exporter", "git", str(self.repo),
            "--working-tree", "-o", str(output_path),
        ])
        output = output_path.read_text(encoding="utf-8")
        self.assertEqual(output, export_git(self.repo, working_tree=True))

    def test_git_cli_ref_comparison_matches_export(self):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        output = subprocess.check_output([
            sys.executable, "-m", "llm_diff_exporter", "git", str(self.repo),
            self.first, self.second,
        ], encoding="utf-8", env=environment)
        self.assertEqual(output, export_git(self.repo, self.first, self.second))


if __name__ == "__main__":
    unittest.main()
