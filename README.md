# php-decode-skills

A **write-once, run-anywhere** Agent Skills package for PHP encrypted-source recovery.
One canonical English skill is compiled into installable packages for five agent
harnesses:

| # | Harness | Build output | Discovery path |
|---|---|---|---|
| 1 | OpenAI Codex CLI | `dist/codex/<skill>/` | `<repo>/.agents/skills/<skill>/` or `~/.agents/skills/<skill>/` |
| 2 | Claude Code | `dist/claude-code/<skill>/` | `.claude/skills/<skill>/` or `~/.claude/skills/<skill>/` |
| 3 | DeepSeek Harness (dsh) | `dist/deepseek-harness/<skill>/` | `<repo>/.dsh/skills/<skill>/` or `~/.dsh/skills/<skill>/` |
| 4 | WorkBuddy | `dist/workbuddy/<skill>/`, `dist/workbuddy-marketplace/<skill>.zip` | `.codebuddy/skills/`, `~/.workbuddy/skills/`, plugin `skills/`, or marketplace ZIP |
| 5 | Doubao Work | `dist/doubao-work/<skill>/` + `.zip` | Client skill upload or open-platform package |

The bundled skill, `php-decode`, is an English rewrite of the reference skill `ioncube-analysis` at
`~/.workbuddy/plugins/marketplaces/my-experts/plugins/php-decode-expert/skills/ioncube-analysis`.
It covers ionCube, SwooleCompiler, SourceGuardian, and XLoad via the
`https://php.jiemi.xyz` decode service. The file gate accepts an upload, an absolute
path, a repo-relative path, or a directory scan; the rest covers the `API_KEY` gate,
official/trial mode selection, job polling, result verification, optional refactoring,
and the three-section report template.

> **Scope:** use on files you are entitled to process - troubleshooting, migration,
> backup restoration, and maintenance of deployments you operate. The skill does not
> cover bypassing license enforcement, stripping copyright notices, or redistributing
> third-party source. A product or directory name alone is never treated as a licensing
> decision; see section 0 of `SKILL.md`. This is not legal advice.

## Why a single source

All five harnesses implement the open [Agent Skills](https://skill.md/) format: a
folder with `SKILL.md` (YAML frontmatter + Markdown instructions) plus optional
`scripts/`, `references/`, and `assets/`. They differ only in **where** they look for
the folder, **which extra frontmatter fields** they understand, and **what they allow
at runtime**. So the instructions live in exactly one place and a small build step
injects platform metadata:

```
src/skills/<skill>/SKILL.md   ── canonical (name + description only)
          │
          ├── scripts/build.py ──> dist/<target>/<skill>/SKILL.md (frontmatter injected)
          ├── scripts/validate.py ─ checks every generated package
          └── scripts/install.py  ─ copies/symlinks into local discovery dirs
```

The canonical file deliberately satisfies the **strictest common denominator**:

- `name` matches `^[a-z0-9]+(-[a-z0-9]+)*$` and equals the folder name (required by
  DeepSeek Harness; also avoids Claude's reserved words `anthropic` / `claude`).
- `description` is under 500 characters, states both *what* and *when*, and front-loads
  trigger words (DeepSeek Harness truncates at 500, Codex budgets ~2% of context for
  the whole skill list, Claude allows 1024).
- Frontmatter contains only `name` and `description`. Other clients ignore unknown
  fields, but a minimal header can never break a strict parser.
- The body uses harness-neutral verbs and relative paths, never a client-specific tool
  name.

## Versioning

The single source of truth is the top-level `version` field in `targets.json`
(initial release: `0.1.0`). `build.py` injects it into the WorkBuddy marketplace
`SKILL.md` frontmatter and expands `{{version}}` inside adapter files such as
`PACKAGE.md`; `validate.py` fails the build if any generated file still carries an
unresolved placeholder. To bump the release, change that one field and rebuild -
never hand-edit `dist/`.

## Quick start

Requires Python 3.9+ (standard library only). The bundled client additionally needs
`python3` and `curl` on `PATH` at runtime.

```bash
python scripts/build.py        # generate dist/ for all 6 targets (5 harnesses + marketplace variant)
python scripts/validate.py     # verify frontmatter, resource parity, script syntax, ZIP contents
python scripts/install.py      # dry-run: preview where each package would be installed
python scripts/install.py --scope user --apply   # actually install user-level skills
```

Useful variants:

```bash
python scripts/build.py --target codex --target deepseek-harness
python scripts/install.py --target claude-code --scope project --repo /path/to/repo --apply
python scripts/install.py --target codex --scope user --apply --link   # symlink instead of copy
python scripts/build.py --clean
```

`install.py` never writes anything unless `--apply` is passed, and it never deletes
existing files. Targets without a local discovery path (Doubao Work, WorkBuddy
marketplace) print manual upload instructions instead.

## Repository layout

```
php-decode-skills/
├── README.md                     # this file (English)
├── AGENTS.md                     # repo-level guidance for Codex / dsh
├── targets.json                  # machine-readable per-harness profile
├── src/skills/
│   └── php-decode/
│       ├── SKILL.md              # canonical English skill (sections 0-14 + portability)
│       ├── scripts/php_decode_api.py   # portable client: gates, submit, poll, download
│       └── references/
│           ├── api-reference.md       # endpoints, fields, errors, billing, artifacts
│           └── platform-notes.md      # portability rules and fallback behaviour
├── adapters/
│   ├── codex/agents/openai.yaml  # Codex UI metadata + invocation policy
│   ├── codex/AGENTS.md.snippet
│   ├── claude-code/CLAUDE.md.snippet
│   └── doubao-work/            # runtime appendix, upload notes, icon
├── scripts/
│   ├── build.py                  # canonical -> dist
│   ├── validate.py               # lint every generated package
│   └── install.py                # dry-run / copy / symlink installer
└── dist/                         # generated, directly installable
    ├── codex/<skill>/
    ├── claude-code/<skill>/
    ├── deepseek-harness/<skill>/
    ├── workbuddy/<skill>/
    ├── workbuddy-marketplace/<skill>/ + <skill>.zip
    ├── doubao-work/<skill>/ + <skill>.zip
    └── guides/                   # optional AGENTS.md / CLAUDE.md merge snippets
```

## Per-harness notes

### OpenAI Codex CLI

- Skills are discovered in `.agents/skills` from the working directory up to the repo
  root, `$HOME/.agents/skills`, and `/etc/codex/skills`. Many existing installations
  also carry `~/.codex/skills/` - the target exposes it as `legacy_user`.
- The generated package includes `agents/openai.yaml` with `interface` metadata and
  `policy.allow_implicit_invocation: true`. Enable/disable individual skills in
  `~/.codex/config.toml` via `[[skills.config]]`.
- `AGENTS.md` is for persistent repo rules, not for the skill body. A merge-ready
  snippet is emitted at `dist/guides/codex.md`.

### Claude Code

- Install to `.claude/skills/<skill>/` (project) or `~/.claude/skills/<skill>/` (user),
  or ship it inside a plugin.
- Injected fields: `when_to_use`, `allowed-tools: Read, Grep, Bash`,
  `user-invocable: true`. Tighten `allowed-tools` if you do not want pre-approved
  shell access. `context: fork`, `model`, `effort`, and hooks are intentionally not
  set - they change execution semantics and are not portable.
- A merge-ready snippet is emitted at `dist/guides/claude-code.md`.

### DeepSeek Harness (dsh)

- Discovery ranks: `.dsh/skills` (100) > `.agents/skills` (200) > `customSkillDirs`
  (300) > `~/.dsh/skills` (400) > `~/.agents/skills` (500). A higher-priority copy
  silently wins on name collision.
- The generated frontmatter uses camelCase `whenToUse` (not Claude's `when_to_use`).
  `name` is strict kebab-case and must equal the folder name; `description` is kept
  under 500 characters.
- The scanner reads only direct children: keep the skill folder directly under the
  skills directory. A flat `<name>.md` also works if you prefer a single file.

### WorkBuddy

- **Local**: `.codebuddy/skills/<skill>/`, `~/.workbuddy/skills/<skill>/`, or a plugin's
  `skills/` directory. Only `name` + `description` are required; `allowed-tools` is
  added by the build.
- **Marketplace**: `dist/workbuddy-marketplace/<skill>.zip` carries the extra required
  fields (`display_name`, `display_name_en`, `description_zh`, `description_en`,
  `version`, `author`) plus examples and `allowed-tools`. These are the only
  Chinese-language strings in the generated frontmatter, and they exist solely because
  the upload form requires them.
- Skill *install* paths are WorkBuddy-specific, but secret storage is not: the client
  only reads standard OS config locations, so one key works on a machine where no
  agent harness is installed.

### Doubao Work

- Upload the folder or the ZIP in the client (Skills > Add > Upload); the ZIP root
  contains the `<skill>/` folder with `SKILL.md`, `scripts/`, and `references/`.
  `PACKAGE.md` lists the name / summary / icon / version values for the upload form.
- The open platform expects external services to be reached through approved
  connectors or registered tools, and cloud sandboxes may not execute bundled scripts
  at all (`skillDirs` mode exposes the skill as reference context only). The generated
  `SKILL.md` therefore carries an extra appendix describing the tool-based fallback
  while keeping every gate and the exact request fields unchanged.
- Local and cloud skill sets are not shared; install the package in the environment
  where the task runs.

## Configuration at runtime

| Variable | Purpose | Default |
|---|---|---|
| `API_KEY` | Bearer key for official decoding | unset |
| `API_BASE` | Service base URL | `https://php.jiemi.xyz` |
| `PHP_DECODE_API_KEY` / `PHP_DECODE_API_BASE` | Aliases with lower priority | unset |
| `PHP_DECODE_ENV_FILE` | Explicit env-file path, overrides the search list | unset |

`API_KEY` in the environment wins. Otherwise the client searches, in order:
`$XDG_CONFIG_HOME/php-decode/env`, `~/.config/php-decode/env`,
`%APPDATA%/php-decode/env` (Windows), `~/.php-decode.env`. Set
`PHP_DECODE_ENV_FILE` to override the entire list. **No agent-specific directory is
used** - installing WorkBuddy, Codex, Claude Code, dsh or Doubao Work is not a
prerequisite; a key kept in an older or custom location is reached via
`PHP_DECODE_ENV_FILE`.

The client never prints, logs, or packages the key, always sends `optimize=0`, and
refuses to call the API until a real PHP file has been located. Official mode without
a key stops with a setup guide instead of silently downgrading to trial mode.

In trial mode the client extracts the returned snippet into a `preview` object
(`text`, `lines`, `line_count`, `user_visible`, `delivery`). **Those decoded lines
are the deliverable**: the skill requires every line to be pasted verbatim into the
result report, not summarized as "N lines returned". The `response` field stays
internal; the decoded snippet is explicitly not a raw response.

## File input forms

`--file` accepts any of these; none is treated as "no file supplied":

| Input | Example |
|---|---|
| Attached / uploaded file | the attachment's local path |
| Absolute path | `/var/www/app/init.php`, `C:\sites\app\init.php` |
| `~` path or `file://` URI | `~/projects/app/init.php` |
| Repo-relative path | `--root /var/www/app --file ./modules/gateways/x.php` |
| Directory / project root | `--root /var/www/app --file .` |
| Glob | `--root /var/www/app --file 'modules/**/*.php'` |

Relative paths resolve against the working directory first, then `--root`. A
directory or glob matching several PHP files returns `multiple_candidates` (paths,
sizes, encoder hints) and exits 2 **without an API call** - pick one and re-run. In a
cloud runtime with no access to the user's filesystem, ask for an upload instead and
say why; that is a resolution issue, not a refusal.

## Adding another skill

1. Create `src/skills/<new-name>/SKILL.md` with `name` (equal to the folder name) and
   a `description` under 500 characters.
2. Add `scripts/` and `references/` resources as needed; use relative paths in the body.
3. Run `python scripts/build.py && python scripts/validate.py`.

Every target in `targets.json` picks up the new skill automatically. To add a sixth
harness, append a target object with its `dist`, `frontmatter`, `extra_files`, and
`install` map - no change to the canonical skill is needed.

## Verification

`python scripts/validate.py` checks, for every generated package: frontmatter position
and shape, name regex and reserved words, description length and tag safety, presence
of all platform-specific fields, byte-identical bundled resources, Python syntax,
adapter files, and ZIP contents. Run it after every edit to `src/` or `targets.json`.
