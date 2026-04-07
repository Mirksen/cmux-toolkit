#!/usr/bin/env python3
"""PostToolUse hook: render git working tree changes in a VS Code-style Source Control view.

On each Edit/Write/Bash:
1. Runs git status + git diff to capture all uncommitted changes
2. Renders a combined HTML page with sidebar (changed files) + unified diff sections
3. Navigates the existing browser tab (or creates one) to the combined page

Works with Claude Code, OpenCode, and any tool that pipes compatible JSON to stdin.
"""
import json, sys, os, subprocess, re, html

# Import shared config (resolve through symlinks)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'lib'))
from common import VIEW_SURFACES_DIR

# --- Shared helpers ---

LANG_MAP = {
    "py": "python", "sh": "bash", "bash": "bash", "zsh": "bash",
    "js": "javascript", "ts": "typescript", "json": "json",
    "yaml": "yaml", "yml": "yaml", "toml": "toml",
    "html": "markup", "css": "css", "go": "go", "rs": "rust",
    "rb": "ruby", "java": "java", "c": "c", "cpp": "cpp",
    "sql": "sql", "hjson": "json", "md": "markdown",
}

def detect_language(filepath):
    """Return Prism language name from file extension or shebang."""
    ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""
    lang = LANG_MAP.get(ext, "")
    if not lang:
        try:
            with open(filepath, "r") as f:
                first_line = f.readline()
            if first_line.startswith("#!"):
                shebang = first_line.lower()
                if "python" in shebang: lang = "python"
                elif "bash" in shebang or "/sh" in shebang: lang = "bash"
                elif "node" in shebang: lang = "javascript"
                elif "ruby" in shebang: lang = "ruby"
        except Exception:
            pass
    return lang


# --- Parse input ---
data = json.load(sys.stdin)
session_id = data.get("session_id", "default")
tool_name = data.get("tool_name", "")

# Trigger on file-mutating tools
if tool_name not in ("Edit", "Write", "Bash"):
    sys.exit(0)

# --- Find git root ---
cwd = os.getcwd()
try:
    git_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=5, cwd=cwd,
    ).stdout.strip()
except Exception:
    git_root = ""

if not git_root:
    git_root = cwd

# --- Get git status ---
file_status = {}  # rel_path -> status code (M, A, D, R, U)
file_rename_from = {}  # rel_path -> original rel_path (for renames)
try:
    result = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        capture_output=True, text=True, timeout=5, cwd=git_root,
    )
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            code = line[:2]
            path = line[3:]
            if code.startswith("R") and " -> " in path:
                old_path, new_path = path.split(" -> ", 1)
                file_status[new_path] = "R"
                file_rename_from[new_path] = old_path
            elif code.startswith("??"):
                file_status[path] = "U"
            elif code.startswith("A") or code.startswith(" A"):
                file_status[path] = "A"
            elif code.startswith("D") or code.endswith("D"):
                file_status[path] = "D"
            else:
                file_status[path] = "M"
except Exception:
    pass

# If no changes, render a clean state page (don't exit — update the browser)
if not file_status:
    _template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")
    with open(os.path.join(_template_dir, "view-changes.css")) as f:
        CSS = f.read()
    project_name = os.path.basename(git_root)
    home = os.path.expanduser("~")
    display_path = ("~/" + os.path.relpath(git_root, home)) if git_root.startswith(home) else git_root
    clean_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style>
<title>Source Control (clean)</title></head><body>
<div class="activity-bar">
<button class="activity-btn active" title="Source Control">
<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M21.007 8.222A3.738 3.738 0 0 0 15.045 5.2a3.737 3.737 0 0 0 1.156 6.583 2.988 2.988 0 0 1-2.668 1.67h-2.99a4.456 4.456 0 0 0-2.989 1.165V7.559a3.738 3.738 0 1 0-1.494 0v8.882a3.738 3.738 0 1 0 1.494.07 2.99 2.99 0 0 1 2.99-2.818h2.988a4.482 4.482 0 0 0 4.238-3.028 3.738 3.738 0 0 0 3.237-2.443zM3.053 2.988a2.244 2.244 0 1 1 4.488 0 2.244 2.244 0 0 1-4.488 0zm4.488 18.024a2.244 2.244 0 1 1-4.488 0 2.244 2.244 0 0 1 4.488 0zm10.469-10.463a2.244 2.244 0 1 1 0-4.488 2.244 2.244 0 0 1 0 4.488z"/></svg>
</button></div>
<div class="sidebar">
<div class="sidebar-title">Source Control<span class="sidebar-path">{html.escape(project_name)}</span></div>
<div class="section-header"><span class="section-arrow">\u25bc</span>Changes<span class="section-count">0</span></div>
<div class="section-content"><ul class="changes-list"></ul></div>
</div>
<div class="resize-handle"></div>
<div class="main"><div class="clean-state">No pending changes &mdash; working tree is clean</div></div>
</body></html>"""

    import time as _time
    out_file = f"/tmp/view-changes-{session_id}.html"
    with open(out_file, "w") as f:
        f.write(clean_html)
    url = f"file://{out_file}?t={int(_time.time() * 1000)}"

    tracking_dir = VIEW_SURFACES_DIR
    os.makedirs(tracking_dir, exist_ok=True)
    tracking_file = os.path.join(tracking_dir, f"{session_id}.txt")
    reuse_surface = ""
    if os.path.isfile(tracking_file):
        with open(tracking_file, "r") as tf:
            lines = [l.strip() for l in tf if l.strip()]
        if lines:
            reuse_surface = lines[-1]
    if reuse_surface:
        try:
            subprocess.run(
                ["cmux", "browser", "--surface", reuse_surface, "navigate", url],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            pass
    sys.exit(0)

# --- Get unified diffs ---

def get_diff_for_file(rel_path, status):
    """Get unified diff content for a file."""
    abs_path = os.path.join(git_root, rel_path)

    if status == "U":
        # Untracked file: show full content as added
        try:
            with open(abs_path, "r") as f:
                content = f.read()
            lines = content.split("\n")
            # Remove trailing empty line from split
            if lines and lines[-1] == "":
                lines = lines[:-1]
            diff_lines = []
            diff_lines.append(f"@@ -0,0 +1,{len(lines)} @@")
            for line in lines:
                diff_lines.append(f"+{line}")
            return "\n".join(diff_lines)
        except Exception:
            return ""

    if status == "D":
        # Deleted file: get diff showing removal
        try:
            result = subprocess.run(
                ["git", "diff", "--", rel_path],
                capture_output=True, text=True, timeout=5, cwd=git_root,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
            # Try cached diff for staged deletions
            result = subprocess.run(
                ["git", "diff", "--cached", "--", rel_path],
                capture_output=True, text=True, timeout=5, cwd=git_root,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception:
            return ""

    # Modified, Added, Renamed: get standard diff
    try:
        # Try unstaged first
        result = subprocess.run(
            ["git", "diff", "--", rel_path],
            capture_output=True, text=True, timeout=5, cwd=git_root,
        )
        diff = result.stdout if result.returncode == 0 else ""

        # Also check staged changes
        result2 = subprocess.run(
            ["git", "diff", "--cached", "--", rel_path],
            capture_output=True, text=True, timeout=5, cwd=git_root,
        )
        staged = result2.stdout if result2.returncode == 0 else ""

        # If file is staged (e.g. new file added with git add), use staged diff
        if not diff and staged:
            return staged
        # If both exist, use HEAD diff for combined view
        if diff and staged:
            result3 = subprocess.run(
                ["git", "diff", "HEAD", "--", rel_path],
                capture_output=True, text=True, timeout=5, cwd=git_root,
            )
            return result3.stdout if result3.returncode == 0 else diff
        return diff
    except Exception:
        return ""


def parse_unified_diff(diff_text):
    """Parse unified diff into structured hunks.

    Returns list of hunks, each hunk is:
    {
        "header": "@@ -10,5 +12,7 @@ context",
        "lines": [
            {"type": "ctx"|"add"|"del", "old_ln": int|None, "new_ln": int|None, "text": str},
            ...
        ]
    }
    """
    hunks = []
    current_hunk = None
    old_ln = 0
    new_ln = 0

    for line in diff_text.split("\n"):
        # Skip diff headers (diff --git, index, ---, +++)
        if line.startswith("diff --git") or line.startswith("index ") or \
           line.startswith("--- ") or line.startswith("+++ ") or \
           line.startswith("new file") or line.startswith("deleted file") or \
           line.startswith("old mode") or line.startswith("new mode") or \
           line.startswith("similarity index") or line.startswith("rename from") or \
           line.startswith("rename to") or line.startswith("Binary files"):
            continue

        hunk_match = re.match(r'^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)', line)
        if hunk_match:
            current_hunk = {
                "header": line,
                "context_text": hunk_match.group(3).strip(),
                "lines": [],
            }
            hunks.append(current_hunk)
            old_ln = int(hunk_match.group(1))
            new_ln = int(hunk_match.group(2))
            continue

        if current_hunk is None:
            continue

        if line.startswith("+"):
            current_hunk["lines"].append({
                "type": "add",
                "old_ln": None,
                "new_ln": new_ln,
                "text": line[1:],
            })
            new_ln += 1
        elif line.startswith("-"):
            current_hunk["lines"].append({
                "type": "del",
                "old_ln": old_ln,
                "new_ln": None,
                "text": line[1:],
            })
            old_ln += 1
        elif line.startswith("\\"):
            # "\ No newline at end of file"
            continue
        else:
            # Context line (starts with space or is empty)
            text = line[1:] if line.startswith(" ") else line
            current_hunk["lines"].append({
                "type": "ctx",
                "old_ln": old_ln,
                "new_ln": new_ln,
                "text": text,
            })
            old_ln += 1
            new_ln += 1

    return hunks


def render_diff_table(hunks, lang):
    """Render parsed hunks as an HTML diff table."""
    if not hunks:
        return '<p class="diff-empty">No changes</p>'

    lang_cls = f' class="language-{lang}"' if lang else ""
    rows = []

    for hunk in hunks:
        # Hunk header row
        header_text = html.escape(hunk["header"])
        rows.append(f'<tr class="diff-hunk"><td class="ln-old"></td><td class="ln-new"></td><td class="sign"></td><td class="code">{header_text}</td></tr>')

        for line in hunk["lines"]:
            text = html.escape(line["text"])
            old_ln = line["old_ln"] if line["old_ln"] is not None else ""
            new_ln = line["new_ln"] if line["new_ln"] is not None else ""

            if line["type"] == "add":
                sign = "+"
                row_cls = "diff-add"
            elif line["type"] == "del":
                sign = "\u2212"  # minus sign
                row_cls = "diff-del"
            else:
                sign = " "
                row_cls = "diff-ctx"

            rows.append(
                f'<tr class="{row_cls}">'
                f'<td class="ln-old">{old_ln}</td>'
                f'<td class="ln-new">{new_ln}</td>'
                f'<td class="sign">{sign}</td>'
                f'<td class="code"><code{lang_cls}>{text}</code></td>'
                f'</tr>'
            )

    return f'<table class="diff-table">{"".join(rows)}</table>'


project_name = os.path.basename(git_root)

# --- File type icons ---
FILE_ICONS = {
    "py": "\U0001f40d", "js": "\U0001f4dc", "ts": "\U0001f4d8", "jsx": "\u269b", "tsx": "\u269b",
    "md": "\U0001f4dd", "json": "\U0001f4cb", "yaml": "\U0001f4cb", "yml": "\U0001f4cb", "toml": "\U0001f4cb",
    "sh": "\u2699", "bash": "\u2699", "zsh": "\u2699",
    "html": "\U0001f310", "css": "\U0001f3a8", "svg": "\U0001f3a8",
    "rs": "\U0001f980", "go": "\U0001f439", "rb": "\U0001f48e", "java": "\u2615",
    "c": "\U0001f527", "cpp": "\U0001f527", "h": "\U0001f527",
    "txt": "\U0001f4c4", "csv": "\U0001f4ca", "sql": "\U0001f5c3",
    "hjson": "\U0001f4cb", "xml": "\U0001f4cb",
    "png": "\U0001f5bc", "jpg": "\U0001f5bc", "gif": "\U0001f5bc", "webp": "\U0001f5bc",
    "lock": "\U0001f512", "env": "\U0001f512",
}
DIR_ICON = "\U0001f4c1"

def get_icon(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return FILE_ICONS.get(ext, "\U0001f4c4")

# Sort changed files: Added/Untracked, Modified, Renamed, Deleted
file_order = []
for status_group in ["U", "A", "M", "R", "D"]:
    for rel_path, status in sorted(file_status.items()):
        if status == status_group:
            file_order.append(rel_path)

file_index = {rel: i for i, rel in enumerate(file_order)}

STATUS_TREE_CLS = {"U": "tree-untracked", "A": "tree-added", "M": "tree-modified", "D": "tree-deleted", "R": "tree-renamed"}
STATUS_BADGE_CLS = {"U": "tree-badge-u", "A": "tree-badge-a", "M": "tree-badge-m", "D": "tree-badge-d", "R": "tree-badge-r"}

# --- Changes list (Source Control sidebar) ---
changes_section_items = []

for rel_path in file_order:
    idx = file_index[rel_path]
    basename = os.path.basename(rel_path)
    icon = get_icon(basename)
    dirname = os.path.dirname(rel_path)
    dir_hint = f'<span class="changes-dir">{dirname}/</span>' if dirname and dirname != "." else ""
    status = file_status[rel_path]
    badge_cls = STATUS_BADGE_CLS.get(status, "tree-badge-m")
    rename_hint = ""
    if status == "R" and rel_path in file_rename_from:
        rename_hint = f'<span class="changes-dir"> &larr; {html.escape(file_rename_from[rel_path])}</span>'
    changes_section_items.append(
        f'<li class="changes-item" onclick="openFile({idx})">'
        f'<span class="tree-icon">{icon}</span>{html.escape(basename)}{dir_hint}{rename_hint}'
        f'<span class="tree-badge {badge_cls}">{status}</span></li>'
    )

changes_html = "\n".join(changes_section_items)

# --- Full file tree (Explorer sidebar) ---
all_files = set()
try:
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True, text=True, timeout=5, cwd=git_root,
    )
    if result.returncode == 0:
        for f in result.stdout.strip().split("\n"):
            if f:
                all_files.add(f)  # rel paths
except Exception:
    pass

# Add changed files to the tree (untracked files won't be in ls-files)
for rel_path in file_status:
    all_files.add(rel_path)

def build_tree(files):
    """Build a tree from relative paths."""
    tree = {}
    for rel_path in sorted(files):
        parts = rel_path.split(os.sep)
        node = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                node.setdefault(part, {"__file__": rel_path})
            else:
                node.setdefault(part, {})
                node = node[part]
    return tree

explorer_tree = build_tree(all_files)

explorer_file_list = []  # track non-changed files for viewer sections

def render_explorer_tree(node, depth=0):
    """Render full file tree, highlighting changed files."""
    lines = []
    dirs = sorted([k for k, v in node.items() if "__file__" not in v])
    files = sorted([k for k, v in node.items() if "__file__" in v])
    indent = depth * 12

    for d in dirs:
        lines.append(f'<li class="tree-dir" style="padding-left:{indent}px">')
        lines.append(f'<span class="tree-toggle"><span class="tree-arrow"></span><span class="tree-icon dir-icon">{DIR_ICON}</span>{html.escape(d)}</span>')
        lines.append('<ul class="tree-children">')
        lines.extend(render_explorer_tree(node[d], depth + 1))
        lines.append('</ul></li>')

    for fname in files:
        rel = node[fname]["__file__"]
        is_changed = rel in file_status
        status = file_status.get(rel, "")
        icon = get_icon(fname)
        if is_changed:
            status_cls = STATUS_TREE_CLS.get(status, "tree-modified")
            cls = f' class="{status_cls}"'
            badge = f'<span class="tree-badge tree-badge-{status.lower()}">{status}</span>'
            idx = file_index.get(rel, 0)
            click = f' onclick="event.stopPropagation();openFile({idx})"'
        else:
            cls = ""
            badge = ""
            explorer_file_list.append(rel)
            viewer_idx = len(file_order) + len(explorer_file_list) - 1
            click = f' onclick="event.stopPropagation();openViewer({viewer_idx})"'
        lines.append(f'<li{cls}{click} style="padding-left:{indent + 14}px"><span class="tree-icon">{icon}</span>{html.escape(fname)}{badge}</li>')

    return lines

explorer_html = "\n".join(["<ul class='tree-root'>"] + render_explorer_tree(explorer_tree) + ["</ul>"])

# --- Load CSS/JS from template files ---
_template_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "templates")
with open(os.path.join(_template_dir, "view-changes.css")) as f:
    CSS = f.read()
with open(os.path.join(_template_dir, "view-changes.js")) as f:
    JS = f.read()

# --- Build combined HTML ---
parts = []
parts.append('<!DOCTYPE html><html><head><meta charset="utf-8">')
parts.append(f'<style>{CSS}</style>')
parts.append(f'<title>Source Control ({len(file_order)} files)</title></head><body>')

home = os.path.expanduser("~")
if git_root.startswith(home):
    display_path = "~/" + os.path.relpath(git_root, home)
else:
    display_path = git_root

# --- Activity bar (far left) ---
parts.append('<div class="activity-bar">')
# Source Control button (active by default)
parts.append(f'<button class="activity-btn active" id="actbtn-scm" onclick="switchPanel(\'scm\')" title="Source Control">')
parts.append('<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M21.007 8.222A3.738 3.738 0 0 0 15.045 5.2a3.737 3.737 0 0 0 1.156 6.583 2.988 2.988 0 0 1-2.668 1.67h-2.99a4.456 4.456 0 0 0-2.989 1.165V7.559a3.738 3.738 0 1 0-1.494 0v8.882a3.738 3.738 0 1 0 1.494.07 2.99 2.99 0 0 1 2.99-2.818h2.988a4.482 4.482 0 0 0 4.238-3.028 3.738 3.738 0 0 0 3.237-2.443zM3.053 2.988a2.244 2.244 0 1 1 4.488 0 2.244 2.244 0 0 1-4.488 0zm4.488 18.024a2.244 2.244 0 1 1-4.488 0 2.244 2.244 0 0 1 4.488 0zm10.469-10.463a2.244 2.244 0 1 1 0-4.488 2.244 2.244 0 0 1 0 4.488z"/></svg>')
if file_order:
    parts.append(f'<span class="activity-badge">{len(file_order)}</span>')
parts.append('</button>')
# Explorer button
parts.append(f'<button class="activity-btn" id="actbtn-explorer" onclick="switchPanel(\'explorer\')" title="Explorer">')
parts.append('<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor"><path d="M17.5 0h-9L7 1.5V6H2.5L1 7.5v15.07L2.5 24h12.07L16 22.57V18h4.7l1.3-1.43V4.5L17.5 0zm0 2.12l2.38 2.38H17.5V2.12zm-3 20.38h-12v-15H7v9.07L8.5 18h6v4.5zm6-6h-12v-15H16V6h4.5v10.5z"/></svg>')
parts.append('</button>')
parts.append('</div>')

# --- Sidebar ---
parts.append('<div class="sidebar">')

# Source Control panel (default)
parts.append(f'<div id="sidebar-scm">')
parts.append(f'<div class="sidebar-title">Source Control<span class="sidebar-path">{html.escape(project_name)}</span></div>')
parts.append(f'<div class="section-header" onclick="this.classList.toggle(\'collapsed\')"><span class="section-arrow">\u25bc</span>Changes<span class="section-count">{len(file_order)}</span></div>')
parts.append(f'<div class="section-content"><ul class="changes-list">{changes_html}</ul></div>')
parts.append('</div>')

# Explorer panel (hidden by default)
parts.append(f'<div id="sidebar-explorer" style="display:none">')
parts.append(f'<div class="sidebar-title">Explorer<span class="sidebar-path">{html.escape(project_name)}</span></div>')
parts.append(f'<div class="section-header" onclick="this.classList.toggle(\'collapsed\')"><span class="section-arrow">\u25bc</span>{html.escape(project_name)}</div>')
parts.append(f'<div class="section-content">{explorer_html}</div>')
parts.append('</div>')

parts.append('</div>')
parts.append('<div class="resize-handle" id="resize-handle"></div>')

# --- Editor area ---
parts.append('<div class="main">')

# Editor header (tab-like bar)
total_added = sum(1 for s in file_status.values() if s in ("U", "A"))
total_modified = sum(1 for s in file_status.values() if s == "M")
total_deleted = sum(1 for s in file_status.values() if s == "D")
total_renamed = sum(1 for s in file_status.values() if s == "R")

stat_parts = []
if total_added: stat_parts.append(f'{total_added} added')
if total_modified: stat_parts.append(f'{total_modified} modified')
if total_renamed: stat_parts.append(f'{total_renamed} renamed')
if total_deleted: stat_parts.append(f'{total_deleted} deleted')
stat_text = ", ".join(stat_parts) if stat_parts else "no changes"

parts.append('<div class="editor-header">')
parts.append(f'<h1><strong>{len(file_order)}</strong> file{"s" if len(file_order) != 1 else ""} changed <span class="stat-summary">({stat_text})</span>')
parts.append('<button class="collapse-all-btn" id="collapse-all-btn" onclick="toggleCollapseAll()" title="Collapse all">')
parts.append('<svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor"><path d="M5.22 3.22a.75.75 0 011.06 0L8 4.94l1.72-1.72a.75.75 0 111.06 1.06L8.53 6.53a.75.75 0 01-1.06 0L5.22 4.28a.75.75 0 010-1.06zm0 8a.75.75 0 011.06 0L8 12.94l1.72-1.72a.75.75 0 111.06 1.06l-2.25 2.25a.75.75 0 01-1.06 0l-2.25-2.25a.75.75 0 010-1.06z"/></svg>')
parts.append('</button>')
parts.append('</h1></div>')

# Editor content area
parts.append('<div class="editor-content">')

# --- Git diff stat summary ---
git_diff_stat = ""
try:
    result = subprocess.run(
        ["git", "diff", "--stat"],
        capture_output=True, text=True, timeout=5, cwd=git_root,
    )
    if result.returncode == 0 and result.stdout.strip():
        git_diff_stat = result.stdout.strip()
    # Also include staged changes
    result2 = subprocess.run(
        ["git", "diff", "--cached", "--stat"],
        capture_output=True, text=True, timeout=5, cwd=git_root,
    )
    if result2.returncode == 0 and result2.stdout.strip():
        if git_diff_stat:
            git_diff_stat += "\n" + result2.stdout.strip()
        else:
            git_diff_stat = result2.stdout.strip()
except Exception:
    pass

if git_diff_stat:
    stat_lines = []
    for sl in git_diff_stat.split("\n"):
        escaped = html.escape(sl)
        # Colorize +/- in stat bars (e.g. "file | 10 ++++------")
        escaped = re.sub(
            r'(\| +\d+\s*)(\+*?)(-*?)$',
            lambda m: m.group(1) + (f'<span class="stat-add">{m.group(2)}</span>' if m.group(2) else '') + (f'<span class="stat-del">{m.group(3)}</span>' if m.group(3) else ''),
            escaped
        )
        stat_lines.append(escaped)
    stat_html = "\n".join(stat_lines)
    parts.append('<details class="diff-stat-section">')
    parts.append('<summary><strong>git diff --stat</strong></summary>')
    parts.append(f'<div class="file-content"><pre class="diff-stat"><code>{stat_html}</code></pre></div>')
    parts.append('</details>')

# --- Render each file's diff ---
for rel_path in file_order:
    status = file_status[rel_path]
    basename = os.path.basename(rel_path)
    dirname = os.path.dirname(rel_path)
    dir_display = (dirname + "/") if dirname and dirname != "." else ""
    idx = file_index[rel_path]
    lang = detect_language(os.path.join(git_root, rel_path))

    count_cls = f"count count-{status.lower()}"
    count_badge = f'<span class="{count_cls}">{status}</span>'

    rename_info = ""
    if status == "R" and rel_path in file_rename_from:
        rename_info = f'<span class="filepath"> &larr; {html.escape(file_rename_from[rel_path])}</span>'

    # Get and parse diff
    diff_text = get_diff_for_file(rel_path, status)
    hunks = parse_unified_diff(diff_text)
    diff_html = render_diff_table(hunks, lang)

    # Read full file content (for "show full file" toggle)
    abs_path = os.path.join(git_root, rel_path)
    full_file_html = ""
    show_full_file_btn = ""
    if status not in ("D", "U", "A") and os.path.isfile(abs_path):
        try:
            with open(abs_path, "r") as f:
                full_content = f.read()
            lang_cls = f' class="language-{lang}"' if lang else ""
            # Collect changed line numbers from hunks
            added_lines = set()  # new-file line numbers that are additions
            for hunk in hunks:
                for hl in hunk["lines"]:
                    if hl["type"] == "add" and hl["new_ln"] is not None:
                        added_lines.add(hl["new_ln"])
            full_lines = full_content.split("\n")
            full_rows = []
            for ln_num, line_text in enumerate(full_lines, 1):
                if ln_num in added_lines:
                    row_cls = "diff-add"
                    sign = "+"
                else:
                    row_cls = "diff-ctx"
                    sign = " "
                full_rows.append(
                    f'<tr class="{row_cls}">'
                    f'<td class="ln-old">{ln_num}</td>'
                    f'<td class="ln-new">{ln_num}</td>'
                    f'<td class="sign">{sign}</td>'
                    f'<td class="code"><code{lang_cls}>{html.escape(line_text)}</code></td>'
                    f'</tr>'
                )
            full_file_html = f'<table class="diff-table">{"".join(full_rows)}</table>'
            show_full_file_btn = f'<button class="diff-toggle" onclick="event.stopPropagation();toggleFullFile({idx})">Show full file</button>'
        except Exception:
            pass

    parts.append(f'<details open id="file-{idx}">')
    parts.append(f'<summary><strong>{html.escape(basename)}</strong><span class="filepath">{html.escape(dir_display)}</span>{rename_info}{show_full_file_btn}{count_badge}</summary>')
    parts.append(f'<div class="file-content">')
    parts.append(f'<div id="diff-view-{idx}">{diff_html}</div>')
    if full_file_html:
        parts.append(f'<div id="full-view-{idx}" style="display:none">{full_file_html}</div>')
    parts.append('</div></details>')


# --- Viewer sections for explorer files (non-changed) ---
for i, rel_path in enumerate(explorer_file_list):
    abs_path = os.path.join(git_root, rel_path)
    if not os.path.isfile(abs_path):
        continue
    viewer_idx = len(file_order) + i
    basename = os.path.basename(rel_path)
    dirname = os.path.dirname(rel_path)
    dir_display = (dirname + "/") if dirname and dirname != "." else ""
    try:
        with open(abs_path, "r") as f:
            viewer_content = f.read()
    except Exception:
        continue
    lang = detect_language(abs_path)
    lang_cls = f' class="language-{lang}"' if lang else ""
    # Render as a simple line-numbered table (same style as diff table)
    viewer_lines = viewer_content.split("\n")
    viewer_rows = []
    for ln_num, line_text in enumerate(viewer_lines, 1):
        viewer_rows.append(
            f'<tr class="diff-ctx">'
            f'<td class="ln-old">{ln_num}</td>'
            f'<td class="ln-new"></td>'
            f'<td class="sign"></td>'
            f'<td class="code"><code{lang_cls}>{html.escape(line_text)}</code></td>'
            f'</tr>'
        )
    viewer_table = f'<table class="diff-table">{"".join(viewer_rows)}</table>'
    parts.append(f'<div id="viewer-{viewer_idx}" class="viewer-section" style="display:none">')
    parts.append(f'<div class="viewer-header"><strong>{html.escape(basename)}</strong><span class="filepath">{html.escape(dir_display)}</span><span class="viewer-close" onclick="this.closest(\'.viewer-section\').style.display=\'none\';clearActiveNav()">&times;</span></div>')
    parts.append(f'<div class="file-content">{viewer_table}</div>')
    parts.append("</div>")

parts.append('</div>')  # close .editor-content
parts.append('</div>')  # close .main

parts.append(f'<script>{JS}</script>')

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
    import fcntl
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
