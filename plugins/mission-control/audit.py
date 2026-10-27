"""Bounded own-asset security audit (reverse-engineering / debugging aid).

Scope, stated plainly because the user asked for a "hacking tool":
this module audits ONLY files inside the mission workspace that the
caller explicitly confirms they own or are authorised to test. It does
NOT remove Hermes' hard floors, does NOT bypass authentication, does
NOT crack passwords, does NOT exfiltrate credentials, and does NOT
attack other people's systems, accounts or networks. Those boundaries
are in blueprint §13 and in the standing rule for this user (no
unauthorised access; security auditing for his own assets only), and
they stay in the execution path here, not just in prompt text:

  * target must resolve inside the workspace (same guard as runner.py);
  * the caller must pass authorised=True -- a plain function call with
    no confirmation is refused, so a tool result or a pasted web page
    cannot silently authorise an audit;
  * network targets, URLs, IP addresses and hostnames are refused;
  * no code from the target is executed by the static analysers;
    the optional debug runner only runs argv-list Python inside the
    workspace, with the runner's safe environment and timeout;
  * any credential-looking string found in output is redacted.

What it CAN do, legitimately: read your own source, flag dangerous
patterns (eval/exec/pickle, shell=True, hardcoded secrets, weak crypto
hints), extract printable strings from your own binaries, and run your
own scripts under a debugger-style bounded runner so you can debug
them. That is reverse-engineering and debugging your own work.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from .runner import WorkspaceViolation, assert_inside, resolve_workspace, safe_env
except ImportError:  # loaded as a standalone file in tests
    from runner import WorkspaceViolation, assert_inside, resolve_workspace, safe_env


class AuditError(Exception):
    """Base audit error."""


class AuditNotAuthorised(AuditError):
    """Target was not explicitly confirmed as owned/authorised."""


# Pattern name -> regex. These are flags for the owner to review, not
# proof of a vulnerability, and never a reason to auto-fix a file.
PATTERNS: list[tuple[str, str]] = [
    ("eval_or_exec", r"\b(eval|exec)\s*\("),
    ("pickle_load", r"pickle\.(load|loads)\s*\("),
    ("shell_true", r"shell\s*=\s*True"),
    ("hardcoded_secret_hint", r"(?i)(password|api_key|secret|token)\s*=\s*['\"][^'\"]{4,}['\"]"),
    ("weak_hash_md5_sha1", r"\b(md5|sha1)\s*\("),
    ("verify_false", r"verify\s*=\s*False"),
    ("os_system", r"os\.system\s*\("),
]

_SECRET_RE = re.compile(r"(?i)(password|api_key|secret|token)\s*=\s*['\"][^'\"]+['\"]")
_PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")


def require_authorised(target: str, workspace: Path, authorised: bool) -> Path:
    """Refuse network targets and unconfirmed targets before any work."""
    if "://" in target:
        raise AuditError(f"network targets are not auditable by this module: {target}")
    if not authorised:
        raise AuditNotAuthorised(
            "audit refused: caller must explicitly confirm they own or are "
            "authorised to test this target (authorised=True)"
        )
    return assert_inside(workspace, target)


def _redact(text: str) -> str:
    return _SECRET_RE.sub(r"\1=[REDACTED]", text)


def analyse_text_file(
    target: str, workspace: str | Path, authorised: bool = False
) -> dict[str, Any]:
    """Static analysis only: no target code is executed."""
    ws = resolve_workspace(workspace)
    path = require_authorised(target, ws, authorised)
    if not path.is_file():
        raise AuditError(f"not a file: {target}")
    content = path.read_text(encoding="utf-8", errors="replace")
    findings: list[dict[str, Any]] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for name, pattern in PATTERNS:
            if re.search(pattern, line):
                findings.append(
                    {"pattern": name, "line": lineno, "excerpt": _redact(line.strip())[:200]}
                )
    return {
        "target": str(path.relative_to(ws)),
        "lines": len(content.splitlines()),
        "findings": findings,
        "note": "Findings are review flags for the owner, not confirmed vulnerabilities.",
    }


def extract_strings(
    target: str, workspace: str | Path, authorised: bool = False, limit: int = 200
) -> dict[str, Any]:
    """Extract printable strings from the owner's own binary file."""
    ws = resolve_workspace(workspace)
    path = require_authorised(target, ws, authorised)
    if not path.is_file():
        raise AuditError(f"not a file: {target}")
    data = path.read_bytes()
    strings = [m.group(0).decode() for m in _PRINTABLE_RE.finditer(data)]
    return {
        "target": str(path.relative_to(ws)),
        "size_bytes": len(data),
        "strings": [_redact(s) for s in strings[:limit]],
        "truncated": len(strings) > limit,
    }


def debug_run(
    script: str,
    workspace: str | Path,
    authorised: bool = False,
    args: list[str] | None = None,
    timeout_seconds: int = 60,
) -> dict[str, Any]:
    """Run the owner's own Python script, bounded, argv-list only.

    The script must be a .py file inside the workspace. No shell, no
    network target, credential env stripped (see runner.safe_env).
    """
    ws = resolve_workspace(workspace)
    path = require_authorised(script, ws, authorised)
    if path.suffix != ".py":
        raise AuditError("debug_run only runs .py files inside the workspace")
    if not path.is_file():
        raise AuditError(f"not a file: {script}")
    try:
        proc = subprocess.run(
            ["python3", str(path), *(args or [])],
            cwd=str(ws),
            timeout=timeout_seconds,
            capture_output=True,
            text=True,
            env=safe_env(),
        )
        return {
            "exit_code": proc.returncode,
            "stdout": _redact(proc.stdout or "")[:4000],
            "stderr": _redact(proc.stderr or "")[:4000],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "stdout": "", "stderr": "timeout", "timed_out": True}
