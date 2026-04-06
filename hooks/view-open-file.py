#!/usr/bin/env python3
"""Claude Code PostToolUse hook: render all edited/written files in a single cmux browser tab.

On each Edit/Write:
1. Appends the edit info (file, new_string) to a session changes log
2. Renders a combined HTML page with file tree sidebar + collapsible diff sections
3. Navigates the existing browser tab (or creates one) to the combined page
"""
import json, sys, os, subprocess, fcntl, re, html
from collections import defaultdict

data = json.load(sys.stdin)
session_id = data.get("session_id", "default")
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

if not file_path or not os.path.isfile(file_path):
    sys.exit(0)

# --- Record this edit ---
changes_dir = os.path.expanduser("~/.claude/view-changes")
os.makedirs(changes_dir, exist_ok=True)
changes_file = os.path.join(changes_dir, f"{session_id}.jsonl")

new_string = ""
old_string = ""
if tool_name == "Edit":
    new_string = tool_input.get("new_string", "")
    old_string = tool_input.get("old_string", "")

entry = json.dumps({
    "file": file_path,
    "tool": tool_name,
    "new_string": new_string,
    "old_string": old_string,
})
with open(changes_file, "a") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.write(entry + "\n")

# --- Load all changes for this session ---
changes = []
with open(changes_file, "r") as f:
    for line in f:
        line = line.strip()
        if line:
            changes.append(json.loads(line))

# --- Group by file, keeping edit pairs per file ---
file_order = []
file_edits = {}  # file -> list of (old_string, new_string) tuples
for c in changes:
    fp = c["file"]
    if fp not in file_edits:
        file_order.append(fp)
        file_edits[fp] = []
    ns = c.get("new_string", "")
    os_ = c.get("old_string", "")
    if ns or os_:
        file_edits[fp].append((os_, ns))

# --- Find project root (use cwd, which is where Claude Code runs) ---
cwd = os.getcwd()
try:
    git_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=5,
        cwd=cwd,
    ).stdout.strip()
except Exception:
    git_root = ""

if not git_root:
    git_root = cwd

# --- Build file tree from git ls-files ---
all_files = set()
try:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, timeout=5,
        cwd=git_root,
    )
    if result.returncode == 0:
        for f in result.stdout.strip().split("\n"):
            if f:
                all_files.add(os.path.join(git_root, f))
except Exception:
    pass

# --- Detect git status for each changed file ---
file_status = {}  # file -> "N" (new/untracked), "M" (modified), "W" (written/overwrite)
for fp in file_order:
    rel = os.path.relpath(fp, git_root) if fp.startswith(git_root + "/") else None
    if rel:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--", rel],
                capture_output=True, text=True, timeout=5, cwd=git_root,
            )
            status_line = result.stdout.strip()
            if status_line.startswith("??") or status_line.startswith("A"):
                file_status[fp] = "N"
            elif status_line:
                file_status[fp] = "M"
            else:
                file_status[fp] = "M"  # changed in session but committed state matches
        except Exception:
            file_status[fp] = "M"
    else:
        file_status[fp] = "M"

    # Override: Write tool with no edit pairs = new file or full overwrite
    tools_used = [c["tool"] for c in changes if c["file"] == fp]
    if tools_used == ["Write"] and not file_edits.get(fp):
        file_status[fp] = "N" if file_status.get(fp) == "N" else "W"

# Split changed files into in-project and external
changed_set = set(file_order)
external_files = []
for fp in file_order:
    if fp.startswith(git_root + "/"):
        all_files.add(fp)
    else:
        external_files.append(fp)

# Build tree structure: nested dict
def build_tree(files, root):
    tree = {}
    for fp in sorted(files):
        rel = os.path.relpath(fp, root)
        if rel.startswith(".."):
            continue  # skip files outside root
        parts = rel.split(os.sep)
        node = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node.setdefault(part, {"__file__": fp})
            else:
                node.setdefault(part, {})
                node = node[part]
    return tree

tree = build_tree(all_files, git_root)
project_name = os.path.basename(git_root)

# Add external files under a virtual "~ external" group
if external_files:
    ext_group = {}
    for fp in external_files:
        # Show path relative to home for readability
        home = os.path.expanduser("~")
        if fp.startswith(home):
            rel = fp[len(home) + 1:]
        else:
            rel = fp
        parts = rel.split(os.sep)
        node = ext_group
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node.setdefault(part, {"__file__": fp})
            else:
                node.setdefault(part, {})
                node = node[part]
    tree["~"] = ext_group

def render_tree(node, depth=0):
    """Render tree as HTML list items."""
    lines = []
    # Sort: directories first, then files
    dirs = sorted([k for k, v in node.items() if "__file__" not in v])
    files = sorted([k for k, v in node.items() if "__file__" in v])

    for d in dirs:
        lines.append(f'<li class="tree-dir"><span class="tree-toggle">{"  " * depth}{d}/</span>')
        lines.append('<ul class="tree-children">')
        lines.extend(render_tree(node[d], depth + 1))
        lines.append('</ul></li>')

    for fname in files:
        fp = node[fname]["__file__"]
        is_changed = fp in changed_set
        status = file_status.get(fp, "")
        if is_changed:
            status_cls = "tree-new" if status == "N" else "tree-changed"
            cls = f' class="{status_cls}"'
            badge = f'<span class="tree-badge tree-badge-{status.lower()}">{status}</span>' if status else ""
        else:
            cls = ""
            badge = ""
        idx = file_order.index(fp) if is_changed else -1
        click = f' onclick="openFile({idx})"' if is_changed else ""
        lines.append(f'<li{cls}{click}>{"  " * depth}{fname}{badge}</li>')

    return lines

tree_html = "\n".join(["<ul class='tree-root'>"] + render_tree(tree) + ["</ul>"])

# --- Build combined HTML ---
CSS = """
:root {
  --bg: #fff; --fg: #1d1d1f; --fg-muted: #6e6e73;
  --surface: #f5f5f7; --border: #d2d2d7;
  --link: #0066cc;
  --diff-bg: #d4edda; --diff-border: #28a745; --diff-fg: #155724;
  --del-bg: #f8d7da; --del-border: #dc3545; --del-fg: #721c24;
  --mod-fg: #856404; --mod-bg: #fff3cd;
  --hover: #fafafa;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1e1e1e; --fg: #d4d4d4; --fg-muted: #858585;
    --surface: #252526; --border: #3c3c3c;
    --link: #4da3ff;
    --diff-bg: #1e3a2a; --diff-border: #2ea043; --diff-fg: #56d364;
    --del-bg: #3d1f28; --del-border: #f85149; --del-fg: #f85149;
    --mod-fg: #e3b341; --mod-bg: #3b2e00;
    --hover: #2a2d2e;
  }
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; color: var(--fg); background: var(--bg); display: flex; height: 100vh; overflow: hidden; }

/* --- Sidebar --- */
.sidebar { width: 260px; min-width: 200px; background: var(--surface); border-right: 1px solid var(--border); overflow-y: auto; padding: 0.5rem 0; font-size: 0.8em; font-family: monospace; flex-shrink: 0; }
.sidebar-header { padding: 0.5rem 0.75rem; font-weight: 600; font-size: 0.9em; color: var(--fg); border-bottom: 1px solid var(--border); margin-bottom: 0.25rem; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.tree-root, .tree-root ul { list-style: none; padding-left: 0; }
.tree-root li { padding: 0.15rem 0.75rem; cursor: default; white-space: nowrap; color: var(--fg-muted); }
.tree-root li.tree-changed { color: var(--mod-fg); font-weight: 600; cursor: pointer; }
.tree-root li.tree-changed:hover { background: var(--mod-bg); }
.tree-root li.tree-new { color: var(--diff-fg); font-weight: 600; cursor: pointer; }
.tree-root li.tree-new:hover { background: var(--diff-bg); }
.tree-badge { font-size: 0.7em; padding: 0.05rem 0.3rem; border-radius: 3px; margin-left: 0.4rem; font-weight: 700; }
.tree-badge-n { background: var(--diff-bg); color: var(--diff-fg); }
.tree-badge-m { background: var(--mod-bg); color: var(--mod-fg); }
.tree-badge-w { background: var(--del-bg); color: var(--del-fg); }
.tree-dir > .tree-toggle { cursor: pointer; color: var(--fg); }
.tree-dir > .tree-toggle::before { content: "\\25B6 "; font-size: 0.65em; display: inline-block; transition: transform 0.15s; }
.tree-dir.open > .tree-toggle::before { transform: rotate(90deg); }
.tree-children { display: none; padding-left: 1rem; }
.tree-dir.open > .tree-children { display: block; }

/* --- Main content --- */
.main { flex: 1; overflow-y: auto; padding: 1.5rem 2rem; }
.main h1 { border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; font-size: 1.2em; margin-bottom: 1rem; }
details { margin-bottom: 0.5rem; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
details[open] { margin-bottom: 1rem; }
summary { font-size: 0.85em; color: var(--fg); padding: 0.5rem 0.75rem; font-family: monospace; cursor: pointer; background: var(--surface); user-select: none; list-style: none; display: flex; align-items: center; }
summary::-webkit-details-marker { display: none; }
summary::before { content: "\\25B6"; font-size: 0.7em; margin-right: 0.5rem; transition: transform 0.15s; }
details[open] > summary::before { transform: rotate(90deg); }
summary .count { padding: 0.1rem 0.4rem; border-radius: 3px; margin-left: auto; font-size: 0.85em; }
summary .count-n { background: var(--diff-bg); color: var(--diff-fg); }
summary .count-m { background: var(--mod-bg); color: var(--mod-fg); }
summary .count-w { background: var(--del-bg); color: var(--del-fg); }
summary .filepath { color: var(--fg-muted); margin-left: 0.25rem; }
.file-content { padding: 0.75rem; line-height: 1.6; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: 0.95em; }
th, td { border: 1px solid var(--border); padding: 0.5rem 0.75rem; text-align: left; }
th { background: var(--surface); font-weight: 600; }
tr:hover { background: var(--hover); }
code { background: var(--surface); padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.9em; }
pre { background: var(--surface); padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.85em; margin: 0; }
pre code { background: none; padding: 0; }
h2 { margin-top: 2rem; }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote { border-left: 3px solid var(--border); margin: 1rem 0; padding: 0.5rem 1rem; color: var(--fg-muted); }
hr { border: none; border-top: 1px solid var(--border); margin: 2rem 0; }
li { margin: 0.25rem 0; }
.diff-new { background: var(--diff-bg); border-left: 3px solid var(--diff-border); padding-left: 0.5rem; margin-left: -0.5rem; padding-right: 0.5rem; }
.diff-del { background: var(--del-bg); border-left: 3px solid var(--del-border); padding-left: 0.5rem; margin-left: -0.5rem; padding-right: 0.5rem; text-decoration: line-through; color: var(--del-fg); }
pre .diff-line { display: block; background: var(--diff-bg); border-left: 3px solid var(--diff-border); margin: 0 -1rem; padding: 0 1rem; }
pre .diff-del-line { display: block; background: var(--del-bg); border-left: 3px solid var(--del-border); margin: 0 -1rem; padding: 0 1rem; text-decoration: line-through; color: var(--del-fg); }
"""

JS = """
function openFile(idx) {
  const details = document.querySelectorAll('.main details');
  if (details[idx]) {
    details[idx].open = true;
    details[idx].scrollIntoView({block: 'start', behavior: 'smooth'});
  }
}
document.querySelectorAll('.tree-dir > .tree-toggle').forEach(el => {
  el.addEventListener('click', () => el.parentElement.classList.toggle('open'));
});
// Auto-expand directories containing changed files
document.querySelectorAll('.tree-changed, .tree-new').forEach(el => {
  let parent = el.parentElement;
  while (parent) {
    if (parent.classList && parent.classList.contains('tree-dir')) {
      parent.classList.add('open');
    }
    parent = parent.parentElement;
  }
});
"""

parts = []
parts.append('<!DOCTYPE html><html><head><meta charset="utf-8">')
parts.append(f'<style>{CSS}</style>')
parts.append(f'<title>Changes ({len(file_order)} files)</title></head><body>')

# --- Sidebar ---
parts.append('<div class="sidebar">')
parts.append(f'<div class="sidebar-header">{html.escape(project_name)}</div>')
parts.append(tree_html)
parts.append('</div>')

# --- Main content ---
parts.append('<div class="main">')
total_edits = len(changes)
parts.append(f'<h1>Changes &mdash; {total_edits} edit{"s" if total_edits != 1 else ""} across {len(file_order)} file{"s" if len(file_order) != 1 else ""}</h1>')

# --- Render each file ---
for fp in file_order:
    ext = fp.rsplit(".", 1)[-1] if "." in fp else ""
    basename = os.path.basename(fp)
    edit_strings = file_edits[fp]
    edit_count = len(edit_strings)

    if not os.path.isfile(fp):
        continue

    with open(fp, "r") as f:
        content = f.read()

    rel_path = os.path.relpath(os.path.dirname(fp), git_root)
    if rel_path == ".":
        rel_path = ""
    else:
        rel_path += "/"

    status = file_status.get(fp, "M")
    status_labels = {"N": "new file", "M": "modified", "W": "overwritten"}
    status_label = status_labels.get(status, "modified")
    count_text = f'{edit_count} edit{"s" if edit_count != 1 else ""}' if edit_strings else status_label
    count_cls = f"count count-{status.lower()}"
    count_badge = f'<span class="{count_cls}">{count_text}</span>'
    parts.append(f'<details>')
    parts.append(f'<summary><strong>{basename}</strong><span class="filepath">{rel_path}</span>{count_badge}</summary>')
    parts.append('<div class="file-content">')

    is_new_file = status == "N"

    if ext == "md":
        md_content = content
        if md_content.startswith("---\n"):
            end = md_content.find("\n---\n", 4)
            if end != -1:
                md_content = md_content[end + 5:]

        if is_new_file:
            # New file: wrap entire content in green
            md_content = f'<div class="diff-new">\n\n{md_content}\n\n</div>'
        else:
            for old_s, new_s in edit_strings:
                new_stripped = new_s.rstrip("\n")
                old_stripped = old_s.rstrip("\n")
                if new_stripped and new_stripped in md_content:
                    del_block = f'<div class="diff-del">\n\n{old_stripped}\n\n</div>\n' if old_stripped else ""
                    md_content = md_content.replace(
                        new_stripped,
                        f'{del_block}<div class="diff-new">\n\n{new_stripped}\n\n</div>',
                        1,
                    )

        try:
            result = subprocess.run(
                ["node", "-e",
                 "const {marked}=require('marked');"
                 "marked.setOptions({gfm:true});"
                 "let md='';process.stdin.on('data',d=>md+=d);"
                 "process.stdin.on('end',()=>process.stdout.write(marked.parse(md)));"],
                input=md_content, capture_output=True, text=True, timeout=10,
                env={**os.environ, "NODE_PATH": subprocess.run(
                    ["npm", "root", "-g"], capture_output=True, text=True
                ).stdout.strip()},
            )
            rendered = result.stdout if result.returncode == 0 else html.escape(md_content)
        except Exception:
            rendered = html.escape(md_content)

        parts.append(rendered)
    else:
        lines = content.split("\n")

        if is_new_file:
            # New file: all lines green
            code_lines = [f'<span class="diff-line">{html.escape(l)}</span>' for l in lines]
        else:
            highlight_lines = set()  # green (new)
            deleted_blocks = []  # (insert_before_line, [old_lines])
            for old_s, new_s in edit_strings:
                new_stripped = new_s.rstrip("\n")
                old_stripped = old_s.rstrip("\n")
                if new_stripped:
                    new_lines = new_stripped.split("\n")
                    file_lines = [l.rstrip("\n") for l in lines]
                    for i in range(len(file_lines) - len(new_lines) + 1):
                        if file_lines[i : i + len(new_lines)] == new_lines:
                            highlight_lines.update(range(i, i + len(new_lines)))
                            if old_stripped:
                                deleted_blocks.append((i, old_stripped.split("\n")))
                            break

            del_before = {}
            for insert_at, old_lines in deleted_blocks:
                del_before[insert_at] = old_lines

            code_lines = []
            for i, line in enumerate(lines):
                if i in del_before:
                    for dl in del_before[i]:
                        code_lines.append(f'<span class="diff-del-line">{html.escape(dl)}</span>')
                escaped = html.escape(line)
                if i in highlight_lines:
                    code_lines.append(f'<span class="diff-line">{escaped}</span>')
                else:
                    code_lines.append(escaped)

        parts.append(f'<pre><code>{chr(10).join(code_lines)}</code></pre>')

    parts.append("</div></details>")

parts.append('</div>')  # close .main

parts.append(f'<script>{JS}</script>')
parts.append("</body></html>")

# --- Write combined HTML ---
out_file = f"/tmp/view-changes-{session_id}.html"
with open(out_file, "w") as f:
    f.write("\n".join(parts))

url = f"file://{out_file}"

# --- Navigate or create browser tab ---
tracking_dir = os.path.expanduser("~/.claude/view-surfaces")
os.makedirs(tracking_dir, exist_ok=True)
tracking_file = os.path.join(tracking_dir, f"{session_id}.txt")

reuse_surface = ""
if os.path.isfile(tracking_file):
    with open(tracking_file, "r") as f:
        lines = [l.strip() for l in f if l.strip()]
    if lines:
        reuse_surface = lines[-1]

navigated = False
if reuse_surface:
    try:
        result = subprocess.run(
            ["cmux", "browser", "--surface", reuse_surface, "navigate", url],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            navigated = True
    except Exception:
        pass

if not navigated:
    try:
        env = os.environ.copy()
        env["VIEW_REUSE_SURFACE"] = ""
        result = subprocess.run(
            ["viewtab", out_file],
            env=env, capture_output=True, text=True, timeout=15,
        )
        output = result.stdout.strip()
        surface_match = re.search(r"surface:(\d+)", output)
        if surface_match:
            surface_ref = f"surface:{surface_match.group(1)}"
            with open(tracking_file, "w") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                f.write(surface_ref + "\n")
    except Exception:
        pass
