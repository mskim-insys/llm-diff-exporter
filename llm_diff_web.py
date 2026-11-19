"""Local web UI for llm_diff_exporter. Serves on 127.0.0.1 only; makes no outbound calls."""

from __future__ import annotations

import json
import re
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from llm_diff_exporter import (
    DEFAULT_EXCLUDES,
    Collected,
    DiffExportError,
    apply_exclusions,
    collect_files,
    collect_git,
    list_git_refs,
    render_collected,
)

HOST = "127.0.0.1"
MAX_BODY = 1024 * 1024


def clean_path(value: object) -> str:
    """Trim whitespace and the quotes Windows adds with 'Copy as path'."""
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1].strip()
    return text


def _existing(value: object, kind: str) -> Path:
    text = clean_path(value)
    if not text:
        raise DiffExportError("Please enter a {} path.".format(kind))
    path = Path(text).expanduser()
    if not path.exists():
        raise DiffExportError("Path does not exist: {}".format(path))
    if kind == "file" and not path.is_file():
        raise DiffExportError("Not a file: {}".format(path))
    if kind == "folder" and not path.is_dir():
        raise DiffExportError("Not a folder: {}".format(path))
    return path.resolve()


def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise DiffExportError("Context lines must be a whole number.")


def _lines(value: object) -> list:
    if isinstance(value, str):
        value = value.splitlines()
    return [str(v).strip() for v in (value or []) if str(v).strip()]


def collect(payload: dict) -> Collected:
    context = _int(payload.get("context", 3), 3)
    if payload.get("mode") == "files":
        return collect_files(
            _existing(payload.get("file_a"), "file"),
            _existing(payload.get("file_b"), "file"),
            context,
        )
    repo = _existing(payload.get("repo"), "folder")
    kind = payload.get("kind", "refs")
    paths = _lines(payload.get("paths"))
    if kind in ("working", "staged"):
        return collect_git(
            repo, context=context, paths=paths,
            staged=kind == "staged", working_tree=kind == "working",
        )
    ref_a = str(payload.get("ref_a", "")).strip()
    ref_b = str(payload.get("ref_b", "")).strip()
    if not ref_a or not ref_b:
        raise DiffExportError("Choose both refs (A and B).")
    return collect_git(repo, ref_a, ref_b, context, paths)


def check_output_dir(payload: dict, out_dir: str) -> Path:
    """Resolve the output folder; refuse folders inside the compared repository."""
    target = Path(clean_path(payload.get("out_dir")) or out_dir).expanduser().resolve()
    if payload.get("mode") != "files":
        repo = Path(clean_path(payload.get("repo"))).expanduser().resolve()
        if target == repo or repo in target.parents:
            raise DiffExportError(
                "The output folder is inside the compared repository; choose another folder."
            )
    if target.exists() and not target.is_dir():
        raise DiffExportError("Output path is not a folder: {}".format(target))
    return target


def _safe_name(text: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", text, flags=re.UNICODE).strip("_") or "diff"


def handle_api(name: str, payload: dict, out_dir: str) -> dict:
    """Run one API call. Raises DiffExportError for user-facing problems."""
    if name == "config":
        return {"out_dir": out_dir, "default_excludes": list(DEFAULT_EXCLUDES)}
    if name == "refs":
        return list_git_refs(_existing(payload.get("repo"), "folder"))

    collected = collect(payload)
    patterns = _lines(payload.get("exclude_patterns"))
    files = _lines(payload.get("exclude_files"))
    markdown = render_collected(collected, patterns, files)
    result = {"chars": len(markdown), "tokens": (len(markdown) + 3) // 4}
    if name == "preview":
        _, excluded = apply_exclusions(collected.changes, patterns, files)
        skipped = {c.path for c in excluded}
        result["files"] = [
            {
                "path": c.path, "status": c.status, "added": c.added,
                "removed": c.removed, "excluded": c.path in skipped,
            }
            for c in collected.changes
        ]
        return result
    if name == "export":
        target = check_output_dir(payload, out_dir)
        try:
            target.mkdir(parents=True, exist_ok=True)
            base = "diff_{}_{}".format(
                _safe_name(collected.label), datetime.now().date().isoformat()
            )
            destination = target / (base + ".md")
            counter = 2
            while destination.exists():
                destination = target / "{}_{}.md".format(base, counter)
                counter += 1
            with destination.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(markdown)
        except OSError as exc:
            raise DiffExportError("Cannot save to {}: {}".format(target, exc))
        result.update(
            filename=destination.name, saved_path=str(destination), content=markdown
        )
        return result
    raise DiffExportError("Unknown action: {}".format(name))


def make_handler(out_dir: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "llm-diff-exporter"

        def log_message(self, *args):
            pass

        def _allowed(self) -> bool:
            port = self.server.server_address[1]
            hosts = {"127.0.0.1:{}".format(port), "localhost:{}".format(port)}
            if self.headers.get("Host", "") not in hosts:
                return False
            origin = self.headers.get("Origin")
            return origin is None or origin in {"http://" + h for h in hosts}

        def _send(self, status: int, body: bytes, content_type: str):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, data: dict):
            self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            if not self._allowed():
                return self._json(403, {"error": "Forbidden host."})
            if self.path in ("/", "/index.html"):
                return self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            self._json(404, {"error": "Not found."})

        def do_POST(self):
            if not self._allowed():
                return self._json(403, {"error": "Forbidden host."})
            if not self.path.startswith("/api/"):
                return self._json(404, {"error": "Not found."})
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return self._json(415, {"error": "JSON required."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > MAX_BODY:
                    return self._json(413, {"error": "Request too large."})
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError
            except ValueError:
                return self._json(400, {"error": "Invalid JSON."})
            try:
                self._json(200, handle_api(self.path[5:], payload, out_dir))
            except DiffExportError as exc:
                self._json(400, {"error": str(exc)})
            except Exception as exc:  # keep the server alive on unexpected errors
                self._json(500, {"error": "Unexpected error: {}".format(exc)})

    return Handler


def create_server(port: int = 8765, out_dir: Optional[str] = None) -> ThreadingHTTPServer:
    default_out = str(Path(out_dir).resolve() if out_dir else (Path.cwd() / "out").resolve())
    return ThreadingHTTPServer((HOST, port), make_handler(default_out))


def serve(port: int = 8765, out_dir: Optional[str] = None, open_browser: bool = True) -> int:
    server = create_server(port, out_dir)
    url = "http://{}:{}/".format(HOST, server.server_address[1])
    print("llm-diff-exporter listening on {} (Ctrl+C to stop)".format(url))
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>LLM Diff Exporter</title>
<style>
body{font-family:sans-serif;max-width:60em;margin:1em auto;padding:0 1em}
fieldset{margin:.7em 0}label{display:block;margin:.3em 0}
input[type=text],textarea,select{width:100%;box-sizing:border-box}
#error{color:#b00;white-space:pre-wrap}#files label{font-family:monospace}
.ok{color:#060}
</style></head><body>
<h1>LLM Diff Exporter</h1>
<p>Local only (127.0.0.1). Inputs are read-only.</p>
<label><input type="radio" name="mode" value="git" checked> Git</label>
<label><input type="radio" name="mode" value="files"> Two files</label>

<div id="gitbox"><fieldset><legend>Git</legend>
<label>Repository folder <input type="text" id="repo" list="recent" placeholder="C:\\path\\to\\repo"></label>
<datalist id="recent"></datalist>
<button id="load">Load commits / branches</button>
<label>Compare
<select id="kind"><option value="refs">two refs (A to B)</option>
<option value="working">working tree vs HEAD</option>
<option value="staged">staged vs HEAD</option></select></label>
<div id="refbox">
<label>Ref A (older) <input type="text" id="ref_a" list="refs"></label>
<label>Ref B (newer) <input type="text" id="ref_b" list="refs"></label>
<datalist id="refs"></datalist>
<select id="pickA"><option value="">Pick recent commit for A...</option></select>
<select id="pickB"><option value="">Pick recent commit for B...</option></select>
</div>
<label>Limit to paths (one per line, optional) <textarea id="paths" rows="2"></textarea></label>
</fieldset></div>

<div id="filesbox" hidden><fieldset><legend>Files</legend>
<label>File A <input type="text" id="file_a"></label>
<label>File B <input type="text" id="file_b"></label></fieldset></div>

<fieldset><legend>Options</legend>
<label>Context lines <input type="text" id="context" value="3" size="3"></label>
<label>Exclude patterns (one glob per line) <textarea id="patterns" rows="5"></textarea></label>
<label>Output folder <input type="text" id="out_dir"></label></fieldset>

<button id="preview">Preview</button> <button id="export" disabled>Export (download + save)</button>
<p id="error"></p><p id="stale"></p><p id="size"></p><p id="saved" class="ok"></p>
<div id="files"></div>
<script>
const $ = id => document.getElementById(id);
const mode = () => document.querySelector('input[name=mode]:checked').value;
let previewGeneration = 0;
function markStale() {
  previewGeneration++;
  $('export').disabled = true;
  $('stale').textContent = 'Inputs changed: click Preview first';
}
async function api(name, body) {
  const r = await fetch('/api/' + name, {method: 'POST',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  const d = await r.json();
  if (!r.ok) throw new Error(d.error || r.statusText);
  return d;
}
function request(fresh) {
  const unchecked = [...document.querySelectorAll('#files input:not(:checked)')].map(e => e.value);
  return {mode: mode(), repo: $('repo').value, kind: $('kind').value,
    ref_a: $('ref_a').value, ref_b: $('ref_b').value, paths: $('paths').value,
    file_a: $('file_a').value, file_b: $('file_b').value, context: $('context').value,
    exclude_patterns: fresh ? $('patterns').value : '', exclude_files: fresh ? [] : unchecked,
    out_dir: $('out_dir').value};
}
function show(d) {
  $('size').textContent = 'Size: ' + d.chars + ' characters, ~' + d.tokens + ' tokens';
}
async function run(fn) {
  $('error').textContent = ''; $('saved').textContent = '';
  try { await fn(); } catch (e) { $('error').textContent = e.message; }
}
async function preview(fresh) {
  const generation = ++previewGeneration;
  if (fresh) $('export').disabled = true;
  const d = await api('preview', request(fresh));
  if (generation !== previewGeneration) return;
  show(d);
  if (fresh) {
    const box = $('files'); box.textContent = '';
    d.files.forEach(f => {
      const l = document.createElement('label'), c = document.createElement('input');
      c.type = 'checkbox'; c.value = f.path; c.checked = !f.excluded;
      c.onchange = () => { if (!$('export').disabled) run(() => preview(false)); };
      l.append(c, ' ' + f.path + ' [' + f.status + ', +' + f.added + ' -' + f.removed + ']');
      box.append(l);
    });
    $('stale').textContent = '';
    $('export').disabled = false;
  }
  if (mode() === 'git') remember($('repo').value);
}
function remember(p) {
  p = p.trim().replace(/^"|"$/g, ''); if (!p) return;
  const list = JSON.parse(localStorage.getItem('recentRepos') || '[]').filter(x => x !== p);
  list.unshift(p); localStorage.setItem('recentRepos', JSON.stringify(list.slice(0, 10)));
  fillRecent();
}
function fillRecent() {
  $('recent').textContent = '';
  JSON.parse(localStorage.getItem('recentRepos') || '[]').forEach(p => {
    const o = document.createElement('option'); o.value = p; $('recent').append(o);
  });
}
function sync() {
  $('gitbox').hidden = mode() !== 'git'; $('filesbox').hidden = mode() !== 'files';
  $('refbox').hidden = $('kind').value !== 'refs';
}
document.querySelectorAll('input[name=mode]').forEach(e => e.onchange = sync);
$('kind').onchange = sync;
document.querySelectorAll('input[name=mode], #kind, #repo, #ref_a, #ref_b, #paths, #file_a, #file_b, #context, #patterns')
  .forEach(e => { e.addEventListener('input', markStale); e.addEventListener('change', markStale); });
$('load').onclick = () => run(async () => {
  const d = await api('refs', {repo: $('repo').value});
  $('refs').textContent = '';
  [...d.branches, ...d.tags].forEach(n => {
    const o = document.createElement('option'); o.value = n; $('refs').append(o);
  });
  ['pickA', 'pickB'].forEach(id => {
    const s = $(id); s.length = 1;
    d.commits.forEach(c => {
      const o = document.createElement('option'); o.value = c.hash;
      o.textContent = c.short + ' ' + c.date + ' ' + c.subject; s.append(o);
    });
    s.onchange = () => {
      if (s.value) { $(id === 'pickA' ? 'ref_a' : 'ref_b').value = s.value; markStale(); }
    };
  });
  remember($('repo').value);
});
$('preview').onclick = () => run(() => preview(true));
$('export').onclick = () => run(async () => {
  const d = await api('export', request(false));
  show(d);
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([d.content], {type: 'text/markdown'}));
  a.download = d.filename; a.click();
  $('saved').textContent = 'Saved: ' + d.saved_path;
});
api('config', {}).then(c => {
  $('out_dir').value = c.out_dir; $('patterns').value = c.default_excludes.join('\\n');
});
fillRecent(); sync();
</script></body></html>
"""
