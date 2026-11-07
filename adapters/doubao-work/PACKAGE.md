# Doubao Work Package Notes

Advisory notes for uploading/publishing this skill. They are not an officially
specified manifest - fill the equivalent fields in the client upload form or the
open-platform console.

| Form field | Value |
|---|---|
| Name | `php-decode` |
| Display name | PHP Encrypted Source Recovery |
| Summary | Recover PHP source from ionCube, SwooleCompiler, SourceGuardian, or XLoad encoded files through a gated submit / poll / verify workflow. |
| Version | `{{version}}` |
| Icon | `assets/icon.svg` |
| Entry | `SKILL.md` |
| Trigger | PHP decryption, deobfuscation, encoded source recovery, ionCube / SwooleCompiler / SourceGuardian / XLoad, or a PHP file given by absolute / repo-relative path, directory, or glob |
| Non-trigger | General PHP refactoring, plaintext PHP cleanup, license-enforcement bypass, copyright removal, redistribution of third-party source |

`Version` is injected from the top-level `version` in `targets.json` at build time.
Edit it there, never in this file's generated copy under `dist/`.

## Package layout

```
php-decode/
├── SKILL.md              # metadata + core flow + safety boundaries
├── PACKAGE.md            # this file (upload-form reference)
├── assets/icon.svg       # icon candidate
├── scripts/
│   └── php_decode_api.py # deterministic client (local tasks only)
└── references/
    ├── api-reference.md
    └── platform-notes.md
```

Zip the **parent** of `php-decode/` so the archive root contains the
`php-decode/` folder, matching the open platform's `{skill-name}/` layout.

## Review checklist

- `SKILL.md` starts with YAML frontmatter containing `name` and `description`.
- No API key, token, or credential is present anywhere in the ZIP.
- Section 0 (scope, one-time upload disclosure, non-refusal rules, two technical gates)
  is present and unchanged from the canonical body; no vendor/product-name-based
  refusal rule exists anywhere in the package.
- Section 1 lists every accepted file input (upload, absolute path, repo-relative
  path, directory, glob) and the bundled client exposes `--root` plus the
  `multiple_candidates` guard.
- No copyright removal or license-enforcement bypass tooling is present in `scripts/`
  or `references/`.
- External HTTP calls are described as connector/registered-tool mediated for
  cloud tasks; the appendix documents the fallback.
- The user-facing output template stays in three sections (Result / Verification /
  Action needed) with no raw endpoint or HTTP-envelope details.
- The trial-preview delivery rule is present: every returned line is shown verbatim
  in `## Result`, never summarized as a line count, and the decoded snippet is
  explicitly distinguished from a raw response.
