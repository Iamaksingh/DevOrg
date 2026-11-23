---
name: init
description: Set up DevOrg in the current project — detects the test command, writes .devorg/config.json and .devorg/rules.md, and git-ignores .devorg/. Run once per project before /devorg:run.
argument-hint: "[--force]"
disable-model-invocation: true
---

Set up DevOrg (the AI software team) in the current project. Work through these steps in order,
tell the human briefly what you're doing, and ask before overwriting anything.

## 1. Check the project

- Run `git rev-parse --show-toplevel`. If this isn't a git repository, explain that DevOrg uses
  git diffs as review evidence and ask whether to run `git init`. Do not continue without git.
- If `.devorg/config.json` already exists and `$ARGUMENTS` doesn't contain `--force`, show its
  contents and ask whether to keep it (stop) or re-initialise.
- If `.devorg/state.json` shows a ticket whose phase is not `done` or `cancelled`, stop: tell the
  human to finish it (`/devorg:run resume`) or type `CANCEL` first.

## 2. Find the test command

Look at the project root (and the obvious subfolders) for these markers and suggest the matching command:

| Marker | Suggested `test_command` |
|---|---|
| `package.json` with a `test` script | `npm test` (or `pnpm test` / `yarn test` if that lockfile exists) |
| `pyproject.toml`, `pytest.ini`, `setup.cfg`, `tests/` with `test_*.py` | `python -m pytest` (or `python -m unittest discover` if pytest isn't used) |
| `go.mod` | `go test ./...` |
| `Cargo.toml` | `cargo test` |
| `pom.xml` | `mvn -q test` |
| `build.gradle` / `build.gradle.kts` | `./gradlew test` |
| `*.sln` / `*.csproj` | `dotnet test` |
| `Gemfile` with rspec | `bundle exec rspec` |
| `Makefile` with a `test:` target | `make test` |

Ask the human to confirm or type their own command (the AskUserQuestion tool is fine here).
If the project has no tests yet, record the command anyway and warn that acceptance reviews will
fail until tests exist.

## 3. Write the files

1. `.devorg/config.json`:
   ```json
   {
     "version": 1,
     "test_command": "<confirmed command>",
     "max_revisions": 3
   }
   ```
2. `.devorg/rules.md`: copy `org-rules.md` from this skill's directory **verbatim**. If
   `.devorg/rules.md` already exists, ask before replacing it (the team may have tailored it).
3. Create the empty folder `.devorg/tickets/` (e.g. by writing `.devorg/tickets/.gitkeep`).
4. `.gitignore`: add a line `.devorg/` unless it is already ignored (`git check-ignore -q .devorg/config.json`).
   Create `.gitignore` if it doesn't exist.

## 4. Recommend (don't apply) project permissions

Tell the human these optional extras for `.claude/settings.local.json`. Do not write them
yourself; settings are the human's call:
- `"allow": ["Bash(<test_command>:*)"]` — so test runs don't prompt every time.
- `"deny": ["Read(**/.env)", "Read(**/.env.*)"]` — a second secrets layer that also covers Grep.

## 5. Finish

Print a short summary of what was created and the next step:
`/devorg:run <ticket.md or "ticket text">`
