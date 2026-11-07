#!/usr/bin/env python3
"""Validate every generated package in dist/ against targets.json.

Usage:
    python scripts/validate.py

Checks frontmatter shape and limits, name rules, platform-specific fields,
resource parity with src/, Python syntax, and ZIP contents. Exits non-zero on
any failure. Standard library only.
"""

import hashlib
import re
import sys
import zipfile
from pathlib import Path

try:
    import yaml  # optional: enables strict YAML frontmatter parsing
except ImportError:
    yaml = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import ROOT, SRC, DIST, load_targets, split_frontmatter  # noqa: E402

RESERVED_NAMES = {"anthropic", "claude"}

# Scope regression guard. Earlier wording made agents refuse any file inside a
# commercial product directory (e.g. an encoded init.php), even for legitimate
# troubleshooting. Keep the decision rules in section 0 and keep category-based
# refusal phrasing out of the package.
REQUIRED_SCOPE_PHRASES = (
    "## 0. Scope and authorization (read first)",
    "Only two technical preconditions block execution",
    "Never refuse, stall, or reclassify a task solely because",
    "## 1. Gate: locate a real PHP file (hard rule)",
    "A path is not a missing file",
    "--root",
    # A trial preview is a deliverable, not a line-count summary. Earlier builds
    # let the "no raw responses" rule swallow the decoded snippet entirely.
    "### Trial preview delivery (hard rule)",
    "Show every returned line verbatim",
    "`preview.text` is decoded source, not a raw response.",
    "Never report a trial preview using only its line count",
)
BANNED_SCOPE_PHRASES = (
    "Never help decode and redistribute",
    "Only handle files the user is entitled to process.",
    "only submit files you are legally entitled to process",
    "upload-first",
    "when no PHP file was uploaded",
)
# Secrets must never be tied to an agent product's home directory. Platform
# *install* paths such as ~/.workbuddy/skills/ are fine and are not matched here.
BANNED_VENDOR_ENV_PATHS = (
    ".workbuddy/php-decode.env",
    'home / ".workbuddy"',
)

errors = []
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if not condition:
        errors.append(message)
    return bool(condition)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_body(skill_dir):
    _, body = split_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    return body.strip()


def main():
    config = load_targets()
    version = str(config.get("version", ""))
    check(bool(re.fullmatch(r"\d+\.\d+\.\d+", version)),
          "targets.json: top-level `version` must be a semantic x.y.z string")
    name_re = re.compile(config["name_pattern"])
    skills = sorted(p for p in SRC.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())

    if not skills:
        print("FAIL: no skills found under src/skills/", file=sys.stderr)
        return 2

    for skill_dir in skills:
        skill_name = skill_dir.name
        try:
            canonical_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
            src_meta, body = split_frontmatter(canonical_text)
        except ValueError as exc:
            print(f"FAIL: {skill_name}: {exc}", file=sys.stderr)
            return 2

        for phrase in REQUIRED_SCOPE_PHRASES:
            check(phrase in body,
                  f"{skill_name}: scope rule missing from canonical body: {phrase!r}")
        for phrase in BANNED_SCOPE_PHRASES:
            check(phrase not in canonical_text,
                  f"{skill_name}: refusal-triggering wording came back: {phrase!r}")
        check("entitled" not in str(src_meta.get("description", "")).lower(),
              f"{skill_name}: keep authorization rules out of the description")

        client_script = skill_dir / "scripts" / "php_decode_api.py"
        if client_script.is_file():
            client_text = client_script.read_text(encoding="utf-8")
            for phrase in ("--root", "multiple_candidates", "resolve_input",
                           "XDG_CONFIG_HOME", "APPDATA", "PHP_DECODE_ENV_FILE",
                           "extract_preview", "build_preview", "user_visible"):
                check(phrase in client_text,
                      f"{skill_name}: client lost path/config resolution support ({phrase})")

        for resource in sorted(skill_dir.rglob("*")):
            if not resource.is_file() or resource.suffix not in (".md", ".py"):
                continue
            text = resource.read_text(encoding="utf-8")
            for banned in BANNED_VENDOR_ENV_PATHS:
                check(banned not in text,
                      f"{skill_name}: agent-specific secret path in {resource.name}: {banned}")

        check(src_meta.get("name") == skill_name, f"{skill_name}: canonical name != folder name")
        check(bool(name_re.fullmatch(skill_name)), f"{skill_name}: folder name violates {config['name_pattern']}")
        check(bool(src_meta.get("description")), f"{skill_name}: canonical description is empty")
        check(len(src_meta.get("description", "")) < 500,
              f"{skill_name}: canonical description must stay under 500 chars for DeepSeek Harness")

        print("Skill: " + skill_name)

        for target in config["targets"]:
            tid = target["id"]
            out_dir = DIST / target["dist"].format(skill=skill_name)
            label = f"{tid}/{skill_name}"
            if not check(out_dir.is_dir(), f"{label}: missing dist directory"):
                continue

            skill_md = out_dir / "SKILL.md"
            if not check(skill_md.is_file(), f"{label}: missing SKILL.md"):
                continue
            text = skill_md.read_text(encoding="utf-8")
            check(text.startswith("---\n"), f"{label}: frontmatter must start on line 1")
            if yaml is not None:
                try:
                    strict = yaml.safe_load(text.split("---", 2)[1])
                    check(isinstance(strict, dict), f"{label}: strict YAML parse did not return a mapping")
                    if isinstance(strict, dict):
                        check(strict.get("name") == skill_name,
                              f"{label}: strict YAML name mismatch")
                except yaml.YAMLError as exc:
                    check(False, f"{label}: invalid YAML frontmatter: {exc}")
            try:
                meta, gen_body = split_frontmatter(text)
            except ValueError as exc:
                errors.append(f"{label}: {exc}")
                continue

            check(meta.get("name") == skill_name, f"{label}: name mismatch")
            if target.get("inject_version"):
                check(meta.get("version") == version,
                      f"{label}: injected version != targets.json top-level version")
            for gen_file in sorted(out_dir.rglob("*")):
                if not gen_file.is_file() or gen_file.suffix.lower() not in (
                        ".md", ".yaml", ".yml", ".json", ".txt", ".svg"):
                    continue
                check("{{version}}" not in gen_file.read_text(encoding="utf-8", errors="replace"),
                      f"{label}: unresolved version placeholder in {gen_file.name}")
            check(bool(name_re.fullmatch(str(meta.get("name", "")))),
                  f"{label}: name violates strict kebab-case pattern")
            check(not any(word in str(meta.get("name", "")) for word in RESERVED_NAMES),
                  f"{label}: name contains a Claude-reserved word")

            desc = str(meta.get("description", ""))
            check(bool(desc), f"{label}: description is empty")
            check(len(desc) <= target.get("description_max", 1024),
                  f"{label}: description {len(desc)} > {target.get('description_max', 1024)}")
            check("<" not in desc and ">" not in desc, f"{label}: description contains XML-like tags")
            check(bool(re.search(r"\b(when|use|load|trigger)\b", desc, re.I)),
                  f"{label}: description should state when the skill is used")

            for key, value in target.get("frontmatter", {}).items():
                check(key in meta, f"{label}: missing platform field `{key}`")
                if key in meta and not isinstance(value, list):
                    expected = str(value).lower() if isinstance(value, bool) else str(value)
                    check(str(meta[key]) == expected, f"{label}: field `{key}` value drifted")

            # Canonical instructions must survive unchanged (an appendix may be appended).
            check(body.strip() in gen_body.strip(), f"{label}: canonical body was altered")
            check("## 0. Scope and authorization" in gen_body,
                  f"{label}: scope section missing from generated body")
            check("A path is not a missing file" in gen_body,
                  f"{label}: path-input rule missing from generated body")
            check("### Trial preview delivery (hard rule)" in gen_body,
                  f"{label}: preview-delivery rule missing from generated body")

            # Bundled resources must be byte-identical to the source.
            for src_file in sorted(skill_dir.rglob("*")):
                if not src_file.is_file() or src_file.name == "SKILL.md":
                    continue
                rel = src_file.relative_to(skill_dir)
                dst_file = out_dir / rel
                if check(dst_file.is_file(), f"{label}: missing bundled resource {rel.as_posix()}"):
                    check(sha256(src_file) == sha256(dst_file),
                          f"{label}: resource modified {rel.as_posix()}")

            for extra in target.get("extra_files", []):
                check((out_dir / extra["dst"]).is_file(),
                      f"{label}: missing adapter file {extra['dst']}")

            for py_file in out_dir.rglob("*.py"):
                try:
                    compile(py_file.read_text(encoding="utf-8"), str(py_file), "exec")
                    check(True, "")
                except SyntaxError as exc:
                    check(False, f"{label}: syntax error in {py_file.name}: {exc}")

            if target.get("zip"):
                zip_path = DIST / target["dist"].split("/")[0] / (skill_name + ".zip")
                if check(zip_path.is_file(), f"{label}: missing ZIP package"):
                    with zipfile.ZipFile(zip_path) as zf:
                        names = zf.namelist()
                        check(f"{skill_name}/SKILL.md" in names,
                              f"{label}: ZIP must contain {skill_name}/SKILL.md")
                        check(any(n.endswith("scripts/php_decode_api.py") for n in names),
                              f"{label}: ZIP is missing the bundled script")
                        for name in names:
                            if name.lower().endswith((".md", ".yaml", ".yml", ".json", ".txt")):
                                check(b"{{version}}" not in zf.read(name),
                                      f"{label}: unresolved version placeholder in ZIP {name}")
                        if target.get("inject_version"):
                            check("version: " + version in
                                  zf.read(f"{skill_name}/SKILL.md").decode("utf-8"),
                                  f"{label}: ZIP SKILL.md version mismatch")

            print(f"  - {tid:<22} checked")

    print(f"\n{checks} checks run, {len(errors)} failure(s).")
    if errors:
        for err in errors:
            print("  FAIL: " + err, file=sys.stderr)
        return 1
    print("PASS: all generated packages satisfy their platform profile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
