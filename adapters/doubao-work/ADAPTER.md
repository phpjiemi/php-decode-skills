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
