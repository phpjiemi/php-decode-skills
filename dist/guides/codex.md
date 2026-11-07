# OpenAI Codex CLI - repo guidance snippet

Merge the text below into the project's instruction file.

---

## PHP decode skill

A reusable skill named `php-decode` is available in `.agents/skills/`.
Use it at the start of any PHP decryption, deobfuscation, or encrypted-source
recovery request - before running commands. It enforces two hard gates: no API
call until a real PHP file is located (upload, absolute path, repo-relative path,
directory scan, or glob - resolve it with `--root`), and no official decode without
`API_KEY`. Load its `SKILL.md` for the full workflow; implement it with the bundled
`scripts/php_decode_api.py` when `python3` and `curl` are available.

When a trial preview is returned, paste every decoded line from the client's
`preview.text` into the result report; a line-count summary is not a result.

Do not put API keys inside this repository or any skill file.
