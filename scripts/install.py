#!/usr/bin/env python3
"""Install generated skill packages into each harness's discovery directory.

Dry-run by default: nothing is written unless --apply is given.

Usage:
    python scripts/install.py                                  # preview all, project scope
    python scripts/install.py --scope user                      # preview user scope
    python scripts/install.py --target codex --target claude-code --apply
    python scripts/install.py --scope user --apply --link      # symlink instead of copy
    python scripts/install.py --target doubao-work           # prints manual upload steps

Target roots come from targets.json (install map). `project` paths resolve under
--repo (default: current working directory); `user`, `legacy_user`, `compat_user`
paths resolve under the home directory.
"""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import SRC, DIST, ROOT, load_targets  # noqa: E402

HOME_SCOPES = {"user", "legacy_user", "compat_user"}
MANUAL_HINTS = {
    "workbuddy-marketplace": (
        "Upload dist/workbuddy-marketplace/<skill>.zip in the WorkBuddy Skill Marketplace "
        "creation form (open platform). Local install is handled by the `workbuddy` target."
    ),
    "doubao-work": (
        "Upload dist/doubao-work/<skill>/ (or dist/doubao-work/<skill>.zip) in the "
        "Doubao client via Skills > Add > Upload, or publish it through the open platform. "
        "Fill the name/summary/icon/version fields from PACKAGE.md. Remember local and "
        "cloud skill sets are separate."
    ),
}


def resolve_install_path(template, skill_name, scope, repo):
    rendered = template.format(skill=skill_name)
    path = Path(rendered).expanduser()
    if not path.is_absolute():
        base = Path.home() if scope in HOME_SCOPES else repo
        path = base / path
    return path


def main():
    ap = argparse.ArgumentParser(description="Install generated skills into harness directories.")
    ap.add_argument("--target", action="append", default=[],
                    help="install only these target ids (repeatable)")
    ap.add_argument("--scope", default="project",
                    help="key from the target's install map: project | user | legacy_user | compat_project | compat_user")
    ap.add_argument("--repo", default=str(Path.cwd()), help="project root for project-scoped paths")
    ap.add_argument("--apply", action="store_true", help="actually write files (default: dry-run)")
    ap.add_argument("--link", action="store_true", help="create a symlink instead of copying (requires --apply)")
    args = ap.parse_args()

    config = load_targets()
    targets = config["targets"]
    if args.target:
        known = {t["id"] for t in targets}
        unknown = [t for t in args.target if t not in known]
        if unknown:
            print("Unknown target ids: " + ", ".join(unknown), file=sys.stderr)
            return 2
        targets = [t for t in targets if t["id"] in args.target]

    skills = sorted(p.name for p in SRC.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    repo = Path(args.repo).resolve()
    mode = "APPLY" if args.apply else "DRY-RUN"
    planned = 0
    skipped = 0

    print(f"Mode: {mode} | scope: {args.scope} | project root: {repo}")
    print("-" * 72)

    for target in targets:
        tid = target["id"]
        installs = target.get("install", {})
        if not installs or tid in MANUAL_HINTS:
            print(f"[{tid}] manual step: {MANUAL_HINTS.get(tid, 'no local discovery path')}")
            skipped += 1
            continue
        if args.scope not in installs:
            available = ", ".join(sorted(installs))
            print(f"[{tid}] SKIP - scope `{args.scope}` unavailable (available: {available})")
            skipped += 1
            continue

        for skill_name in skills:
            src = DIST / target["dist"].format(skill=skill_name)
            dst = resolve_install_path(installs[args.scope], skill_name, args.scope, repo)
            if not src.is_dir():
                print(f"[{tid}/{skill_name}] SKIP - missing build output, run scripts/build.py first")
                skipped += 1
                continue
            planned += 1
            action = "symlink" if (args.apply and args.link) else "copy"
            print(f"[{tid}/{skill_name}] {action} {src.relative_to(ROOT).as_posix()} -> {dst}")
            if not args.apply:
                continue
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if args.link:
                    if dst.exists() or dst.is_symlink():
                        print(f"  ! destination exists, skipped: {dst}")
                        continue
                    dst.symlink_to(src, target_is_directory=True)
                else:
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                print("  done")
            except OSError as exc:
                print(f"  ! failed: {exc}", file=sys.stderr)
                return 1

    print("-" * 72)
    print(f"{planned} install action(s), {skipped} manual/skipped target(s).")
    if not args.apply:
        print("Dry-run only. Re-run with --apply to write files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
