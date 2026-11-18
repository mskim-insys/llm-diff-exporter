import json
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from llm_diff_exporter import DiffExportError, export_files, export_git
from llm_diff_web import clean_path, create_server, handle_api


class ExcludeTests(unittest.TestCase):
    def test_pattern_excludes_file_and_is_noted(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "r"
            repo.mkdir()

            def git(*a):
                subprocess.check_call(["git"] + list(a), cwd=str(repo), stdout=subprocess.DEVNULL)

            git("init", "-q")
            git("config", "user.name", "T")
            git("config", "user.email", "t@example.invalid")
            (repo / "a.txt").write_text("1\n", encoding="utf-8")
            (repo / "uv.lock").write_text("1\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-qm", "one")
            (repo / "a.txt").write_text("2\n", encoding="utf-8")
            (repo / "uv.lock").write_text("2\n", encoding="utf-8")
            output = export_git(repo, working_tree=True, exclude=["*.lock"])
        self.assertIn("Files changed: 1", output)
        self.assertIn("Excluded from this export: `uv.lock`", output)


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.a = self.root / "a b.txt"
        self.b = self.root / "ß.txt"
        self.a.write_text("x\n", encoding="utf-8")
        self.b.write_text("y\n", encoding="utf-8")
        self.out = self.root / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_path_strips_quotes(self):
        self.assertEqual(clean_path('  "C:\\a b\\c.txt" '), "C:\\a b\\c.txt")

    def test_preview_and_export_save_copy_without_touching_inputs(self):
        payload = {"mode": "files", "file_a": '"%s"' % self.a, "file_b": str(self.b)}
        preview = handle_api("preview", payload, str(self.out))
        self.assertEqual(preview["tokens"], (preview["chars"] + 3) // 4)
        self.assertEqual(len(preview["files"]), 1)
        self.assertFalse(self.out.exists())

        result = handle_api("export", payload, str(self.out))
        saved = Path(result["saved_path"])
        self.assertEqual(saved.parent, self.out.resolve())
        self.assertEqual(saved.read_bytes().decode("utf-8"), result["content"])
        self.assertTrue(result["filename"].startswith("diff_a_b_"))
        again = handle_api("export", payload, str(self.out))
        self.assertNotEqual(again["saved_path"], result["saved_path"])
        self.assertEqual(self.a.read_bytes().replace(b"\r\n", b"\n"), b"x\n")

    def test_per_file_exclusion_changes_size(self):
        payload = {"mode": "files", "file_a": str(self.a), "file_b": str(self.b)}
        full = handle_api("preview", payload, str(self.out))
        payload["exclude_files"] = [full["files"][0]["path"]]
        reduced = handle_api("preview", payload, str(self.out))
        self.assertTrue(reduced["files"][0]["excluded"])
        self.assertNotEqual(reduced["chars"], full["chars"])

    def test_path_validation(self):
        with self.assertRaises(DiffExportError):
            handle_api("preview", {"mode": "files", "file_a": str(self.root), "file_b": str(self.b)}, "x")
        with self.assertRaises(DiffExportError):
            handle_api("preview", {"mode": "files", "file_a": str(self.root / "nope"), "file_b": str(self.b)}, "x")
        with self.assertRaises(DiffExportError):
            handle_api("refs", {"repo": str(self.a)}, "x")

    def test_output_folder_inside_repo_rejected(self):
        repo = self.root / "repo"
        repo.mkdir()
        subprocess.check_call(["git", "init", "-q"], cwd=str(repo))
        payload = {"mode": "git", "repo": str(repo), "kind": "working", "out_dir": str(repo / "out")}
        subprocess.check_call(["git", "config", "user.name", "T"], cwd=str(repo))
        subprocess.check_call(["git", "config", "user.email", "t@example.invalid"], cwd=str(repo))
        (repo / "f.txt").write_text("1\n", encoding="utf-8")
        subprocess.check_call(["git", "add", "."], cwd=str(repo))
        subprocess.check_call(["git", "commit", "-qm", "c"], cwd=str(repo), stdout=subprocess.DEVNULL)
        with self.assertRaises(DiffExportError):
            handle_api("export", payload, str(self.out))
        refs = handle_api("refs", {"repo": str(repo)}, str(self.out))
        self.assertEqual(refs["commits"][0]["subject"], "c")
        self.assertTrue(refs["branches"])


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, path, data=None, headers=None):
        req = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (self.port, path),
            data=None if data is None else json.dumps(data).encode(),
            headers=headers or {},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_serves_page_and_api(self):
        status, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"LLM Diff Exporter", body)
        status, body = self.request("/api/config", {}, {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        self.assertIn("default_excludes", json.loads(body))

    def test_rejects_foreign_host_origin_and_non_json(self):
        self.assertEqual(self.request("/", headers={"Host": "evil.example"})[0], 403)
        headers = {"Content-Type": "application/json", "Origin": "http://evil.example"}
        self.assertEqual(self.request("/api/config", {}, headers)[0], 403)
        self.assertEqual(self.request("/api/config", {}, {"Content-Type": "text/plain"})[0], 415)


if __name__ == "__main__":
    unittest.main()
