import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from llm_diff_exporter import export_files, export_git


class ExportFilesTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
