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

# --- File type icons ---
FILE_ICONS = {
    "py": "🐍", "js": "📜", "ts": "📘", "jsx": "⚛", "tsx": "⚛",
    "md": "📝", "json": "📋", "yaml": "📋", "yml": "📋", "toml": "📋",
    "sh": "⚙", "bash": "⚙", "zsh": "⚙",
    "html": "🌐", "css": "🎨", "svg": "🎨",
    "rs": "🦀", "go": "🐹", "rb": "💎", "java": "☕",
    "c": "🔧", "cpp": "🔧", "h": "🔧",
    "txt": "📄", "csv": "📊", "sql": "🗃",
    "hjson": "📋", "xml": "📋",
    "png": "🖼", "jpg": "🖼", "gif": "🖼", "webp": "🖼",
    "lock": "🔒", "env": "🔒",
}
DIR_ICON = "📁"
DIR_OPEN_ICON = "📂"

def get_icon(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return FILE_ICONS.get(ext, "📄")

all_tree_files = []  # non-edited files clicked in explorer

def render_tree(node, depth=0):
    """Render tree as HTML list items with icons and indent guides."""
    lines = []
    dirs = sorted([k for k, v in node.items() if "__file__" not in v])
    files = sorted([k for k, v in node.items() if "__file__" in v])

    indent = depth * 12  # px

    for d in dirs:
        lines.append(f'<li class="tree-dir" style="padding-left:{indent}px">')
        lines.append(f'<span class="tree-toggle"><span class="tree-arrow"></span><span class="tree-icon dir-icon">{DIR_ICON}</span>{html.escape(d)}</span>')
        lines.append('<ul class="tree-children">')
        lines.extend(render_tree(node[d], depth + 1))
        lines.append('</ul></li>')

    for fname in files:
        fp = node[fname]["__file__"]
        is_changed = fp in changed_set
        status = file_status.get(fp, "")
        icon = get_icon(fname)
        if is_changed:
            status_cls = "tree-new" if status == "N" else "tree-changed"
            cls = f' class="{status_cls}"'
            badge = f'<span class="tree-badge tree-badge-{status.lower()}">{status}</span>'
            idx = file_order.index(fp)
            click = f' onclick="event.stopPropagation();openFile({idx})"'
        else:
            cls = ""
            badge = ""
            # Non-edited files: assign an index offset after edited files
            all_tree_files.append(fp)
            viewer_idx = len(file_order) + len(all_tree_files) - 1
            click = f' onclick="event.stopPropagation();openViewer({viewer_idx})"'
        lines.append(f'<li{cls}{click} style="padding-left:{indent + 14}px"><span class="tree-icon">{icon}</span>{html.escape(fname)}{badge}</li>')

    return lines

tree_html = "\n".join(["<ul class='tree-root'>"] + render_tree(tree) + ["</ul>"])

# --- Changes section (grouped by status) ---
changes_section_items = []
# New files first, then modified
new_files = [(fp, i) for i, fp in enumerate(file_order) if file_status.get(fp) == "N"]
mod_files = [(fp, i) for i, fp in enumerate(file_order) if file_status.get(fp) != "N"]

for label, file_list, badge_cls in [("New", new_files, "tree-badge-n"), ("Modified", mod_files, "tree-badge-m")]:
    if not file_list:
        continue
    for fp, idx in file_list:
        basename = os.path.basename(fp)
        icon = get_icon(basename)
        home = os.path.expanduser("~")
        if fp.startswith(git_root + "/"):
            rel = os.path.relpath(fp, git_root)
        elif fp.startswith(home):
            rel = "~/" + fp[len(home) + 1:]
        else:
            rel = fp
        dirname = os.path.dirname(rel)
        dir_hint = f'<span class="changes-dir">{dirname}/</span>' if dirname and dirname != "." else ""
        status = file_status.get(fp, "M")
        changes_section_items.append(
            f'<li class="changes-item" onclick="openFile({idx})">'
            f'<span class="tree-icon">{icon}</span>{html.escape(basename)}{dir_hint}'
            f'<span class="tree-badge {badge_cls}">{status}</span></li>'
        )

changes_html = "\n".join(changes_section_items)

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
.sidebar { width: 260px; min-width: 200px; background: var(--surface); border-right: 1px solid var(--border); overflow-y: auto; font-size: 13px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; flex-shrink: 0; }
.sidebar-header { padding: 6px 10px; font-weight: 600; font-size: 11px; color: var(--fg-muted); text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }
.sidebar-path { font-size: 10px; font-weight: 400; text-transform: none; letter-spacing: 0; color: var(--fg-muted); opacity: 0.7; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Section headers */
.section-header { padding: 4px 4px 4px 10px; font-weight: 600; font-size: 11px; color: var(--fg-muted); text-transform: uppercase; letter-spacing: 0.5px; border-top: 1px solid var(--border); cursor: pointer; user-select: none; display: flex; align-items: center; line-height: 1.4; }
.section-header .section-arrow { display: inline-block; font-size: 8px; margin-right: 4px; transition: transform 0.15s; }
.section-header.collapsed .section-arrow { transform: rotate(-90deg); }
.section-content { }
.section-header.collapsed + .section-content { display: none; }
.section-count { margin-left: auto; font-weight: 400; opacity: 0.7; }

/* Changes list */
.changes-list { list-style: none; padding: 0; margin: 0; }
.changes-item { padding: 2px 6px 2px 10px; margin: 0; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; color: var(--fg); line-height: 1.6; }
.changes-item:hover { background: var(--hover); }
.changes-dir { color: var(--fg-muted); margin-left: 4px; font-size: 0.85em; }

/* Tree */
.tree-root, .tree-root ul { list-style: none; padding-left: 0; margin: 0; }
.tree-root li { padding: 1px 0; margin: 0; cursor: default; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--fg-muted); display: flex; align-items: center; line-height: 1.6; }
.tree-root li:not(.tree-dir) { cursor: pointer; }
.tree-root li:not(.tree-dir):hover { background: var(--hover); }
.tree-root li.tree-active { background: var(--border); }
.tree-root li.tree-changed { color: var(--mod-fg); cursor: pointer; }
.tree-root li.tree-new { color: var(--diff-fg); cursor: pointer; }
.tree-icon { margin-right: 3px; flex-shrink: 0; }
.tree-badge { font-size: 10px; padding: 0 4px; border-radius: 3px; margin-left: auto; font-weight: 600; flex-shrink: 0; margin-right: 6px; }
.tree-badge-n { background: var(--diff-bg); color: var(--diff-fg); }
.tree-badge-m { background: var(--mod-bg); color: var(--mod-fg); }
.tree-badge-w { background: var(--del-bg); color: var(--del-fg); }
.tree-root li.tree-dir { flex-direction: column; align-items: stretch; }
.tree-dir > .tree-toggle { cursor: pointer; color: var(--fg); display: flex; align-items: center; padding: 1px 0; }
.tree-dir > .tree-toggle:hover { background: var(--hover); }
.tree-arrow { display: inline-block; width: 0; height: 0; border-top: 4px solid transparent; border-bottom: 4px solid transparent; border-left: 5px solid var(--fg-muted); margin-right: 3px; transition: transform 0.1s; flex-shrink: 0; }
.tree-dir.open > .tree-toggle .tree-arrow { transform: rotate(90deg); }
.tree-children { display: none; }
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
pre code { background: none; padding: 0; counter-reset: line; }
pre:not(.line-numbers) code .line { counter-increment: line; }
pre:not(.line-numbers) code .line::before { content: counter(line); display: inline-block; width: 3em; margin-right: 1em; text-align: right; color: var(--fg-muted); opacity: 0.5; user-select: none; }
pre.line-numbers { background: var(--surface) !important; }
pre.line-numbers code { color: var(--fg); }
h2 { margin-top: 2rem; }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
blockquote { border-left: 3px solid var(--border); margin: 1rem 0; padding: 0.5rem 1rem; color: var(--fg-muted); }
hr { border: none; border-top: 1px solid var(--border); margin: 2rem 0; }
li { margin: 0.25rem 0; }
.viewer-section { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; margin-bottom: 1rem; }
.viewer-header { font-size: 0.85em; padding: 0.5rem 0.75rem; font-family: monospace; background: var(--surface); border-bottom: 1px solid var(--border); display: flex; align-items: center; }
.viewer-close { margin-left: auto; cursor: pointer; color: var(--fg-muted); font-size: 1.1em; padding: 0 4px; border-radius: 3px; }
.viewer-close:hover { background: var(--hover); color: var(--fg); }
.viewer-header .filepath { color: var(--fg-muted); margin-left: 0.25rem; }
.diff-new { background: var(--diff-bg); border-left: 3px solid var(--diff-border); padding-left: 0.5rem; margin-left: -0.5rem; padding-right: 0.5rem; }
.diff-del { background: var(--del-bg); border-left: 3px solid var(--del-border); padding-left: 0.5rem; margin-left: -0.5rem; padding-right: 0.5rem; text-decoration: line-through; color: var(--del-fg); }
pre code .line { display: block; }
pre code .line:hover { background: var(--hover); }
pre .diff-line { background: var(--diff-bg); border-left: 3px solid var(--diff-border); margin: 0 -1rem; padding: 0 1rem; }
pre .diff-line:hover { background: var(--diff-bg); filter: brightness(0.95); }
pre .diff-del-line { background: var(--del-bg); border-left: 3px solid var(--del-border); margin: 0 -1rem; padding: 0 1rem; text-decoration: line-through; color: var(--del-fg); }
pre .diff-del-line:hover { filter: brightness(0.95); }
.line-skip { display: block; text-align: center; color: var(--fg-muted); font-size: 0.85em; padding: 2px 0; opacity: 0.6; cursor: pointer; user-select: none; }
.line-skip:hover { opacity: 1; background: var(--hover); }
.diff-toggle { font-size: 11px; padding: 2px 8px; border-radius: 3px; border: 1px solid var(--border); background: var(--surface); color: var(--fg-muted); cursor: pointer; margin-left: 8px; }
.diff-toggle:hover { background: var(--hover); color: var(--fg); }
"""

JS = """
function openFile(idx) {
  const details = document.querySelectorAll('.main details:not(.viewer-section)');
  if (details[idx]) {
    details[idx].open = true;
    details[idx].scrollIntoView({block: 'start', behavior: 'smooth'});
  }
  // Highlight in nav
  clearActiveNav();
  const items = document.querySelectorAll('[onclick*="openFile(' + idx + ')"]');
  items.forEach(el => el.classList.add('tree-active'));
}
// Tree directory toggles
document.querySelectorAll('.tree-dir > .tree-toggle').forEach(el => {
  el.addEventListener('click', () => el.parentElement.classList.toggle('open'));
});
// Sync nav highlight when collapsible is toggled directly
document.querySelectorAll('.main details:not(.viewer-section)').forEach((det, idx) => {
  det.addEventListener('toggle', () => {
    const navItems = document.querySelectorAll('[onclick*="openFile(' + idx + ')"]');
    if (det.open) {
      clearActiveNav();
      navItems.forEach(el => el.classList.add('tree-active'));
    } else {
      navItems.forEach(el => el.classList.remove('tree-active'));
    }
  });
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
function toggleFullFile(idx) {
  const collapsed = document.getElementById('diff-collapsed-' + idx);
  const full = document.getElementById('diff-full-' + idx);
  if (!collapsed || !full) return;
  const btn = document.querySelector('[onclick*="toggleFullFile(' + idx + ')"]');
  if (full.style.display === 'none') {
    collapsed.style.display = 'none';
    full.style.display = '';
    if (btn) btn.textContent = 'changes only';
  } else {
    collapsed.style.display = '';
    full.style.display = 'none';
    if (btn) btn.textContent = 'full file';
  }
}
function clearActiveNav() {
  document.querySelectorAll('.tree-active').forEach(el => el.classList.remove('tree-active'));
}
function openViewer(idx) {
  const viewer = document.getElementById('viewer-' + idx);
  if (!viewer) return;
  const wasVisible = viewer.style.display !== 'none';
  document.querySelectorAll('.viewer-section').forEach(el => el.style.display = 'none');
  clearActiveNav();
  if (!wasVisible) {
    viewer.style.display = '';
    viewer.scrollIntoView({block: 'start', behavior: 'smooth'});
    // Highlight the clicked nav item
    const item = document.querySelector('[onclick*="openViewer(' + idx + ')"]');
    if (item) item.classList.add('tree-active');
  }
}
"""

parts = []
parts.append('<!DOCTYPE html><html><head><meta charset="utf-8">')
parts.append('<link id="prism-light" rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" media="(prefers-color-scheme: light)" />')
parts.append('<link id="prism-dark" rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" media="(prefers-color-scheme: dark)" />')
parts.append(f'<style>{CSS}</style>')
parts.append(f'<title>Changes ({len(file_order)} files)</title></head><body>')

# --- Sidebar ---
parts.append('<div class="sidebar">')
home = os.path.expanduser("~")
if git_root.startswith(home):
    display_path = "~/" + os.path.relpath(git_root, home)
else:
    display_path = git_root
parts.append(f'<div class="sidebar-header">{html.escape(project_name)}<div class="sidebar-path">{html.escape(display_path)}</div></div>')

# Changes section
parts.append(f'<div class="section-header" onclick="this.classList.toggle(\'collapsed\')"><span class="section-arrow">▼</span>Changes<span class="section-count">{len(file_order)}</span></div>')
parts.append(f'<div class="section-content"><ul class="changes-list">{changes_html}</ul></div>')

# Explorer section (always open)
parts.append(f'<div class="section-header" onclick="this.classList.toggle(\'collapsed\')"><span class="section-arrow">▼</span>Explorer</div>')
parts.append(f'<div class="section-content">{tree_html}</div>')

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
    file_idx = file_order.index(fp)
    toggle_btn = f'<button class="diff-toggle" onclick="event.stopPropagation();toggleFullFile({file_idx})">full file</button>' if edit_strings and status != "N" else ""
    parts.append(f'<details open>')
    parts.append(f'<summary><strong>{basename}</strong><span class="filepath">{rel_path}</span>{toggle_btn}{count_badge}</summary>')
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
        file_idx = file_order.index(fp)
        # Map extension to Prism language class
        if is_new_file:
            code_lines = [f'<span class="line diff-line">{html.escape(l)}</span>' for l in lines]
            parts.append(f'<pre><code>{chr(10).join(code_lines)}</code></pre>')
        else:
            highlight_lines = set()
            deleted_blocks = []
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

            # Build all lines with diff markers
            all_code_lines = []
            all_types = []
            for i, line in enumerate(lines):
                if i in del_before:
                    for dl in del_before[i]:
                        all_code_lines.append(f'<span class="line diff-del-line">{html.escape(dl)}</span>')
                        all_types.append("del")
                escaped = html.escape(line)
                if i in highlight_lines:
                    all_code_lines.append(f'<span class="line diff-line">{escaped}</span>')
                    all_types.append("new")
                else:
                    all_code_lines.append(f'<span class="line">{escaped}</span>')
                    all_types.append("ctx")

            # Collapsed view: only changed lines + 3 lines context
            CONTEXT = 3
            important = set()
            for i, t in enumerate(all_types):
                if t in ("new", "del"):
                    for j in range(max(0, i - CONTEXT), min(len(all_types), i + CONTEXT + 1)):
                        important.add(j)

            collapsed_lines = []
            last_shown = -1
            for i, line_html in enumerate(all_code_lines):
                if i in important:
                    if last_shown >= 0 and i > last_shown + 1:
                        skipped = i - last_shown - 1
                        collapsed_lines.append(f'<span class="line-skip">--- {skipped} lines hidden ---</span>')
                    collapsed_lines.append(line_html)
                    last_shown = i
            if last_shown < len(all_code_lines) - 1:
                skipped = len(all_code_lines) - last_shown - 1
                collapsed_lines.append(f'<span class="line-skip">--- {skipped} lines hidden ---</span>')

            parts.append(f'<div id="diff-collapsed-{file_idx}"><pre><code>{chr(10).join(collapsed_lines)}</code></pre></div>')
            parts.append(f'<div id="diff-full-{file_idx}" style="display:none"><pre><code>{chr(10).join(all_code_lines)}</code></pre></div>')

    parts.append("</div></details>")

# --- Render non-edited files (hidden until clicked from explorer) ---
for i, fp in enumerate(all_tree_files):
    if not os.path.isfile(fp):
        continue
    viewer_idx = len(file_order) + i
    basename = os.path.basename(fp)
    ext = fp.rsplit(".", 1)[-1] if "." in fp else ""
    rel_path = os.path.relpath(fp, git_root) if fp.startswith(git_root + "/") else fp

    try:
        with open(fp, "r") as f:
            viewer_content = f.read()
    except Exception:
        continue

    dir_display = os.path.dirname(rel_path)
    dir_display = (dir_display + "/") if dir_display and dir_display != "." else ""
    parts.append(f'<div id="viewer-{viewer_idx}" class="viewer-section" style="display:none">')
    parts.append(f'<div class="viewer-header"><strong>{html.escape(basename)}</strong><span class="filepath">{html.escape(dir_display)}</span><span class="viewer-close" onclick="this.closest(\'.viewer-section\').style.display=\'none\';clearActiveNav()">&times;</span></div>')
    viewer_ext = fp.rsplit(".", 1)[-1].lower() if "." in fp else ""

    if viewer_ext == "md":
        # Render markdown as HTML
        md_content = viewer_content
        if md_content.startswith("---\n"):
            end = md_content.find("\n---\n", 4)
            if end != -1:
                md_content = md_content[end + 5:]
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
            rendered = result.stdout if result.returncode == 0 else f"<pre>{html.escape(md_content)}</pre>"
        except Exception:
            rendered = f"<pre>{html.escape(md_content)}</pre>"
        parts.append(f'<div class="file-content">{rendered}</div>')
    else:
        # Code file: Prism syntax highlighting
        viewer_lang_map = {"py": "python", "sh": "bash", "bash": "bash", "zsh": "bash",
                           "js": "javascript", "ts": "typescript", "json": "json",
                           "yaml": "yaml", "yml": "yaml", "toml": "toml",
                           "html": "markup", "css": "css", "go": "go", "rs": "rust",
                           "rb": "ruby", "java": "java", "c": "c", "cpp": "cpp",
                           "sql": "sql", "hjson": "json"}
        viewer_lang = viewer_lang_map.get(viewer_ext, "")
        if not viewer_lang:
            first_line = viewer_content.split("\n", 1)[0] if viewer_content else ""
            if first_line.startswith("#!"):
                shebang = first_line.lower()
                if "python" in shebang: viewer_lang = "python"
                elif "bash" in shebang or "/sh" in shebang: viewer_lang = "bash"
                elif "node" in shebang: viewer_lang = "javascript"
                elif "ruby" in shebang: viewer_lang = "ruby"
        viewer_lang_cls = f' class="language-{viewer_lang}"' if viewer_lang else ""
        escaped_content = html.escape(viewer_content)
        parts.append(f'<pre class="line-numbers"><code{viewer_lang_cls}>{escaped_content}</code></pre>')
    parts.append("</div>")

parts.append('</div>')  # close .main

parts.append(f'<script>{JS}</script>')
# Prism.js — only for viewer files (non-edited files opened from explorer)
parts.append('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css" />')
parts.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>')
parts.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>')
for lang in ["python", "bash", "javascript", "typescript", "json", "yaml", "toml", "markup", "css", "go", "rust", "java", "ruby", "sql", "c", "cpp"]:
    parts.append(f'<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-{lang}.min.js"></script>')
parts.append("</body></html>")

# --- Write combined HTML ---
out_file = f"/tmp/view-changes-{session_id}.html"
with open(out_file, "w") as f:
    f.write("\n".join(parts))

import time as _time
url = f"file://{out_file}?t={int(_time.time() * 1000)}"

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
