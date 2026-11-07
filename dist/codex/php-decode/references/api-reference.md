# Decode API Reference

Supplemental detail for `SKILL.md`. Load this file only when you need exact endpoints,
fields, or billing rules. All values below describe the third-party service
`https://php.jiemi.xyz`; do not invent fields that are not listed here.

## Authentication

- Official mode: `Authorization: Bearer $API_KEY` on every `/api/v1/*` request.
- Trial mode: no authentication.
- Missing or invalid key: `401 {"code":"invalid_api_key","error":"A valid Bearer API key is required."}`
- Keys are issued at `https://php.jiemi.xyz/console/api`.
- Never echo, log, or package the key. Check presence with
  `printenv API_KEY >/dev/null && echo ready || echo missing`.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `API_KEY` | Bearer key (official mode) | empty |
| `API_BASE` | Service base URL | `https://php.jiemi.xyz` |
| `PHP_DECODE_API_KEY` | Alias, lower priority than `API_KEY` | empty |
| `PHP_DECODE_API_BASE` | Alias, lower priority than `API_BASE` | empty |
| `PHP_DECODE_ENV_FILE` | Explicit env-file path, overrides the search list | unset |

Env file search order (first match wins, one `NAME=value` line per key). Only standard
OS config locations are used; **no agent-product home directory is assumed**:

1. `$PHP_DECODE_ENV_FILE` - explicit override, replaces this whole list
2. `$XDG_CONFIG_HOME/php-decode/env` (when `XDG_CONFIG_HOME` is set)
3. `~/.config/php-decode/env` (XDG default)
4. `%APPDATA%/php-decode/env` (Windows native config, when `APPDATA` is set)
5. `~/.php-decode.env` (plain dotfile)

`API_KEY` / `PHP_DECODE_API_KEY` in the environment always take priority over any
file. If a key already lives in an agent-specific or otherwise custom location, point
`PHP_DECODE_ENV_FILE` at it - do not add product-specific paths to the client.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/decode` | Bearer | Submit an official async job |
| GET | `/api/v1/credits` | Bearer | Query remaining credits |
| GET | `/api/v1/jobs/{jobId}` | Bearer | Poll job state |
| GET | `/api/v1/jobs/{jobId}/download` | Bearer | Download the result package |
| POST | `/api/tryit` | none | Submit a free trial |

## Official submit fields (multipart/form-data)

| Field | Value | Notes |
|---|---|---|
| `product` | `IC` / `SC` / `SG` / `XL` | Official product code |
| `file` | `@<real local path>` | The resolved local PHP file (SKILL.md section 1) |
| `optimize` | `0` | **Mandatory.** Server default enables billable optimization |
| `license` | `@<real local path>` | Optional; SourceGuardian only, when the service requests it |

Response: a JSON object containing a job id (`jobId` / `job_id` / `id` / `taskId` / `task_id`).
Poll `GET /api/v1/jobs/{jobId}` until `state == "done"`, then use the returned
`downloadUrl` (or `resultUrl` / `download_url` / `result_url`) or the `/download` endpoint.

Terminal states handled by the bundled script: `done`, `completed`, `succeeded`,
`success`, `failed`, `error`, `cancelled`, `canceled`.

## Trial submit fields (multipart/form-data)

| Field | Value | Notes |
|---|---|---|
| `product` | Trial slug (see mapping) | Service-side spelling must be copied verbatim |
| `file` | `@<real local path>;type=application/octet-stream` | The resolved local PHP file (SKILL.md section 1) |
| `locale` | `zh-CN` | Service-side locale, not user-facing copy |

Common trial headers: `accept: */*`, cookie `phpdecode_lang=zh-CN`,
`origin: https://php.jiemi.xyz`, `referer: https://php.jiemi.xyz/tryit/<slug>`.

## Trial response and preview delivery

The trial response envelope is **not a published, stable contract**. Do not assert a
fixed field name: read whichever string field (or plain-text body) actually carries
the decoded lines. The bundled client's `extract_preview()` implements this
defensively - candidate keys first, then a bounded scan for the most PHP-like
string - and exposes a `preview` object with `text`, `lines`, `line_count`,
`user_visible`, and `delivery`. This is parsing of what was returned, not an
invented API schema.

Delivery requirements (see "Trial preview delivery" in `SKILL.md` section 7):

- Every visible line goes into `## Result` verbatim in a fenced `php` block, with a
  one-line label marking it as a partial preview. A four-line preview is a four-line
  deliverable, not a failed decode.
- Never replace the snippet with its line count, a prose summary, or "no complete
  file was generated".
- Zero visible lines: say so, show no code block, never fabricate content.
- The decoded snippet is **not** a raw response. HTTP statuses, headers, JSON
  envelopes and error payloads stay internal.
- Do not explain the missing key or the mode choice in the report; one line about
  obtaining the full source belongs in `## Action needed`.

## Product mapping

| Encoder | Trial slug | Official code | Notes |
|---|---|---|---|
| ionCube | `ioncube-decoder` | `IC` | ionCube header / Loader dependency / `//00363`-style markers |
| SwooleCompiler | `swoolecomplier-decoder` | `SC` | The service misspells "compiler"; do not "fix" it |
| SourceGuardian | `sourceguardian-decoder` | `SG` | May require a `license` file |
| XLoad | `xload-decoder` | `XL` | Matching Loader dependency |

## Errors

| HTTP / code | Meaning | Action |
|---|---|---|
| `400` `Choose a non-empty PHP file.` | Empty file or empty multipart body | Request a non-empty PHP file, do not retry |
| `401` `invalid_api_key` | Missing/invalid key | Guide `API_KEY` setup, verify Bearer header |
| `422` `decoder_failed` | No decoder output (wrong product or plaintext) | Recheck encoder and mapping, confirm the file |
| `413` / size error | Over 1 MB trial / 5 MB official | Official mode only, else contact provider |
| 5xx / timeout | Service fault | Keep `jobId`, query later, no silent retry |
| Insufficient credits | Balance too low | Check `/api/v1/credits`, guide top-up |

## Limits and billing

- Trial: <= 1 MB, free, **preview only**. Visible effective lines: 0-3 -> 0, 4-7 -> 1,
  8-15 -> 2, 16-30 -> 3, 31-60 -> 4, 61-150 -> 5, 151+ -> 10.
- Official: 1 MB-5 MB. Above 5 MB: contact support.
- Credits by effective output lines: 3 (<=1,500), 5 (<=3,000), 7 (<=5,000), 9 (above).
  9 credits are pre-authorized and the difference is refunded after settlement.
- `optimize=0` prevents extra optimization charges.

## Result package

`result.zip` contains:

- `listing.txt` - Zend VM opcode listing, the ground truth for tracing bad output.
- `*-decoded.php` - reconstructed source, namespaces / class and method signatures preserved.

Validation: check zip integrity and entry list first; compare runtime behaviour with the
original sample under identical input; record regression cases and differences; grade
fidelity as full logic / partial structure / behaviour only / preview snippet only.
Variable names, comments, and original structure are usually unrecoverable - say so.

## File input resolution

The `file` multipart field must carry the absolute path resolved by section 1 of
`SKILL.md`, whether the user supplied an attachment, an absolute path, a
repo-relative path, or a directory/glob narrowed down to one file. Never send a
directory or several files in a single request; the bundled client reports those
as `multiple_candidates` before any HTTP call.

## Scope and safety boundary

This reference documents the decode-service contract for files the user is entitled to
process (troubleshooting, migration, backup restoration, maintenance). It does not cover
cracking license enforcement, removing copyright notices, or redistributing a third
party's recovered source. A file's presence in a commercial product or vendor directory
is not by itself a reason to withhold routine recovery or diagnostics - see
"Scope and authorization" in `SKILL.md`. This is technical guidance, not legal advice.
