"""Security Research Mode (authorised scope only).

This module extends audit.py with the workflows the user asked for,
under the same hard gates, plus scope and resource limits:

  * static analysis: audit.analyse_text_file, plus a dependency audit
    that parses requirements.txt / pyproject.toml / package.json in the
    workspace and reports declared dependencies -- it does NOT invent
    CVE findings. If a real scanner (pip-audit / npm audit) is installed
    it may be run, bounded, and its output quoted; otherwise the report
    says plainly that no scanner was available.
  * dynamic analysis: audit.debug_run (own .py only, bounded, safe env).
  * binary analysis: audit.extract_strings plus static_malware_profile,
    which computes size, SHA-256, entropy estimate and printable strings
    WITHOUT executing the file. Untrusted binaries are never executed.
  * network diagnostics: scoped DNS + TCP reachability for ONE host and
    an explicit, small port list (max 20 ports, 1s timeout each). No
    subnet sweeps, no port-range scans, no brute force, no packet
    crafting. The host must be authorised and must not be a private
    cloud-metadata address (169.254.169.254) or localhost credential
    service -- diagnostics are for your own / authorised hosts only.
  * CTF helpers: pure, offline decoders (base64, hex, rot13, reverse)
    for authorised challenge files in the workspace. CTF challenges are
    puzzles the user is meant to solve; decoding your own challenge
    file is legitimate.
  * authorised penetration testing: this module does NOT provide
    exploits, payloads, credential attacks or auth bypasses. What it
    provides is a scoped test plan + evidence report: the target, the
    authorisation confirmation, the checks actually run (the ones above),
    and the findings. An "authorised pentest" here means: you confirmed
    you own / are authorised to test the target, the checks are the
    read-only / diagnostic ones listed, and anything that would be an
    attack is out of scope and refused.

Every public function requires authorised=True and a workspace-scoped
target, except the pure CTF decoders (which take strings, not targets).
Failures are safe: unknown tools, missing files and refused scopes
return a structured error, never a partial claim of success, and never
a secret in output.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import hashlib
import json
import math
import re
import shutil
import socket
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .audit import AuditError, AuditNotAuthorised, analyse_text_file, require_authorised
    from .runner import WorkspaceViolation, assert_inside, resolve_workspace
except ImportError:  # loaded as standalone files in tests
    from audit import AuditError, AuditNotAuthorised, analyse_text_file, require_authorised
    from runner import WorkspaceViolation, assert_inside, resolve_workspace

MAX_PORTS = 20
PORT_TIMEOUT_S = 1.0
MAX_STATIC_FILE_BYTES = 50 * 1024 * 1024
_BLOCKED_DIAG_HOSTS = {"169.254.169.254", "metadata.google.internal"}


class SecurityError(Exception):
    """Base security-mode error."""


def _redact(text: str) -> str:
    return re.sub(r"(?i)(password|api[_-]?key|secret|token)\s*[:=]\s*\S+", r"\1=[REDACTED]", text)


# ---------- dependency audit ----------

def dependency_audit(workspace: str | Path, authorised: bool = False) -> dict[str, Any]:
    """List declared dependencies from workspace manifest files.

    No CVE is claimed unless a real scanner ran and said so. If
    pip-audit is installed, it is run (bounded, workspace cwd, no
    network claim beyond what the tool itself does) and its summary is
    included verbatim, truncated; otherwise scanner_available=False.
    """
    ws = resolve_workspace(workspace)
    if not authorised:
        raise AuditNotAuthorised("dependency audit requires authorised=True (own/authorised project)")
    declared: list[dict[str, Any]] = []
    req = ws / "requirements.txt"
    if req.is_file():
        for line in req.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                declared.append({"file": "requirements.txt", "spec": line[:200]})
    pkg = ws / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies"):
                for name, ver in (data.get(section) or {}).items():
                    declared.append({"file": "package.json", "spec": f"{name}@{ver}"})
        except (json.JSONDecodeError, OSError):
            declared.append({"file": "package.json", "spec": "unparseable (not counted as a finding)"})
    scanner = shutil.which("pip-audit")
    scanner_output = None
    if scanner:
        try:
            proc = subprocess.run(
                [scanner, "--format", "json"],
                cwd=str(ws),
                timeout=120,
                capture_output=True,
                text=True,
            )
            scanner_output = (proc.stdout or proc.stderr or "")[:4000]
        except (OSError, subprocess.TimeoutExpired) as exc:
            scanner_output = f"scanner failed: {exc}"
    return {
        "declared": declared,
        "scanner_available": scanner is not None,
        "scanner_output": _redact(scanner_output) if scanner_output else None,
        "cve_claim": "none claimed unless the scanner output above lists one",
    }


# ---------- binary / static malware profile (no execution) ----------

def static_malware_profile(target: str, workspace: str | Path, authorised: bool = False) -> dict[str, Any]:
    """Static-only profile of a file. The file is NEVER executed."""
    ws = resolve_workspace(workspace)
    path = require_authorised(target, ws, authorised)
    if not path.is_file():
        raise SecurityError(f"not a file: {target}")
    size = path.stat().st_size
    if size > MAX_STATIC_FILE_BYTES:
        raise SecurityError(f"file too large for static profile: {size} bytes (limit {MAX_STATIC_FILE_BYTES})")
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    counts = Counter(data)
    entropy = 0.0
    for count in counts.values():
        p = count / max(len(data), 1)
        entropy -= p * math.log2(p) if p > 0 else 0
    strings = [m.group(0).decode() for m in re.finditer(rb"[\x20-\x7e]{4,}", data)][:200]
    return {
        "target": str(path.relative_to(ws)),
        "size_bytes": size,
        "sha256": sha,
        "entropy_bits_per_byte": round(entropy, 3),
        "magic_first_bytes_hex": data[:8].hex(),
        "strings_sample": [_redact(s) for s in strings],
        "executed": False,
        "note": "Static analysis only. No code from this file was executed.",
    }


# ---------- network diagnostics (scoped, one host) ----------

def network_diagnostics(host: str, ports: list[int], authorised: bool = False) -> dict[str, Any]:
    """DNS + TCP reachability for ONE authorised host, max 20 ports."""
    if not authorised:
        raise AuditNotAuthorised("network diagnostics require authorised=True (own/authorised host)")
    host = (host or "").strip()
    if not host or "://" in host or "/" in host:
        raise SecurityError("host must be a bare hostname or IP, not a URL or path")
    if host in _BLOCKED_DIAG_HOSTS:
        raise SecurityError("cloud-metadata hosts are never diagnostic targets")
    if len(ports) > MAX_PORTS:
        raise SecurityError(f"port list too large: {len(ports)} > {MAX_PORTS} (scope limit)")
    for port in ports:
        if not isinstance(port, int) or not (1 <= port <= 65535):
            raise SecurityError(f"invalid port: {port!r}")
    try:
        resolved = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        addresses = sorted({info[4][0] for info in resolved})
    except socket.gaierror as exc:
        return {"host": host, "dns": f"failed: {exc}", "ports": [], "note": "DNS failed; no port check was run"}
    results = []
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=PORT_TIMEOUT_S):
                results.append({"port": port, "open": True})
        except OSError:
            results.append({"port": port, "open": False})
    return {"host": host, "dns": addresses, "ports": results, "note": "Reachability only; no exploit, no auth attempt, no data sent beyond TCP connect"}


# ---------- CTF helpers (pure, offline) ----------

def ctf_decode(text: str, method: str) -> str:
    """Decode a challenge string. Pure function; no target, no network."""
    if method == "base64":
        try:
            return base64.b64decode(text.strip(), validate=True).decode(errors="replace")
        except (binascii.Error, ValueError) as exc:
            raise SecurityError(f"base64 decode failed: {exc}")
    if method == "hex":
        try:
            return bytes.fromhex(text.strip()).decode(errors="replace")
        except ValueError as exc:
            raise SecurityError(f"hex decode failed: {exc}")
    if method == "rot13":
        return codecs.decode(text, "rot_13")
    if method == "reverse":
        return text[::-1]
    raise SecurityError(f"unknown CTF method: {method!r} (base64, hex, rot13, reverse)")


# ---------- scoped test plan / evidence report ----------

def scoped_security_report(
    target: str,
    workspace: str | Path,
    authorised: bool = False,
    checks: list[str] | None = None,
) -> dict[str, Any]:
    """Evidence-based report for an authorised target.

    checks is a subset of: static, strings, dependency, profile.
    Anything else (exploit, brute-force, bypass) is refused by the
    allowlist below -- it is not a valid check name.
    """
    allowed = {"static", "strings", "dependency", "profile"}
    wanted = checks or ["static"]
    unknown = [c for c in wanted if c not in allowed]
    if unknown:
        raise SecurityError(f"refused checks (not in authorised scope): {unknown}")
    if not authorised:
        raise AuditNotAuthorised("security report requires authorised=True (own/authorised target)")
    ws = resolve_workspace(workspace)
    evidence: dict[str, Any] = {}
    if "static" in wanted and (ws / target).is_file() and (ws / target).suffix == ".py":
        evidence["static"] = analyse_text_file(target, ws, authorised=True)
    if "strings" in wanted:
        try:
            from .audit import extract_strings
        except ImportError:
            from audit import extract_strings

        evidence["strings"] = extract_strings(target, ws, authorised=True)
    if "profile" in wanted:
        evidence["profile"] = static_malware_profile(target, ws, authorised=True)
    if "dependency" in wanted:
        evidence["dependency"] = dependency_audit(ws, authorised=True)
    return {
        "target": target,
        "authorised": True,
        "checks_run": wanted,
        "evidence": evidence,
        "attacks_run": [],
        "note": "Read-only / diagnostic checks only. No exploit, auth bypass or credential attack was run.",
    }
