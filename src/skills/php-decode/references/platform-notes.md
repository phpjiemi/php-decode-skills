# Portability Notes

This skill is authored once in `src/skills/` and built into five harness-specific
packages. The canonical `SKILL.md` deliberately uses only `name` and `description`
frontmatter plus relative paths, so the **instructions are identical everywhere**.
Only metadata and packaging differ.

## Common baseline (lowest common denominator)

| Constraint | Value chosen | Why |
|---|---|---|
| `name` | `^[a-z0-9]+(-[a-z0-9]+)*$`, matches the folder name | DeepSeek Harness is strictest; Claude Code forbids reserved words and uppercase |
| `description` | < 500 characters, states *what* and *when* | DeepSeek Harness truncates at 500; Codex caps the whole skill list at ~2% of context |
| Frontmatter | `name` + `description` only | Every client ignores unknown fields, but a minimal header never breaks a parser |
| Body | Harness-neutral verbs ("read", "run", "ask") | Avoids tool names that only exist in one client |
| Resources | Relative `scripts/` and `references/` paths | Supported by all five clients |

## Per-harness differences

| Harness | Skill location | Extra metadata | Notable limits |
|---|---|---|---|
| OpenAI Codex CLI | `<repo>/.agents/skills/<name>/` (or `~/.agents/skills/`, `/etc/codex/skills/`); `~/.codex/skills/` also seen on older installs | `agents/openai.yaml` for UI metadata and invocation policy | `Agents.md` is for repo rules, not for skill bodies; skills can be toggled in `~/.codex/config.toml` |
| Claude Code | `.claude/skills/<name>/` or `~/.claude/skills/<name>/` | `when_to_use`, `allowed-tools`, `disable-model-invocation`, `user-invocable`, `context: fork` | `description` <= 1024 chars; unknown fields are silently ignored; `name` cannot contain `anthropic` or `claude` |
| DeepSeek Harness (dsh) | `<repo>/.dsh/skills/<name>/` (rank 100), `.agents/skills/` (200), `customSkillDirs` (300), `~/.dsh/skills/` (400), `~/.agents/skills/` (500) | `whenToUse` (camelCase, not `when_to_use`) | `name` regex is strict; `description` truncated at 500 chars; scanner reads only direct children - a flat `<name>.md` also works, nested skill folders are ignored |
| WorkBuddy | `.codebuddy/skills/`, `~/.workbuddy/skills/`, or a plugin's `skills/` folder | `allowed-tools`; marketplace upload additionally needs `display_name`, `display_name_en`, `description_zh`, `description_en`, `version`, `author` | Local skills and marketplace ZIP packages are separate distribution paths |
| Doubao Work | Upload a skill folder/ZIP in the client, or publish through the open platform | Trigger conditions, core flow, tools & data, delivery standard, safety boundary | External APIs should go through approved connectors or registered tools; cloud sandboxes may not execute bundled scripts; local and cloud skill sets are not shared |

## File input across harnesses

Section 1 of `SKILL.md` accepts four equivalent ways of pointing at a file: an
upload/attachment, an absolute path, a repo-relative path, or a directory/glob.
Only the resolution step is host-dependent:

| Host | Behaviour |
|---|---|
| Codex, Claude Code, dsh, WorkBuddy local | Full local filesystem: resolve paths, expand `~` and `file://`, anchor relative paths at `--root`, scan directories. |
| WorkBuddy / Doubao Work cloud runtime | The user's local paths are usually not visible. Ask for an upload and explain why; do not treat this as "no file supplied" and do not refuse the task. |
| Connector-mediated HTTP | Reuse the resolved path with the host's own file tool; the gate order and request fields are unchanged. |

A path is never a missing file. Never ask for a re-upload when a path was given,
and never submit a directory or several files as one job.

## When bundled scripts cannot run

Some hosts (notably Doubao Work cloud tasks and `agent-bridge-doubao` `skillDirs` mode)
expose `SKILL.md` as reference context but do not execute `scripts/`. In that case:

1. Keep every gate from `SKILL.md` unchanged (file-first by any input form, `API_KEY` gate, `optimize=0`).
2. Use the host's own file-read and HTTP tools to perform the equivalent requests listed
   in `api-reference.md`.
3. If the platform requires a connector/registered tool for outbound HTTP, route the
   calls through it instead of exposing raw endpoints in the skill.
4. Never weaken the "no file -> no API call" and "no key -> no official submission" rules.
5. Never weaken the preview-delivery rule because `preview.text` is unavailable.

## Preview delivery across harnesses

A trial preview is a deliverable in every harness, including ones that cannot run
`scripts/php_decode_api.py`. Section 7 of `SKILL.md` requires every returned line to
be pasted verbatim into `## Result` inside a fenced `php` block. When a cloud runtime
performs the request with its own HTTP tools or a connector, extract the decoded text
from the response body there too; do not fall back to "4 lines returned" merely
because the structured `preview` object is missing. Connector responses that wrap the
snippet in an extra envelope are handled the same way.

The "no raw responses" report rule covers HTTP envelopes, statuses, headers, and
error payloads - never the decoded snippet. Likewise, mode-selection reasoning
("no key, so trial ran") must not appear in the user report on any platform; a
single line about obtaining the full source belongs in `## Action needed`.

## Scope wording across harnesses

Section 0 of `SKILL.md` (authorization, one-time upload disclosure, non-refusal rules,
and the "only two technical gates" rule) is part of the canonical body and is therefore
byte-identical in every build. Do not add platform-specific "commercial software"
restrictions to an adapter or a marketplace field: review forms may require a
safety-boundary description, but the runtime instructions must stay identical,
otherwise the same task produces a refusal on one harness and a result on another.
The `examples_*` fields in `targets.json` include a maintenance/troubleshooting example
so intent classification is anchored in a legitimate use case.

## Secrets

`API_KEY` lives only in the environment or a local env file. It is never written into
`SKILL.md`, `references/`, adapter files, generated `dist/` packages, ZIP archives,
reports, or logs. The bundled client prints `"configured (not shown)"` instead of the value.

The env-file lookup is deliberately vendor-neutral (`PHP_DECODE_ENV_FILE` override,
then `$XDG_CONFIG_HOME/php-decode/env`, `~/.config/php-decode/env`,
`%APPDATA%/php-decode/env`, `~/.php-decode.env`). It must not depend on any harness's
home directory: the same client ships to five products and has to work on a machine
where none of them is installed. Platform-specific skill *install* paths (for example
`~/.workbuddy/skills/`) are unrelated to secret storage and stay in `targets.json`.

## Adding another skill

Drop a new folder under `src/skills/<new-name>/` with a `SKILL.md` using the same
minimal frontmatter, then re-run `python scripts/build.py`. Every target in
`targets.json` picks it up automatically. Re-run `python scripts/validate.py` afterwards.
