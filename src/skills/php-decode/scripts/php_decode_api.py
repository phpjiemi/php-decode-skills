#!/usr/bin/env python3
"""Portable client for the PHP decode API (php.jiemi.xyz).

Harness-neutral: uses only the Python 3 standard library plus `curl` on PATH.
It is bundled identically by every platform adapter generated from src/skills.

Input forms for --file (all are equivalent to "the file is supplied"):
  attached/uploaded file path, absolute path, ~ path, file:// URI,
  repo-relative path (cwd first, then --root), a directory, or a glob.
A directory or glob matching several files returns `multiple_candidates`
without any API call; re-run with the single chosen path.

Modes:
  --mode api    official async API, Bearer auth via $API_KEY (required)
  --mode trial  free tryit endpoint, no key, returns a short preview snippet
  --mode auto   api when $API_KEY is set, otherwise trial (default)

A trial preview is a real deliverable, not a failure. The client extracts the
returned snippet into a `preview` object flagged `user_visible: true`, so the
agent pastes the actual decoded lines into the report instead of reporting only
how many lines came back.

Safety rules:
  - refuses to call the API until a real PHP file has been located
  - never submits a directory or a batch of files as one job
  - official mode without a key stops and guides the user to set $API_KEY
  - never prints, logs or packages the API key
  - always sends optimize=0; decode optimization is never enabled

There is deliberately no authorization check: whether the user is entitled to process a
file is their decision (see section 0 of SKILL.md), not a client-side gate.
"""

import argparse
import glob as globmod
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote

DEFAULT_BASE = "https://php.jiemi.xyz"
PRODUCTS = {
    "ioncube": {"slug": "ioncube-decoder", "code": "IC"},
    "swoolecompiler": {"slug": "swoolecomplier-decoder", "code": "SC"},
    "sourceguardian": {"slug": "sourceguardian-decoder", "code": "SG"},
    "xload": {"slug": "xload-decoder", "code": "XL"},
}
ENCODER_MARKERS = (
    (b"ioncube", "ioncube"),
    (b"sourceguardian", "sourceguardian"),
    (b"swoole compiler", "swoolecompiler"),
    (b"xload", "xload"),
)
SKIP_DIRS = {".git", "node_modules", ".svn", ".hg", "__pycache__", ".venv", "venv"}
EXTS = {".php", ".phtml", ".php5", ".php7", ".inc"}
TRIAL_LIMIT = 1024 * 1024
MAX_SCAN = 200
MAX_CANDIDATES = 30

# Candidate keys for the visible snippet in a trial response. The trial endpoint's
# envelope is not a published contract, so these are hints for defensive parsing,
# not an asserted API schema (SKILL.md section 14: never invent response fields).
PREVIEW_KEYS = (
    "preview", "previewcode", "preview_code", "previewtext", "preview_text",
    "code", "content", "result", "output", "decoded", "decodedcode",
    "decoded_code", "source", "snippet", "php", "text", "data", "lines",
)
IGNORED_PREVIEW_KEYS = (
    "error", "message", "msg", "hint", "status", "url", "state", "jobid",
    "job_id", "filename", "name", "product", "locale",
)
ERROR_TOKENS = (
    "invalid_api_key", "decoder_failed", "choose a non-empty",
    "a valid bearer api key", "unauthorized", "too large",
)

FILE_HINT = (
    "Point me at the PHP file to decode: upload it, give an absolute path, a "
    "project-relative path, or a directory/glob to scan (.php / .phtml / .php5 / "
    ".php7 / .inc). Up to 1 MB can use the free trial; 1-5 MB need an API key; "
    "above 5 MB contact the service provider. The file will be sent to a "
    "third-party decode service."
)
SETUP_HINT = (
    "API_KEY is not configured. Official decoding needs an API key:\n"
    "  1) Current session (Git Bash / macOS / Linux): export API_KEY='your-key'\n"
    "     Current session (Windows PowerShell):     $env:API_KEY = 'your-key'\n"
    "  2) Persistent (recommended): put one line API_KEY=your-key in "
    "~/.config/php-decode/env\n"
    "     (or set PHP_DECODE_ENV_FILE to any path you prefer). Other searched locations:\n"
    "     $XDG_CONFIG_HOME/php-decode/env, %APPDATA%/php-decode/env, ~/.php-decode.env.\n"
    "     The lookup is vendor-neutral - no agent product needs to be installed.\n"
    "  3) Apply for a key: https://php.jiemi.xyz/console/api\n"
    "  4) Verify: curl \"$API_BASE/api/v1/credits\" -H \"Authorization: Bearer $API_KEY\"\n"
    "Re-run after setup. If you only want a free preview, pass --mode trial explicitly."
)
DONE_STATES = ("done", "completed", "succeeded", "success",
               "failed", "error", "cancelled", "canceled")


def emit(obj, code=0):
    print(json.dumps(obj, ensure_ascii=False, indent=2))
    sys.exit(code)


def safe_home():
    """Path.home() raises on hosts without HOME/USERPROFILE (some cloud sandboxes)."""
    try:
        return Path.home()
    except (RuntimeError, OSError):
        return None


def safe_expand(value):
    try:
        return Path(value).expanduser()
    except (RuntimeError, OSError):
        return Path(value)


def read_env_first(*names):
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def env_file_candidates():
    """Vendor-neutral env-file lookup using only standard OS config locations.

    No agent-product home directory is assumed: the client works whether or not
    Codex, Claude Code, dsh, WorkBuddy, or Doubao Work is installed. Environment
    variables (API_KEY / PHP_DECODE_API_KEY) always take priority over these files.
    PHP_DECODE_ENV_FILE overrides the entire list. First file with a key line wins.
    """
    override = os.environ.get("PHP_DECODE_ENV_FILE", "").strip()
    if override:
        return [safe_expand(override)]

    candidates = []

    def add(path):
        resolved = Path(path)
        if resolved not in candidates:
            candidates.append(resolved)

    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        add(safe_expand(xdg) / "php-decode" / "env")
    home = safe_home()
    if home is not None:
        add(home / ".config" / "php-decode" / "env")
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        add(safe_expand(appdata) / "php-decode" / "env")
    if home is not None:
        add(home / ".php-decode.env")
    return candidates


def read_api_key():
    key = read_env_first("API_KEY", "PHP_DECODE_API_KEY")
    if key:
        return key
    for env_file in env_file_candidates():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                for name in ("API_KEY", "PHP_DECODE_API_KEY"):
                    if line.startswith(name + "="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if value:
                            return value
        except OSError:
            continue
    return ""


def get_base():
    return (read_env_first("API_BASE", "PHP_DECODE_API_BASE") or DEFAULT_BASE).rstrip("/")


def run_curl(extra, timeout=60):
    cmd = ["curl", "-sS", "--max-time", str(timeout), "-w", "\n__HTTP__%{http_code}"] + extra
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError:
        return 0, "", "curl not found in PATH"
    body = proc.stdout or ""
    if "__HTTP__" in body:
        body, status = body.rsplit("__HTTP__", 1)
        body = body.rstrip("\n")
        try:
            status_code = int(status.strip())
        except ValueError:
            status_code = 0
    else:
        status_code = 0
    return status_code, body, (proc.stderr or "").strip()


def parse_body(body):
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return body


def looks_like_php(text):
    stripped = text.lstrip()
    if not stripped or len(stripped) > 200000:
        return False
    return (stripped.startswith("<?") or "<?php" in stripped
            or "function " in stripped or "class " in stripped
            or "namespace " in stripped or "->" in stripped or "=>" in stripped)


def extract_preview(resp):
    """Best-effort extraction of the visible snippet from a trial response.

    The trial endpoint's response envelope is not a published contract, so no
    single field name is required. Known candidate keys are tried first, then a
    bounded recursive scan picks the most PHP-like string. This is defensive
    parsing of whatever was actually returned, not an invented API schema.
    Returns (text, source_key).
    """
    if isinstance(resp, str):
        return (resp.strip(), "response body") if resp.strip() else ("", "")
    if not isinstance(resp, dict):
        return "", ""

    best_text, best_field, best_rank = "", "", (-1, -1, -1)

    def consider(value, key, depth, known):
        nonlocal best_text, best_field, best_rank
        if isinstance(value, str):
            text = value.strip()
            if not text or len(text) > 200000:
                return
            low_key = key.lower()
            if any(bad in low_key for bad in IGNORED_PREVIEW_KEYS):
                return
            strong = looks_like_php(text)
            plausible = strong or (len(text) >= 20 and ("\n" in text or ";" in text))
            if not plausible or any(tok in text.lower() for tok in ERROR_TOKENS):
                return
            rank = (1 if strong else 0, 1 if known else 0, len(text))
            if rank > best_rank:
                best_rank, best_text, best_field = rank, text, key
        elif isinstance(value, dict) and depth < 3:
            for k, v in value.items():
                consider(v, str(k), depth + 1, known)
        elif isinstance(value, list) and depth < 3:
            if value and all(isinstance(v, str) for v in value):
                consider("\n".join(value), key, depth + 1, known)
            for i, v in enumerate(value[:20]):
                consider(v, key + "[" + str(i) + "]", depth + 1, known)

    for candidate in PREVIEW_KEYS:
        for k, v in resp.items():
            if str(k).lower().replace("-", "_") == candidate:
                consider(v, str(k), 0, True)
    consider(resp, "response", 0, False)
    return best_text, best_field


def build_preview(resp, status):
    """Report-ready snippet: the deliverable, explicitly not a raw response."""
    text, field = extract_preview(resp)
    lines = text.splitlines()
    usable = bool(text) and bool(status) and status < 400
    preview = {
        "found": bool(text),
        "usable": usable,
        "text": text,
        "lines": lines,
        "line_count": len(lines),
        "source_field": field or None,
        "user_visible": True,
        "delivery": (
            "Show preview.text verbatim in a fenced ```php block under ## Result. "
            "These lines are the deliverable, not a raw response. Label the block "
            "as a partial preview and never report only its line count."
        ),
    }
    if not usable:
        preview["delivery"] = (
            "No usable preview text was returned. Say plainly that the preview "
            "contained no visible lines; never invent content and never paste raw "
            "error responses into the report."
        )
    return preview


def hint_for(status, resp):
    text = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
    if status == 401 or "invalid_api_key" in text:
        return (
            "API_KEY is invalid, expired, or not passed as Authorization: Bearer. "
            "Check the key at https://php.jiemi.xyz/console/api and verify it with "
            "curl \"$API_BASE/api/v1/credits\" -H \"Authorization: Bearer $API_KEY\". "
            "If it is not set up yet: " + SETUP_HINT
        )
    if "Choose a non-empty PHP file" in text:
        return "The file is empty or the multipart body carried no content. " + FILE_HINT
    if "decoder_failed" in text:
        return (
            "The decoder produced no output: confirm the file really is encoded with the "
            "selected product and that the product mapping is correct. Compare the "
            "encoder_hint from this client with section 4. Do not retry with a plaintext file."
        )
    if status == 413 or "too large" in text.lower():
        return "File is over the size limit; official mode supports 1-5 MB, above that contact the provider."
    if status >= 500:
        return "Service-side error. Record the job ID and query it later; do not retry silently."
    if status == 0:
        return "Network request failed. Check connectivity and service availability."
    if status == 200 and isinstance(resp, dict) and resp.get("code"):
        return "The service returned a business error code; see response."
    return ""


def normalize_input(raw):
    """Strip quotes and convert file:// URIs to a local path."""
    text = str(raw).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    if text.lower().startswith("file://"):
        text = unquote(text[7:])
        if text.lower().startswith("localhost/"):
            text = text[len("localhost/"):]
        if re.match(r"^/[A-Za-z]:[\\/]", text):
            text = text[1:]
    return text


def is_absolute(text):
    return Path(text).is_absolute() or bool(re.match(r"^[A-Za-z]:[\\/]", text))


def anchors(root):
    """cwd first, then the user-supplied project root."""
    result = [Path.cwd()]
    if root:
        base = safe_expand(root).resolve()
        if base not in result:
            result.append(base)
    return result


def guess_encoder(path):
    """Cheap header hint only; never overrides --product automatically."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(8192).lower()
    except OSError:
        return "unknown"
    for marker, name in ENCODER_MARKERS:
        if marker in head:
            return name
    return "unknown"


def scan_dir(directory):
    found = []
    try:
        items = sorted(directory.rglob("*"))
    except OSError:
        return found
    for item in items:
        if len(found) >= MAX_SCAN:
            break
        if not item.is_file() or item.suffix.lower() not in EXTS:
            continue
        try:
            parts = item.relative_to(directory).parts[:-1]
        except ValueError:
            continue
        if any(part in SKIP_DIRS or part.startswith(".") for part in parts):
            continue
        found.append(item)
    found.sort(key=lambda f: (guess_encoder(f) == "unknown", str(f).lower()))
    return found


def validate_file(path):
    if path.suffix.lower() not in EXTS:
        return None, "bad_extension", "Unsupported extension. " + FILE_HINT, []
    if not path.is_file():
        return None, "missing_file", "Not a regular file. " + FILE_HINT, []
    if path.stat().st_size == 0:
        return None, "empty_file", (
            "The file is empty; the server returns 400 Choose a non-empty PHP file. " + FILE_HINT
        ), []
    return path.resolve(), "ok", "", []


def pick_one(found, source):
    files, seen = [], set()
    for item in found:
        try:
            key = str(item.resolve())
            if key in seen or not item.is_file() or item.suffix.lower() not in EXTS:
                continue
            seen.add(key)
            files.append(item)
        except OSError:
            continue
    if not files:
        return None, "missing_file", "No matching PHP file found for " + source + ". " + FILE_HINT, []
    if len(files) > 1:
        candidates = []
        for item in files[:MAX_CANDIDATES]:
            try:
                candidates.append({"path": item.resolve().as_posix(),
                                   "size": item.stat().st_size,
                                   "encoder_hint": guess_encoder(item)})
            except OSError:
                continue
        hint = (
            str(len(files)) + " PHP files matched (" + source + "). Ask the user which ONE "
            "to decode; never submit a directory or a batch. Re-run with --file <chosen path>."
        )
        return None, "multiple_candidates", hint, candidates
    return validate_file(files[0])


def resolve_input(raw, root=None):
    """Return (path, state, hint, candidates) for any supported input form."""
    if not raw:
        return None, "missing_file", FILE_HINT, []
    text = normalize_input(raw)

    if any(ch in text for ch in "*?["):
        patterns = [text]
        if not is_absolute(text) and root:
            patterns.append(str(safe_expand(root).resolve() / text))
        found = []
        for pattern in patterns:
            try:
                found.extend(Path(p) for p in globmod.glob(pattern, recursive=True))
            except (OSError, ValueError):
                continue
        return pick_one(found, "glob " + text)

    path = safe_expand(text)
    if is_absolute(text):
        resolved = path
    else:
        resolved, tried = None, []
        for anchor in anchors(root):
            candidate = anchor / path
            tried.append(str(candidate))
            if candidate.exists():
                resolved = candidate
                break
        if resolved is None:
            return None, "missing_file", (
                "File not found. Tried: " + "; ".join(tried) + ". " + FILE_HINT
            ), []
    if not resolved.exists():
        return None, "missing_file", "File not found: " + str(resolved) + ". " + FILE_HINT, []
    if resolved.is_dir():
        return pick_one(scan_dir(resolved), "directory " + str(resolved))
    return validate_file(resolved)


def check_php_file(raw_path, root=None):
    """Backward-compatible (path, state, hint) wrapper around resolve_input."""
    path, state, hint, _ = resolve_input(raw_path, root)
    return path, state, hint


def check_license(raw_path, root=None):
    if not raw_path:
        return None, ""
    path = safe_expand(normalize_input(raw_path))
    if not is_absolute(str(path)):
        for anchor in anchors(root):
            candidate = anchor / path
            if candidate.is_file():
                path = candidate
                break
    if not path.is_file():
        return None, "License file not found: " + str(path)
    if path.stat().st_size == 0:
        return None, "License file is empty: " + str(path)
    return path.resolve().as_posix(), ""


def job_state(resp):
    if not isinstance(resp, dict):
        return ""
    return str(resp.get("state") or resp.get("status") or "")


def download_url_from(resp, job_id, base):
    if isinstance(resp, dict):
        for key in ("downloadUrl", "download_url", "resultUrl", "result_url"):
            if resp.get(key):
                return str(resp[key])
    return base + "/api/v1/jobs/" + str(job_id) + "/download"


def main():
    ap = argparse.ArgumentParser(description="Submit a PHP decode job.")
    ap.add_argument("--file", help="uploaded path, absolute path, ~ path, file:// URI, "
                                   "repo-relative path, directory, or glob")
    ap.add_argument("--root", help="project root for resolving relative paths and scans "
                                   "(default: current working directory)")
    ap.add_argument("--product", choices=sorted(PRODUCTS), default="ioncube")
    ap.add_argument("--mode", choices=("auto", "api", "trial"), default="auto",
                    help="api = official decode (requires API_KEY), trial = free preview, auto = default")
    # Deprecated no-op, accepted but hidden: a flag named "authorized" invites agents
    # to invent an extra approval gate that this skill deliberately does not have.
    ap.add_argument("--authorized", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--license", help="optional license file, e.g. license.lic for SourceGuardian (SG)")
    ap.add_argument("--no-poll", action="store_true", help="submit only, return job id without polling")
    ap.add_argument("--job-id", help="query/download an existing job instead of submitting a new one")
    ap.add_argument("--download", help="download result.zip to this path when state is done")
    ap.add_argument("--credits", action="store_true", help="only query account credits (official mode)")
    ap.add_argument("--poll-interval", type=float, default=3.0)
    ap.add_argument("--max-polls", type=int, default=40)
    ap.add_argument("--locale", default="zh-CN",
                    help="service-side locale parameter; keep the default unless the service documents another value")
    args = ap.parse_args()

    base = get_base()
    key = read_api_key()

    if args.mode == "api" and not key:
        emit({"error": "api_key_required", "mode_requested": "api", "hint": SETUP_HINT}, 2)
    if args.mode == "trial":
        mode = "trial"
    elif args.mode == "api":
        mode = "api"
    else:
        mode = "api" if key else "trial"

    auth_header = "Authorization: Bearer " + key

    if args.credits:
        if not key:
            emit({"error": "api_key_required", "mode": mode, "hint": SETUP_HINT}, 2)
        status, body, err = run_curl(["-H", auth_header, base + "/api/v1/credits"])
        emit({"mode": mode, "endpoint": "/api/v1/credits", "http_status": status,
              "response": parse_body(body), "hint": hint_for(status, parse_body(body)),
              "curl_stderr": err}, 0 if status < 400 else 1)

    result = {
        "mode": mode,
        "api_base": base,
        "api_key": "configured (not shown)" if key else "not configured",
    }

    # Resume an existing job: query status and optionally download.
    if args.job_id:
        if not key:
            emit({"error": "api_key_required", "mode": mode, "hint": SETUP_HINT}, 2)
        job_id = args.job_id
        s2, b2, _ = run_curl(["-H", auth_header, base + "/api/v1/jobs/" + str(job_id)])
        r2 = parse_body(b2)
        result.update({"job_id": job_id, "endpoint": "/api/v1/jobs/" + str(job_id),
                       "http_status": s2, "response": r2, "state": job_state(r2),
                       "hint": hint_for(s2, r2)})
        if args.download and job_state(r2).lower() == "done":
            url = download_url_from(r2, job_id, base)
            rc = subprocess.run(["curl", "-L", "-sS", "--max-time", "120", url,
                                 "-H", auth_header, "-o", args.download],
                                capture_output=True, text=True)
            result["download"] = {"url": url, "path": args.download, "returncode": rc.returncode,
                                  "stderr": (rc.stderr or "").strip()}
        emit(result, 0 if s2 and s2 < 400 else 1)

    path, state, hint, candidates = resolve_input(args.file, args.root)
    if state != "ok":
        out = {"error": state, "mode": mode, "hint": hint}
        if candidates:
            out["candidates"] = candidates
            out["candidate_count"] = len(candidates)
        emit(out, 2)

    license_path, license_err = check_license(args.license, args.root)
    if license_err:
        emit({"error": "invalid_license", "mode": mode, "hint": license_err}, 2)

    size = path.stat().st_size
    product = PRODUCTS[args.product]
    file_arg = path.resolve().as_posix()
    result.update({
        "product": product["code"] if mode == "api" else product["slug"],
        "file": file_arg,
        "file_size": size,
        "encoder_hint": guess_encoder(path),
    })
    if mode == "trial" and size > TRIAL_LIMIT:
        result["warning"] = "File exceeds the 1 MB trial limit; configure API_KEY and use official mode."

    if mode == "trial":
        endpoint = "/api/tryit"
        curl_args = [
            "-X", "POST", base + endpoint,
            "-H", "accept: */*",
            "-b", "phpdecode_lang=zh-CN",
            "-H", "origin: " + base,
            "-H", "referer: " + base + "/tryit/" + product["slug"],
            "-F", "product=" + product["slug"],
            "-F", "file=@" + file_arg + ";type=application/octet-stream",
            "-F", "locale=" + args.locale,
        ]
        result["trial_limit"] = (
            "<=1 MB, preview snippet only (0-10 visible lines depending on effective output "
            "line count); full source is never returned. Every returned line is still a "
            "deliverable and must be shown to the user verbatim."
        )
    else:
        endpoint = "/api/v1/decode"
        curl_args = [
            "-X", "POST", base + endpoint,
            "-H", auth_header,
            "-F", "product=" + product["code"],
            "-F", "file=@" + file_arg,
            "-F", "optimize=0",
        ]
        if license_path:
            curl_args += ["-F", "license=@" + license_path]
            result["license"] = license_path
        result["optimize"] = "0 (optimization disabled)"

    status, body, err = run_curl(curl_args)
    resp = parse_body(body)
    result.update({
        "endpoint": endpoint,
        "http_status": status,
        "response": resp,
        "hint": hint_for(status, resp),
    })
    if err:
        result["curl_stderr"] = err

    if mode == "api" and not args.no_poll and status and status < 300 and isinstance(resp, dict):
        job_id = next(
            (resp[k] for k in ("jobId", "job_id", "id", "taskId", "task_id") if resp.get(k)),
            None,
        )
        if job_id:
            result["job_id"] = job_id
            poll_log = []
            final_job = None
            for i in range(args.max_polls):
                time.sleep(args.poll_interval)
                s2, b2, _ = run_curl(["-H", auth_header, base + "/api/v1/jobs/" + str(job_id)])
                r2 = parse_body(b2)
                state2 = job_state(r2)
                poll_log.append({"attempt": i + 1, "http_status": s2, "state": state2})
                if state2.lower() in DONE_STATES or s2 >= 400:
                    final_job = r2
                    break
            result["poll"] = poll_log
            if final_job is not None:
                result["final_job"] = final_job
                result["state"] = job_state(final_job)
                if args.download and job_state(final_job).lower() == "done":
                    url = download_url_from(final_job, job_id, base)
                    rc = subprocess.run(["curl", "-L", "-sS", "--max-time", "120", url,
                                         "-H", auth_header, "-o", args.download],
                                        capture_output=True, text=True)
                    result["download"] = {"url": url, "path": args.download,
                                          "returncode": rc.returncode,
                                          "stderr": (rc.stderr or "").strip()}
            else:
                result["hint"] = "Polling timed out; keep this job_id for a later query: " + str(job_id)

    if mode == "trial":
        result["preview"] = build_preview(resp, status)

    emit(result, 0 if status and status < 400 else 1)


if __name__ == "__main__":
    main()
