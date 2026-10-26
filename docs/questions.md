# Question format reference

Question sets are JSON files or challenge folders listed in `[questions].files`. **Each entry is one Jeopardy-style board category** — the `title` is what players click on the board.

```json
{
  "set_id": "fake_logos",
  "title": "Fake Logos",
  "questions": [ { "id": "g1", "type": "multiple_choice", "prompt": "...", "images": [...], "points": 10, ... } ]
}
```

## Board flow (config)

| Key | Meaning |
|-----|---------|
| `warmup_count` | Linear questions before the board (`0` = board immediately) |
| `board_slots` | How many categories shown at once |
| `questions_per_pick` | How many questions after picking a category |
| `redo_missed_at_set_end` | Redo missed within warm-up set / within a pick |

After a pick, that slot is refilled from unused categories. Timers freeze on the board. When no categories remain, the game ends.

## Types

| type | Key fields |
|------|------------|
| `multiple_choice` | `choices[]`, `answer` (index); optional `images` for picture rounds (Fake Logos) |
| `desk` | HC-style folder challenge: `accepted[]`, `panes` (`files` / `terminal` / `page`), optional `page_file`. Loaded from a challenge directory. Terminal is a real WSL bash for the team — see [wsl-desk.md](wsl-desk.md). |

Pictures: `images` is an array of **1 to 8** picture files. Paths are relative to the question JSON file. Formats: `png`, `jpg`, `jpeg`, `gif`, `webp`, `bmp`.

All files are validated at startup; the app refuses to start on errors.

## Challenge folders (HC-style)

```
challenges/hello_shell/
  challenge.json
  public/          # copied into the team's WSL disk on first open
  private/         # staff only — never copied into the distro
```

`challenge.json` can be a normal set or a compact one-question form. Desk challenges must be exactly one question. The loader sets `public_dir` automatically.

The desk UI is a narrow **file-name rail**, a dominant **terminal** (piped to the team bash), an optional **page**, and a flag box. Baton lock stops new commands; the shell and transcript stay. Talk across the handoff.

Do not put the accepted `TR{...}` string in `public/` unless the puzzle is meant to be a straight `cat`.
