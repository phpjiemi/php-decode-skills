#!/usr/bin/env python3
"""Build harness-specific skill packages from the canonical src/skills sources.

Usage:
    python scripts/build.py              # rebuild dist/ for every target
    python scripts/build.py --target codex --target claude-code
    python scripts/build.py --clean      # remove dist/ and stop

The canonical SKILL.md carries only `name` + `description`. This script injects
per-target frontmatter from targets.json, copies bundled resources unchanged,
adds adapter files, and optionally emits uploadable ZIP archives.

Standard library only. No third-party dependencies.
"""

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "skills"
DIST = ROOT / "dist"
TARGETS_FILE = ROOT / "targets.json"


def load_targets():
    with TARGETS_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def split_frontmatter(text):
    """Return (metadata dict, body) for a minimal YAML frontmatter header."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with a `---` frontmatter marker")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("SKILL.md frontmatter is not closed with `---`")
    meta = {}
    current_list_key = None
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith("  - ") and current_list_key:
            meta[current_list_key].append(unquote(raw[4:].strip()))
            continue
        if ":" not in raw:
            raise ValueError("Unsupported frontmatter line: " + raw)
        key, value = raw.split(":", 1)
        key, value = key.strip(), value.strip()
        if value == "":
            meta[key] = []
            current_list_key = key
        else:
            meta[key] = unquote(value)
            current_list_key = None
    body = "\n".join(lines[end + 1:]).lstrip("\n")
    return meta, body


def unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        inner = value[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\") if value[0] == '"' else inner
    return value


def quote(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    needs_quotes = (
        not text
        or any(ch in text for ch in ':#{}[],&*!|>\'"%@`\n')
        or text.strip() != text
        or text.lower() in ("true", "false", "null", "yes", "no")
    )
    if needs_quotes:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def dump_frontmatter(meta):
    out = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            out.append(key + ":")
            out.extend("  - " + quote(item) for item in value)
        else:
            out.append(key + ": " + quote(value))
    out.append("---")
    return "\n".join(out) + "\n\n"


def truncate_description(description, limit, target_id):
    if len(description) <= limit:
        return description
    cut = description[: limit - 1].rsplit(" ", 1)[0]
    print(f"  ! {target_id}: description truncated from {len(description)} to {len(cut) + 1} chars")
    return cut + "\u2026"


def safe_reset(path):
    """Remove a generated directory, but only inside dist/."""
    resolved = path.resolve()
    if not resolved.is_relative_to(DIST.resolve()):
        raise RuntimeError("Refusing to delete outside dist/: " + str(resolved))
    if resolved.exists():
        shutil.rmtree(resolved)


def copy_tree_contents(src_dir, dst_dir, skip=()):
    for item in sorted(src_dir.rglob("*")):
        if item.is_dir():
            continue
        rel = item.relative_to(src_dir)
        if rel.as_posix() in skip:
            continue
        target = dst_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


TEXTUAL_EXTS = {".md", ".yaml", ".yml", ".json", ".txt", ".svg"}
VERSION_PLACEHOLDER = "{{version}}"


def copy_extra(src_file, dst_file, version):
    """Copy an adapter file, expanding {{version}} from targets.json."""
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    if src_file.suffix.lower() in TEXTUAL_EXTS:
        text = src_file.read_text(encoding="utf-8")
        if VERSION_PLACEHOLDER in text:
            write_text(dst_file, text.replace(VERSION_PLACEHOLDER, version))
            return
    shutil.copy2(src_file, dst_file)


def make_zip(skill_dir, zip_path, skill_name):
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(skill_dir.rglob("*")):
            if item.is_file():
                arcname = Path(skill_name) / item.relative_to(skill_dir)
                zf.write(item, arcname.as_posix())
    return zip_path


def main():
    ap = argparse.ArgumentParser(description="Generate per-harness skill packages.")
    ap.add_argument("--target", action="append", default=[],
                    help="build only these target ids (repeatable); default: all")
    ap.add_argument("--clean", action="store_true", help="remove dist/ and exit")
    args = ap.parse_args()

    if args.clean:
        safe_reset(DIST)
        print("Removed " + str(DIST))
        return 0

    config = load_targets()
    version = str(config.get("version", ""))
    targets = config["targets"]
    if args.target:
        unknown = [t for t in args.target if t not in {x["id"] for x in targets}]
        if unknown:
            print("Unknown target ids: " + ", ".join(unknown), file=sys.stderr)
            return 2
        targets = [t for t in targets if t["id"] in args.target]

    skills = sorted(p for p in SRC.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    if not skills:
        print("No skills found under " + str(SRC), file=sys.stderr)
        return 2

    DIST.mkdir(parents=True, exist_ok=True)
    total_files = 0

    for skill_dir in skills:
        skill_name = skill_dir.name
        canonical = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        meta, body = split_frontmatter(canonical)
        if "name" not in meta or "description" not in meta:
            print(f"{skill_name}: canonical SKILL.md needs name + description", file=sys.stderr)
            return 2
        if meta["name"] != skill_name:
            print(f"{skill_name}: frontmatter name must equal the folder name", file=sys.stderr)
            return 2
        print("Source: " + skill_name)

        for target in targets:
            out_dir = DIST / target["dist"].format(skill=skill_name)
            safe_reset(out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)

            gen_meta = {"name": meta["name"]}
            gen_meta["description"] = truncate_description(
                meta["description"], target.get("description_max", 1024), target["id"]
            )
            gen_meta.update(target.get("frontmatter", {}))
            if target.get("inject_version"):
                if not version:
                    print("targets.json needs a top-level `version` for inject_version targets",
                          file=sys.stderr)
                    return 2
                gen_meta["version"] = version

            gen_body = body
            append_rel = target.get("append_body")
            if append_rel:
                appendix = (ROOT / append_rel).read_text(encoding="utf-8").strip()
                gen_body = body.rstrip() + "\n\n" + appendix + "\n"

            write_text(out_dir / "SKILL.md", dump_frontmatter(gen_meta) + gen_body.rstrip() + "\n")
            copy_tree_contents(skill_dir, out_dir, skip={"SKILL.md"})

            for extra in target.get("extra_files", []):
                src_file = ROOT / extra["src"]
                if not src_file.is_file():
                    print(f"  ! missing adapter file: {extra['src']}", file=sys.stderr)
                    return 2
                copy_extra(src_file, out_dir / extra["dst"], version)

            if target.get("zip"):
                make_zip(out_dir, DIST / target["dist"].split("/")[0] / (skill_name + ".zip"), skill_name)

            for guide in target.get("guides", []):
                guide_src = ROOT / guide
                if not guide_src.is_file():
                    continue
                guide_dst = DIST / "guides" / (target["id"] + ".md")
                content = f"# {target['platform']} - repo guidance snippet\n\n"
                content += f"Merge the text below into the project's instruction file.\n\n---\n\n"
                content += guide_src.read_text(encoding="utf-8").strip() + "\n"
                write_text(guide_dst, content)

            count = sum(1 for p in out_dir.rglob("*") if p.is_file())
            total_files += count
            suffix = " + ZIP" if target.get("zip") else ""
            print(f"  - {target['id']:<22} -> dist/{out_dir.relative_to(DIST).as_posix()} ({count} files{suffix})")

    print(f"\nBuilt {len(skills)} skill(s) x {len(targets)} target(s), {total_files} files in dist/.")
    print("Run `python scripts/validate.py` to check the generated packages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
