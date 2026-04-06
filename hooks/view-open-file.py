#!/usr/bin/env python3
"""PostToolUse hook: render all edited/written files in a single cmux browser tab.

On each Edit/Write:
1. Appends the edit info (file, new_string) to a session changes log
2. Renders a combined HTML page with file tree sidebar + collapsible diff sections
3. Navigates the existing browser tab (or creates one) to the combined page

Works with Claude Code, OpenCode, and any tool that pipes compatible JSON to stdin.
"""
import json, sys, os, subprocess, fcntl, re, html

# Import shared config (resolve through symlinks)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'lib'))
from common import VIEW_CHANGES_DIR, VIEW_SURFACES_DIR

# --- Shared helpers ---

LANG_MAP = {
    "py": "python", "sh": "bash", "bash": "bash", "zsh": "bash",
    "js": "javascript", "ts": "typescript", "json": "json",
    "yaml": "yaml", "yml": "yaml", "toml": "toml",
    "html": "markup", "css": "css", "go": "go", "rs": "rust",
    "rb": "ruby", "java": "java", "c": "c", "cpp": "cpp",
    "sql": "sql", "hjson": "json", "md": "markdown",
}

def detect_language(ext, first_line=""):
    """Return Prism language name from file extension or shebang."""
    lang = LANG_MAP.get(ext, "")
    if not lang and first_line.startswith("#!"):
        shebang = first_line.lower()
        if "python" in shebang: lang = "python"
        elif "bash" in shebang or "/sh" in shebang: lang = "bash"
        elif "node" in shebang: lang = "javascript"
        elif "ruby" in shebang: lang = "ruby"
    return lang


data = json.load(sys.stdin)
session_id = data.get("session_id", "default")
tool_name = data.get("tool_name", "")
tool_input = data.get("tool_input", {})
file_path = tool_input.get("file_path", "")

if not file_path or not os.path.isfile(file_path):
    sys.exit(0)

# --- Record this edit ---
changes_dir = VIEW_CHANGES_DIR
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

file_index = {fp: i for i, fp in enumerate(file_order)}  # O(1) lookups

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

# --- Detect git status for each changed file (single subprocess call) ---
# Status codes follow VS Code convention: U=untracked, A=added, M=modified, D=deleted, R=renamed
file_status = {}
file_rename_from = {}  # file -> original path (for renamed files)
git_statuses = {}  # rel_path -> porcelain status code
try:
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, timeout=5, cwd=git_root,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if len(line) >= 4:
                code = line[:2]
                path = line[3:]
                # Renames: "R  old -> new" or "RM old -> new"
                if code.startswith("R") and " -> " in path:
                    old_path, new_path = path.split(" -> ", 1)
                    git_statuses[new_path] = code
                    git_statuses[old_path] = code
                    # Track the rename mapping (new -> old)
                    new_abs = os.path.join(git_root, new_path)
                    file_rename_from[new_abs] = old_path
                else:
                    git_statuses[path] = code
except Exception:
    pass

for fp in file_order:
    rel = os.path.relpath(fp, git_root) if fp.startswith(git_root + "/") else None
    if rel:
        code = git_statuses.get(rel, "")
        if code.startswith("??"):
            file_status[fp] = "U"
        elif code.startswith("A") or code.startswith(" A"):
            file_status[fp] = "A"
        elif code.startswith("R"):
            file_status[fp] = "R"
        elif code.startswith("D") or code.startswith(" D"):
            file_status[fp] = "D"
        else:
            file_status[fp] = "M"
    else:
        file_status[fp] = "M"

    # Write tool to an untracked file = untracked; to a tracked file = modified
    tools_used = [c["tool"] for c in changes if c["file"] == fp]
    if tools_used == ["Write"] and not file_edits.get(fp):
        if file_status.get(fp) in ("U", "A"):
            file_status[fp] = "U"

# Detect deleted files: in changes log but no longer on disk
for fp in file_order:
    if not os.path.isfile(fp):
        file_status[fp] = "D"

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
            STATUS_TREE_CLS = {"U": "tree-untracked", "A": "tree-added", "M": "tree-modified", "D": "tree-deleted", "R": "tree-renamed"}
            status_cls = STATUS_TREE_CLS.get(status, "tree-modified")
            cls = f' class="{status_cls}"'
            badge = f'<span class="tree-badge tree-badge-{status.lower()}">{status}</span>'
            idx = file_index[fp]
            click = f' onclick="event.stopPropagation();openFile({idx})"'
        else:
            cls = ""
            badge = ""
            all_tree_files.append(fp)
            viewer_idx = len(file_order) + len(all_tree_files) - 1
            click = f' onclick="event.stopPropagation();openViewer({viewer_idx})"'
        lines.append(f'<li{cls}{click} style="padding-left:{indent + 14}px"><span class="tree-icon">{icon}</span>{html.escape(fname)}{badge}</li>')

    return lines

tree_html = "\n".join(["<ul class='tree-root'>"] + render_tree(tree) + ["</ul>"])

# --- Changes section (grouped by status, VS Code order) ---
changes_section_items = []
STATUS_BADGE_CLS = {"U": "tree-badge-u", "A": "tree-badge-a", "M": "tree-badge-m", "D": "tree-badge-d", "R": "tree-badge-r"}
# Group order: Added/Untracked, Modified, Renamed, Deleted
added_files = [(fp, i) for i, fp in enumerate(file_order) if file_status.get(fp) in ("U", "A")]
mod_files = [(fp, i) for i, fp in enumerate(file_order) if file_status.get(fp) == "M"]
ren_files = [(fp, i) for i, fp in enumerate(file_order) if file_status.get(fp) == "R"]
del_files = [(fp, i) for i, fp in enumerate(file_order) if file_status.get(fp) == "D"]

for file_list in [added_files, mod_files, ren_files, del_files]:
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
        badge_cls = STATUS_BADGE_CLS.get(status, "tree-badge-m")
        # Show original path for renamed files
        rename_hint = ""
        if status == "R" and fp in file_rename_from:
            rename_hint = f'<span class="changes-dir"> &larr; {html.escape(file_rename_from[fp])}</span>'
        changes_section_items.append(
            f'<li class="changes-item" onclick="openFile({idx})">'
            f'<span class="tree-icon">{icon}</span>{html.escape(basename)}{dir_hint}{rename_hint}'
            f'<span class="tree-badge {badge_cls}">{status}</span></li>'
        )

changes_html = "\n".join(changes_section_items)

# --- Build combined HTML ---
# --- Load CSS/JS from template files ---
_template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")
with open(os.path.join(_template_dir, "view-changes.css")) as f:
    CSS = f.read()
with open(os.path.join(_template_dir, "view-changes.js")) as f:
    JS = f.read()
with open(os.path.join(_template_dir, "view-changes-prism.js")) as f:
    PRISM_JS = f.read()

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

    is_deleted = not os.path.isfile(fp)
    if is_deleted:
        content = ""
    else:
        with open(fp, "r") as f:
            content = f.read()

    rel_path = os.path.relpath(os.path.dirname(fp), git_root)
    if rel_path == ".":
        rel_path = ""
    else:
        rel_path += "/"

    status = file_status.get(fp, "M")
    status_labels = {"U": "untracked", "A": "added", "M": "modified", "D": "deleted", "R": "renamed"}
    status_label = status_labels.get(status, "modified")
    count_text = f'{edit_count} edit{"s" if edit_count != 1 else ""}' if edit_strings else status_label
    count_cls = f"count count-{status.lower()}"
    count_badge = f'<span class="{count_cls}">{count_text}</span>'
    file_idx = file_index[fp]
    is_new_or_untracked = status in ("U", "A")
    toggle_btn = f'<button class="diff-toggle" onclick="event.stopPropagation();toggleFullFile({file_idx})">Show full file</button>' if edit_strings and not is_new_or_untracked else ""
    rename_info = ""
    if status == "R" and fp in file_rename_from:
        rename_info = f'<span class="filepath"> &larr; {html.escape(file_rename_from[fp])}</span>'
    parts.append(f'<details open>')
    parts.append(f'<summary><strong>{basename}</strong><span class="filepath">{rel_path}</span>{rename_info}{toggle_btn}{count_badge}</summary>')
    parts.append('<div class="file-content">')

    is_new_file = status in ("U", "A")

    if is_deleted:
        # Show deleted file with strikethrough old content if available
        del_content = "\n".join(old_s for old_s, _ in edit_strings if old_s)
        if del_content:
            parts.append(f'<pre><code><span class="diff-del">{html.escape(del_content)}</span></code></pre>')
        else:
            parts.append('<p style="color:var(--del-fg);font-style:italic">File deleted</p>')
        parts.append("</div></details>")
        continue

    lines = content.split("\n")
    file_idx = file_index[fp]
    # Determine language for Prism syntax highlighting
    diff_lang = detect_language(ext, lines[0] if lines else "")
    diff_lang_cls = f' class="language-{diff_lang}"' if diff_lang else ""

    if is_new_file:
        # Raw code with language class; JS will wrap lines with diff-line after Prism highlights
        parts.append(f'<pre><code{diff_lang_cls} data-diff-type="new-file">{html.escape(content)}</code></pre>')
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

        line_types = ["new" if i in highlight_lines else "ctx" for i in range(len(lines))]
        del_json = {str(k): v for k, v in del_before.items()}
        meta = json.dumps({"types": line_types, "deleted": del_json, "context": 3, "idx": file_idx})

        # Hidden source block for Prism to highlight; JS builds collapsed/full views from it
        parts.append(f'<div id="diff-source-{file_idx}" style="display:none"><pre><code{diff_lang_cls} data-diff-idx="{file_idx}">{html.escape(content)}</code></pre></div>')
        parts.append(f'<script type="application/json" id="diff-meta-{file_idx}">{meta}</script>')
        parts.append(f'<div id="diff-collapsed-{file_idx}"></div>')
        parts.append(f'<div id="diff-full-{file_idx}" style="display:none"></div>')

    parts.append("</div></details>")

# --- Viewer sections for non-edited files (hidden, opened via sidebar click) ---
for i, fp in enumerate(all_tree_files):
    if not os.path.isfile(fp):
        continue
    viewer_idx = len(file_order) + i
    basename = os.path.basename(fp)
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
    viewer_lang = detect_language(viewer_ext, viewer_content.split("\n", 1)[0] if viewer_content else "")
    viewer_lang_cls = f' class="language-{viewer_lang}"' if viewer_lang else ""
    parts.append(f'<pre class="line-numbers"><code{viewer_lang_cls}>{html.escape(viewer_content)}</code></pre>')
    parts.append("</div>")

parts.append('</div>')  # close .main

parts.append(f'<script>{JS}</script>')
# Prism.js
parts.append('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css" />')
parts.append('<script>window.Prism = window.Prism || {}; Prism.manual = true;</script>')
parts.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>')
parts.append('<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>')
for lang in ["python", "bash", "javascript", "typescript", "json", "yaml", "toml", "markup", "markdown", "css", "go", "rust", "java", "ruby", "sql", "c", "cpp"]:
    parts.append(f'<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-{lang}.min.js"></script>')

# Post-Prism: apply diff line wrapping to syntax-highlighted code
parts.append(f'<script>{PRISM_JS}</script>')

parts.append("</body></html>")

# --- Write combined HTML ---
out_file = f"/tmp/view-changes-{session_id}.html"
with open(out_file, "w") as f:
    f.write("\n".join(parts))

import time as _time
url = f"file://{out_file}?t={int(_time.time() * 1000)}"

# --- Navigate or create browser tab ---
tracking_dir = VIEW_SURFACES_DIR
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
