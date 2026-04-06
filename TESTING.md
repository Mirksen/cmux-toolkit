# Testing the cmux-toolkit

## Test 1: Combined diff view (basic)

Paste this prompt into a Claude Code session to verify the combined browser view with sidebar and diff highlighting.

---

```
Ich teste den viewtab-Hook (PostToolUse → view-open-file.py). Bitte führe nacheinander diese Schritte aus, damit ich die kombinierte Browser-Ansicht mit Sidebar und Diff-Highlighting prüfen kann:

1. Erstelle /tmp/test-viewtab/README.md mit diesem Inhalt:

# Testprojekt ViewTab

Ein kleines Beispiel zum Testen des viewtab-Hooks.

## Features

- Markdown-Rendering
- Syntax-Highlighting
- Diff-Anzeige

## Status

Noch in Arbeit.

2. Editiere /tmp/test-viewtab/README.md — ersetze "Noch in Arbeit." durch "Version 1.0 — fertig! Alle Tests bestanden."

3. Erstelle /tmp/test-viewtab/app.py mit diesem Inhalt:

def greet(name: str) -> str:
    return f"Hallo {name}"

def add(a: int, b: int) -> int:
    return a + b

if __name__ == "__main__":
    print(greet("Welt"))
    print(add(2, 3))

4. Editiere /tmp/test-viewtab/app.py — füge nach der add-Funktion eine neue Funktion ein:

def multiply(a: int, b: int) -> int:
    """Multipliziert zwei Zahlen."""
    return a * b

5. Erstelle /tmp/test-viewtab/config.yaml:

app:
  name: viewtab-test
  version: "1.0"
  debug: false

server:
  host: localhost
  port: 8080

6. Editiere /tmp/test-viewtab/config.yaml — ändere debug von false auf true und port von 8080 auf 9090.

Warte nach jedem Schritt 2 Sekunden, damit ich den Tab prüfen kann. Sag mir bei jedem Schritt kurz was du gemacht hast (Write/Edit, welche Datei).
```

---

### Expected results

After all steps, the browser shows a **combined view** with:

| Element | Expected |
|---------|----------|
| **Sidebar** | File tree with 3 files, each showing status badge |
| **Changes list** | 3 files grouped by status (U for new, M for modified) |
| **README.md** | Rendered Markdown, old text in red strikethrough, new text in green |
| **app.py** | Syntax-highlighted Python, `multiply` function in green, collapsed context |
| **config.yaml** | Syntax-highlighted YAML, changed lines in green |
| **Toggle buttons** | "Show full file" / "Show changes only" on edited files |

Each Write/Edit updates the **same browser tab** (no new tabs per edit).

---

## Test 2: Git status badges

Run this in a **git-initialized** directory to verify all status types:

```
Ich teste die Git-Status-Badges. Bitte führe diese Schritte in /tmp/test-git-status aus:

1. Erstelle das Verzeichnis und initialisiere ein Git-Repo:
   mkdir -p /tmp/test-git-status && cd /tmp/test-git-status && git init

2. Erstelle eine Datei und committe sie:
   echo "original" > tracked.txt && git add tracked.txt && git commit -m "init"

3. Jetzt editiere tracked.txt — ersetze "original" durch "modified content"
   → Erwartung: Badge "M" (modified, gelb)

4. Erstelle eine neue Datei untracked.txt mit "hello world"
   → Erwartung: Badge "U" (untracked, grün)

Sag mir bei jedem Schritt was du siehst.
```

### Expected badges

| File | Status | Badge | Color |
|------|--------|-------|-------|
| tracked.txt | Modified | M | Yellow/amber |
| untracked.txt | Untracked | U | Green |

---

## Test 3: Deleted files

```
Ich teste die Anzeige gelöschter Dateien. Bitte führe diese Schritte in /tmp/test-delete aus:

1. mkdir -p /tmp/test-delete && cd /tmp/test-delete && git init
2. Erstelle eine Datei old-code.py mit:

def deprecated():
    return "this will be removed"

3. git add old-code.py && git commit -m "add old code"

4. Erstelle eine neue Datei new-code.py mit:

def replacement():
    return "this is the new version"

5. Lösche old-code.py: rm old-code.py

6. Editiere new-code.py — füge hinzu:

def helper():
    return "added helper"

Sag mir was die kombinierte Ansicht zeigt — insbesondere ob old-code.py als gelöscht (D, rot) angezeigt wird.
```

### Expected

| File | Status | Badge | Display |
|------|--------|-------|---------|
| old-code.py | Deleted | D | Red, strikethrough in sidebar, content shown with strikethrough |
| new-code.py | Untracked | U | Green, full file highlighted |

---

## Test 4: Dark mode

1. Switch your system to dark mode (System Settings → Appearance → Dark)
2. Run any of the tests above
3. Verify: dark background, light text, green/red/yellow diffs still readable

---

## Test 5: Manual view/edit commands

```bash
# View a markdown file in browser
! view ~/cmux-toolkit/README.md

# View a code file with syntax highlighting
! viewtab ~/cmux-toolkit/hooks/view-open-file.py

# Open a file in Vim (split pane)
! edit ~/cmux-toolkit/setup.sh

# Open a file in Vim (tab mode)
! edittab ~/cmux-toolkit/setup.sh
```

---

## Cleanup

```bash
rm -rf /tmp/test-viewtab /tmp/test-git-status /tmp/test-delete
```
