# Testing the cmux-toolkit

Paste this prompt into a Claude Code session to verify viewtab browser tabs and diff highlighting work correctly.

The prompt creates test files (Markdown, Python, YAML) and edits them step by step — each Write triggers a new browser tab, each Edit triggers a tab with green diff highlighting.

---

```
Ich teste den viewtab-Hook (PostToolUse → view-open-file.py → viewtab). Bitte führe nacheinander diese Schritte aus, damit ich sehe ob die Browser-Tabs mit Diff-Highlighting korrekt aufgehen:

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

## Expected results

| Step | Tool | File | Browser tab shows |
|------|------|------|-------------------|
| 1 | Write | README.md | Rendered Markdown (no diff) |
| 2 | Edit | README.md | Rendered Markdown, "Version 1.0..." in green |
| 3 | Write | app.py | Syntax-highlighted Python (no diff) |
| 4 | Edit | app.py | Python with `multiply` function in green |
| 5 | Write | config.yaml | Syntax-highlighted YAML (no diff) |
| 6 | Edit | config.yaml | YAML with `debug: true` and `port: 9090` in green |

## Cleanup

```bash
rm -rf /tmp/test-viewtab
```
