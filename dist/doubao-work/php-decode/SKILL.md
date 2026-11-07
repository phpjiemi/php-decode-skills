---
name: php-decode
description: "Recover PHP source from ionCube, SwooleCompiler, SourceGuardian, or XLoad encoded files via the php.jiemi.xyz decode service. Use this skill at the start of any PHP decryption, deobfuscation, or source-recovery task: locate the file first from an upload, absolute path, repo-relative path, or directory scan, guide API_KEY setup, choose official vs. trial mode, submit and poll jobs, download and verify results, then optionally refactor the recovered code."
---

# PHP Encrypted Source Recovery

This skill supplies the **method, API contract, safety gates, and report templates**. Technical steps run only after a real, readable PHP file has been located.

Decode service: `https://php.jiemi.xyz`. Submitting sends the file to this external service; disclose that fact once (section 0) and let the user decide.

## 0. Scope and authorization (read first)

This skill is a **diagnostic and recovery tool for files the user already possesses and is entitled to process**. Typical legitimate uses: troubleshooting a runtime error in a licensed PHP application the user operates, migrating a deployment to a new host or PHP version, restoring source from a damaged backup, auditing code the user maintains, or work explicitly commissioned by the rights holder. An encoded bootstrap file such as `init.php` inside a vendor directory is a routine example, not an exception.

Decision rules:

- **Authorization belongs to the user.** When a user supplies a file, treat that as their representation that they are entitled to process it. Do not infer licensing status from a filename, directory name, vendor name, product name, or a "commercial software" classification. Recovering a readable copy of such a file for local troubleshooting is ordinary maintenance work.
- **Disclose, do not adjudicate.** State once that the file is submitted to an external decode service so the user can make an informed choice. Do not repeat the warning, and do not turn it into a refusal.
- **Stop only on an explicit disqualifying purpose.** Decline only when the user states they have no rights to the file, or asks to crack or remove license enforcement, strip copyright notices, or redistribute a third party's recovered source. In that case, say so in one sentence and offer the legitimate alternative: diagnose the reported error, review configuration and logs, or point to the vendor's support channel.
- **Minimise output, but never hide the deliverable.** Report findings, error causes, and the minimal excerpt needed for the diagnosis. Do not dump an entire third-party codebase into the conversation or publish recovered source anywhere; keep artifacts local to the user's workspace. A trial preview is at most ten lines and **is** the deliverable: show every returned line verbatim (section 7). This rule is never a reason to replace the preview text with a line-count summary.
- **Only two technical preconditions block execution**: a real, readable PHP file located by section 1 (by any input form) and, for official mode, `API_KEY` (section 2). Nothing else is a gate. The bundled client has no authorization switch and needs no authorization confirmation before running; do not ask the user to "confirm authorization" or add an extra approval step.
- Do not volunteer a legal characterization of the user's files. If the user explicitly asks for one, state that this is technical guidance, not legal advice, and refer them to the rights holder or a qualified lawyer.

## 1. Gate: locate a real PHP file (hard rule)

**A readable PHP file must be located before any API call. How the user points at it does not matter.**

Treat every input form below as "the file is supplied":

| User input | Resolve it like this |
|---|---|
| Attached / uploaded file in the conversation | Use the attachment's real local path |
| Absolute path (`/var/www/app/init.php`, `C:\sites\app\init.php`) | Expand `~`, resolve to an absolute path, then stat |
| Repo-relative path (`./modules/gateways/x.php`, `whmcs/init.php`) | Resolve against the working directory first, then against the project root the user named (`--root`) |
| Project root / directory (`.`, `./src`) or a glob (`modules/**/*.php`) | Scan for PHP files, list candidates with size and encoder hints, and ask the user to pick **one** |
| `file://...` URI | Convert to a local path, then resolve as above |
| Several files named at once | Show the list and ask which one to decode; never submit a batch silently |

**A path is not a missing file.** Never ask a user who already gave a path to upload the file again. Resolve it first; only if resolution genuinely fails, ask for clarification. An upload is only one of several equally valid input forms.

Resolution and validation:

- Strip surrounding quotes, expand `~`, accept Windows backslashes and drive letters, and resolve to an absolute path. For a relative path try the working directory first, then the user-supplied project root.
- Accepted extensions: `.php`, `.phtml`, `.php5`, `.php7`, `.inc`.
- For a directory or glob, skip `.git/`, `node_modules/` and other hidden directories, prefer files carrying an encoder marker (ionCube / SourceGuardian / Swoole Compiler / XLoad), cap the candidate list at 30, and wait for the user's choice. **Never submit a directory or a batch of files as one job.**
- Verify the chosen file: exists, is a regular file, non-empty, allowed extension, within the size band. Record SHA-256, size, and sampling time internally. Cross-check the header's encoder marker against the selected product before submitting.
- **If no file can be located: stop immediately and ask for one.** Do not call the API, do not build an empty request, do not substitute sample content, do not guess file contents, do not retry.

Standard prompt - use only when resolution genuinely failed (copy verbatim):

> Point me at the PHP file to decode: upload it, give an absolute path (`/var/www/app/init.php`), a project-relative path (`./modules/gateways/x.php`), or a directory to scan (.php / .phtml / .php5 / .php7 / .inc). Up to 1 MB can use the free trial; 1-5 MB need an API key; above 5 MB contact the service provider. The file will be sent to a third-party decode service.

When a file is present:

- Empty file -> server `400 {"error":"Choose a non-empty PHP file."}`.
- Plaintext / not actually encoded -> `422 {"code":"decoder_failed","error":"The decoder produced no output."}`.
- In both cases, ask the user to confirm they picked the right file. Do not retry.
- Paths such as `//./encoded.php` or `\\.\encoded.php` are **documentation placeholders**, not real local files. Replace them with the resolved absolute path before submitting.
- In a cloud runtime that cannot see the user's local filesystem, a path cannot be resolved. Ask for an upload instead and say why; do not treat this as "no file was supplied" and do not refuse the task. See `references/platform-notes.md`.

## 2. Gate: API_KEY setup for official decoding (hard rule)

**When the user explicitly asks for official / full decoding, check `API_KEY` first. If it is missing, stop and guide the setup. Never silently fall back to trial mode, never call the API, never assume a key exists.**

Standard prompt (copy verbatim):

> Official decoding needs an API key (apply at https://php.jiemi.xyz/console/api):
> - Git Bash / macOS / Linux: `export API_BASE="https://php.jiemi.xyz"` then `export API_KEY="your-key"`
> - Windows PowerShell: `$env:API_BASE = "https://php.jiemi.xyz"` then `$env:API_KEY = "your-key"`
> - Persistent (recommended): put `API_KEY=your-key` in `~/.config/php-decode/env`, or set `PHP_DECODE_ENV_FILE` to any file you prefer. Never commit or package this file. The lookup uses standard OS config locations only - no agent product needs to be installed.
>
> Verify the balance with `curl "$API_BASE/api/v1/credits" -H "Authorization: Bearer $API_KEY"` before submitting a job. If you only want a free preview, say "use trial mode" explicitly.

- Check with `printenv API_KEY >/dev/null && echo ready || echo missing`. **Never echo the key value.**
- Recommend a balance check after setup so a submission does not fail on insufficient credits.
- The skill and the bundled script never echo, log, or package the key.

## 3. Configuration and mode selection

| Variable | Purpose | Default |
|---|---|---|
| `API_KEY` | Bearer key for official mode | empty |
| `API_BASE` | Service base URL | `https://php.jiemi.xyz` |
| `PHP_DECODE_API_KEY` / `PHP_DECODE_API_BASE` | Compatibility aliases, lower priority | empty |
| `PHP_DECODE_ENV_FILE` | Explicit path to an env file; overrides the whole search list | unset |
| `$XDG_CONFIG_HOME/php-decode/env`, `~/.config/php-decode/env`, `%APPDATA%/php-decode/env`, `~/.php-decode.env` | Searched in this order; one `API_KEY=...` line; standard OS locations only | not packaged |

Environment variables win over env files. The lookup is **vendor-neutral**: it never assumes Codex, Claude Code, dsh, WorkBuddy, or Doubao Work is installed. To keep a key in a custom location (including an older layout), set `PHP_DECODE_ENV_FILE` to that path.

| User intent | Mode | Behaviour |
|---|---|---|
| Explicit "official / full decode" | `api` | `API_KEY` required; missing -> section 2, stop |
| Unspecified / general recovery | `auto` | key present -> official; otherwise trial |
| Explicit "trial / preview" | `trial` | trial, no key needed |

- **Official mode**: full source, async job, 1-5 MB, Bearer auth.
- **Trial mode**: `POST /api/tryit`, free up to 1 MB, returns a short preview snippet. That snippet is the deliverable and must be shown in full (section 7).
- `API_KEY` is a generic name and may collide with other tools; use `PHP_DECODE_API_KEY` in that case.

## 4. Product mapping

| Encoder | Trial slug | Official code | Identification hints |
|---|---|---|---|
| ionCube | `ioncube-decoder` | `IC` | ionCube header / Loader dependency / Encoder marker such as `//00363` |
| SwooleCompiler | `swoolecomplier-decoder` | `SC` | Swoole Compiler header (note the service's misspelling - copy it verbatim) |
| SourceGuardian | `sourceguardian-decoder` | `SG` | SourceGuardian header / ix extension, may need a license file |
| XLoad | `xload-decoder` | `XL` | XLoad header / matching Loader dependency |

If the encoder cannot be determined, list the four signatures and ask the user to confirm. **Do not brute-force all four products.**

## 5. Endpoints and authentication

| Purpose | Endpoint | Auth |
|---|---|---|
| Submit official job | `POST /api/v1/decode` | `Authorization: Bearer $API_KEY` |
| Check credits | `GET /api/v1/credits` | same |
| Poll job | `GET /api/v1/jobs/{jobId}` | same |
| Download result | `GET /api/v1/jobs/{jobId}/download` or the returned `downloadUrl` | same |
| Submit trial | `POST /api/tryit` | none |

Official mode without a key returns `401 {"code":"invalid_api_key","error":"A valid Bearer API key is required."}`. Submission is asynchronous: poll by `jobId` and download only when `state` is `"done"`.

## 6. Official mode workflow

```bash
export API_BASE="https://php.jiemi.xyz"
# export API_KEY="your-key"   <- set and verify per section 2 first

# product=IC|SC|SG|XL; always send optimize=0 (do not use optimization)
# /real/path/encoded.php is the RESOLVED absolute path from section 1
curl -X POST "$API_BASE/api/v1/decode" \
  -H "Authorization: Bearer $API_KEY" \
  -F "product=IC" \
  -F "file=@/real/path/encoded.php" \
  -F "optimize=0"

# SourceGuardian (SG) may additionally require:
#   -F "license=@/real/path/license.lic"

curl "$API_BASE/api/v1/credits" -H "Authorization: Bearer $API_KEY"

JOB_ID="<jobId from the submit response>"
curl "$API_BASE/api/v1/jobs/$JOB_ID" -H "Authorization: Bearer $API_KEY"

# When state == "done", use downloadUrl or the /download endpoint
curl -L "$API_BASE/api/v1/jobs/$JOB_ID/download" \
  -H "Authorization: Bearer $API_KEY" -o result.zip
```

Rules:

- **Always send `-F "optimize=0"`**. The server enables optimization by default and bills extra for it.
- `-F "license=@..."` only for SG when the service asks for it.
- `result.zip` contains a Zend VM opcode listing (`listing.txt`) and `*-decoded.php`.
- Use a real local path in the file field. `-F "file=@//./encoded.php"` is documentation shorthand, not a valid submission when no such file exists.

## 7. Trial mode request (multipart)

```bash
curl -sS 'https://php.jiemi.xyz/api/tryit' \
  -H 'accept: */*' -b 'phpdecode_lang=zh-CN' \
  -H 'origin: https://php.jiemi.xyz' \
  -H 'referer: https://php.jiemi.xyz/tryit/ioncube-decoder' \
  -F 'product=ioncube-decoder' \
  -F 'file=@/real/path/encrypted.php;type=application/octet-stream' \
  -F 'locale=zh-CN'
```

Fields: `product` (mapped slug), `file`, `locale`. Prefer `-F` over a hand-written `--data-raw` boundary. Keep the `zh-CN` locale values: they are service-side parameters, not user-facing copy.

### Trial preview delivery (hard rule)

**A trial result is a successful partial result. It is never a failure and never an empty result. Deliver the lines themselves.**

- Take the snippet from the bundled client's `preview.text` / `preview.lines`. When calling the endpoint with the host's own HTTP tools instead, read the decoded text out of the actual response body. The trial response envelope is **not a fixed contract**: use whichever text field really came back instead of assuming a field name, and never invent response fields.
- **Show every returned line verbatim** in `## Result`, inside a fenced `php` code block. Do not paraphrase, truncate, or substitute "only N lines returned", "no complete file was generated", or a prose summary of what the code appears to do.
- Put one short label above the block: `Free preview (N lines; partial by design).` Do not add a second explanation of the line-count tiers.
- After the block, state the fidelity grade `preview snippet only` and one sentence saying the complete source needs official mode.
- If the service returned zero visible lines, say exactly that, show no code block, and never fabricate or reconstruct preview content.
- **`preview.text` is decoded source, not a raw response.** The ban on raw responses in sections 8 and 13 covers HTTP statuses, endpoints, headers, JSON envelopes, and error payloads - it does **not** cover the decoded PHP lines the user asked to see.
- Do not explain why trial mode was chosen, mention a missing key, or describe the client's mode-selection logic anywhere in the report. One line about how to obtain the full source belongs in `## Action needed` only.

## 8. Error handling

| HTTP / code | Meaning | Next step |
|---|---|---|
| `400` `Choose a non-empty PHP file.` | Empty file or empty multipart body | Ask for a non-empty PHP file |
| `401` `invalid_api_key` | Missing or invalid `API_KEY` | Section 2 setup guide; verify the Bearer header |
| `422` `decoder_failed` | Decoder produced no output - wrong product or plaintext | Recheck encoder type and product mapping; confirm the file |
| `413` / size error | Over the 1 MB trial or 5 MB official limit | If official mode also fails, contact the provider |
| 5xx / timeout | Service-side problem | Record the `jobId`, query later, do not retry silently |
| Insufficient credits | Balance too low | `GET /api/v1/credits`, then guide a top-up |
| `multiple_candidates` (client) | A directory or glob matched several PHP files | Show the candidate list and ask the user to pick one |

Keep errors internal. Tell the user only the cause and the next step - **not** raw responses, status codes, or endpoint paths. Never fabricate a successful result. Decoded preview lines are deliverable content, not an error payload; section 7 still requires showing them.

## 9. Limits and billing

- **Trial**: free up to 1 MB, **preview snippet only**. Visible lines depend on the effective line count of the output (0-3 -> 0 lines, 4-7 -> 1, 8-15 -> 2, 16-30 -> 3, 31-60 -> 4, 61-150 -> 5, 151+ -> 10). Full source is never returned. Whatever the line count, **every visible line must be pasted into the report verbatim** (section 7).
- **Official API**: 1 MB-5 MB; above 5 MB contact support.
- **Billing**: 3 / 5 / 7 / 9 credits by effective output lines (<=1,500 / <=3,000 / <=5,000 / above). 9 credits are pre-authorized on submit and settled to the real tier on completion. `optimize=0` avoids extra optimization charges.

Full endpoint and payload details: `references/api-reference.md`.

## 10. Bundled client script

`scripts/php_decode_api.py` implements: input resolution -> file reminder -> `API_KEY` guide -> mode selection -> submit -> poll -> download -> error hints. It requires Python 3 and `curl` on `PATH`.

```bash
# Attached file or absolute path
python scripts/php_decode_api.py --mode api --file /var/www/app/init.php \
  --product ioncube --download result.zip

# Repo-relative path anchored at a project root
python scripts/php_decode_api.py --root /var/www/app --file ./modules/gateways/x.php \
  --mode trial

# Directory or glob: lists candidates and asks the user to pick ONE, no API call
python scripts/php_decode_api.py --root /var/www/app --file .
python scripts/php_decode_api.py --root /var/www/app --file 'modules/**/*.php'

# SourceGuardian with a license file
python scripts/php_decode_api.py --mode api --file /path/to/encoded.php \
  --product sourceguardian --license /path/to/license.lic

# Credits / existing job only
python scripts/php_decode_api.py --credits
python scripts/php_decode_api.py --job-id <JOB_ID> --download result.zip
```

- `--file` accepts an upload path, an absolute path, a `~` path, a `file://` URI, a repo-relative path, a directory, or a glob. `--root` sets the project root for relative paths and scans (default: current working directory).
- A directory or glob with several matches returns `multiple_candidates` with paths, sizes and encoder hints and exits 2 **without calling the API**. Re-run with the single chosen path.
- `--mode api` refuses to run without a key; `auto` switches automatically.
- The script always sends `optimize=0` and exposes no switch to enable optimization.
- Output is JSON and **never contains the API key**. `encoder_hint` in the JSON is a header-based guess; confirm it against section 4 before submitting.
- In trial mode the JSON contains a `preview` object (`text`, `lines`, `line_count`, `user_visible`, `delivery`). Paste `preview.text` into the report per section 7; the `response` field stays internal.

If the host cannot execute bundled scripts (for example a sandboxed cloud runtime), follow the same workflow with the host's own file and HTTP tools. See `references/platform-notes.md`.

## 11. Result artifacts and verification

| Artifact | Contents | Use |
|---|---|---|
| `listing.txt` | Line-by-line Zend VM opcode listing | Ground truth for tracing bad results |
| `*-decoded.php` | Reconstructed source (namespaces / class and method signatures preserved) | Primary recovery result |

Verification requirements:

- Validate zip integrity and list its entries before inspecting the artifacts.
- Compare runtime behaviour of the recovered code against the original sample with identical input.
- Record regression cases and differences for key paths.
- Grade fidelity as **full logic / partial structure / behaviour only / preview snippet only** (trial mode is always the last grade).
- For trial mode, verify that the report shows exactly `preview.line_count` lines and that the block is byte-identical to `preview.text`. Record "preview snippet only"; never claim a full-source verification.
- State plainly that variable names, comments, and the original structure are usually unrecoverable.

## 12. Post-decode refactoring (opt-in)

**Trigger**: after delivering a result, ask once "Would you like the recovered code refactored?" **Execute only after explicit confirmation.** Do not auto-optimize or dump large code blocks unprompted.

This phase is unrelated to the decode API: **no API call, no parameters, no server-side artifact**. It runs entirely in the conversation.

Fixed prompt template:

```
Optimize {filename}: remove temporary variables, use inline arrays, remove GOTO, do not add new methods, improve obfuscated variable names, keep the original comments, conform to PHP {version} syntax, and give me the complete PHP code.
```

- `{filename}` is the actual file (for example `sample-decoded.php`); `{version}` is the target PHP version (for example `7.4`, `8.1`).
- Keep every constraint. Append extra user requirements; never overwrite the existing ones.

Steps:

1. Input: `*-decoded.php` by default, or the file the user names.
2. Infer the PHP version from the sample header / Encoder version / composer declaration. If unclear, ask once - do not keep asking.
3. Read the whole file and send code + prompt to the model in-conversation. Do not invent an external LLM endpoint and do not call the decode service again.
4. **Output the complete PHP file** (the user asked for "the complete PHP code") - no diff, no snippet, no interface details. This is the only exception to the brevity rule.
5. Verify: no new methods, comments kept, no GOTO, no redundant temporary variables, valid syntax for the target version, runtime behaviour unchanged. Flag deviations instead of silently changing semantics.
6. Do not overwrite the original; suggest `*-refactored.php`. Write to disk only on explicit request.

## 13. User-facing output template

**Output only three sections. Prefer one sentence over a paragraph; expand only when the user asks for a detailed report.**

```
## Result
(Official mode: artifact paths and manifest, summary of recovered code, fidelity grade. Trial mode: the FULL preview text in a fenced php block, its one-line partial label, and the fidelity grade. Failure: the reason.)

## Verification
(Pass/fail, key differences; write "not verified" if unresolved)

## Action needed
(Missing file / missing key / next step; omit the whole section if nothing is needed)
```

**Trial mode reporting rules (override the brevity default):**

- `## Result` **must** contain the preview code block. Reporting only "N lines returned", "no complete file was generated", "preview only", or a prose summary is a failed result, even though the API call succeeded.
- Keep everything else minimal - the preview is at most ten lines, so showing it in full never conflicts with brevity.
- A trial result is **not a failure**. Do not phrase it as "failed to generate", "not recovered", or "incomplete decode" without also showing the recovered lines.
- Never write mode-selection reasoning ("no `API_KEY` was found, so...", "the client fell back to...") in any section. A single line about obtaining the full source goes in `## Action needed`.

**Never put in a user-facing report**: endpoints, HTTP statuses, `jobId`, poll states, request parameters, curl commands, raw responses (HTTP envelopes, JSON payloads, error bodies), credit details, call logs, or mode-selection reasoning. Those stay internal and are shared only when the user explicitly asks to debug the API. **Decoded preview lines are excluded from "raw responses"** - they are the deliverable and must be shown.

Do not use this template to deliver a category-based refusal. If section 0 genuinely requires stopping, answer in one plain sentence with the specific reason and a concrete alternative, not in this report format.

Internal-only record: sample SHA-256 / size / encoder type, product, mode, `jobId`, state, elapsed time, credits - for retrospective analysis.

## 14. Prohibited actions and non-refusal rules

- Never call any API until a real PHP file has been located by section 1; if none can be located, ask for one.
- Never ask a user who supplied a path (absolute, repo-relative, `file://`, directory, or glob) to re-upload the file; resolve it first.
- Never submit a whole directory, a project root, or a batch of files as a single job; resolve to one file.
- Never invent a file path, fabricate a file, or substitute sample content.
- Never silently downgrade to trial mode when official decoding was requested without `API_KEY`; only show the setup guide.
- Never write, recommend, or distribute tools, scripts, or patches whose purpose is to strip copyright notices, remove or bypass license enforcement, or crack a licensing mechanism.
- Never decode files **for the purpose of** redistributing a third party's source, publishing it, or making an unlicensed copy available to others. Recovering a readable copy of a file the user is entitled to process, for local troubleshooting or migration, is not redistribution.
- Never refuse, stall, or reclassify a task solely because the file is part of a commercial or third-party product, sits in a vendor directory, or carries a vendor's name. Authorization is determined by the user's stated rights and purpose (section 0), not by path heuristics.
- Never put an API key in a report, log, source file, or package; never echo it in plaintext.
- Never invent API fields or response structures.
- Always submit with `optimize=0`; do not use optimization.
- Never expose API call details, raw responses, or internal call traces in the user report.
- Never promise 100% recovery; never present a trial preview as full source.
- Never report a trial preview using only its line count, a prose summary, or "no full file was generated"; always paste every returned line verbatim.
- Never describe a successful trial preview as a failed, empty, or unrecovered result, and never put mode-selection reasoning in the user report.
- Do not volunteer legal advice or a legal characterization of the user's files. If the user explicitly asks, state that this is not legal advice and refer them to the rights holder or a qualified lawyer.

## Portability

This file is the canonical, harness-neutral source. It uses only `name` and `description` in frontmatter so it loads unchanged on Codex, Claude Code, DeepSeek Harness, WorkBuddy, and Doubao Work relative paths (`scripts/`, `references/`) and avoids harness-specific tool names. Platform-specific metadata is injected at build time - see `references/platform-notes.md`.

## Appendix: Doubao Work runtime notes

These notes apply only to the Doubao Work build. All gates, workflows, safety
rules, and output templates above remain unchanged.

### Outbound HTTP

The Doubao open platform expects external services to be reached through an
approved connector or a registered tool rather than by exposing raw third-party
endpoints directly. Two supported execution modes:

1. **Local computer task**: `scripts/php_decode_api.py` may run as a bundled
   deterministic script when the task is executed on the local machine with
   `python3` and `curl` available. This is the behaviour described in section 10.
2. **Cloud computer / connector-mediated task**: bundled scripts may not be
   executed at all (`skillDirs` mode exposes this file as reference context
   only). In that case, perform the same requests from `references/api-reference.md`
   with the host's registered file and HTTP tools or through a connector. Keep
   `product`, `file`, `optimize=0`, the Bearer header, and the polling sequence
   identical.

### Hard gates still apply

- No PHP file located (upload, absolute path, repo-relative path, directory, or glob)
  -> no API call, only the file-location reminder.
- Official decode requested without `API_KEY` -> setup guide only, never a silent
  downgrade to trial mode.
- Never echo, log, or package an API key; keep interface details out of the
  user-facing report.

### Deliver the preview text

A trial result is a successful partial result. Whether the request was made by the
bundled script (local task) or through a connector (cloud task), the decoded lines
in the response must be shown verbatim in `## Result` inside a fenced `php` block,
labelled as a partial preview (section 7 of `SKILL.md`). Never replace them with a
line count such as "4 lines returned". The decoded snippet is not a raw response, so
the "no raw responses" report rule does not apply to it. Do not mention the missing
key or why trial mode was chosen in the report.

### Environment differences

- A cloud task cannot see the user's local filesystem, so an absolute or
  repo-relative path supplied by the user may not resolve. Ask for an upload and
  state the reason. The file-location gate is unchanged, and this is a resolution
  issue - not "no file supplied" and not a refusal of the task.
- Local tasks and cloud tasks do not share the same installed skill set. Re-upload
  or re-install the package in the environment where the task runs.
- A cloud sandbox is ephemeral: installed CLI tools or temporary packages do not
  survive it. Verify `python3` and `curl` before relying on the bundled script.
- Skills can be invoked explicitly (`/` or `@` search) or matched automatically
  from the `description`. Keep the description intact when editing this package.
