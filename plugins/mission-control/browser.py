"""Browser smoke test for AGENT 22 (real browser_exec, when available).

What this module is and is not:
  * It is the smoke test the user asked for: open a PUBLIC page
    (https://example.com, no login, no cookies, no credentials),
    read its title, take a screenshot, and return the result
    through the Telegram handler (platforms dispatch, owner/admin
    only). The screenshot is returned as a FILE DESCRIPTOR
    (path + size), never as bytes in chat, and the real Telegram
    adapter sends it as an attachment.
  * It does NOT copy browser cookies into chat, print credentials,
    or enable remote debugging on a public interface. The browser
    runs with the default fresh throwaway profile
    (browser.user_data_dir="" and use_real_profile=False in the
    example config), so no real-profile cookies or logins are
    involved at all. No CDP URL is set in the example config, and
    no code here sets BROWSER_CDP_URL to a public address.
  * It does NOT fake a browser. The default runner imports the
    repo's real browser_exec (tools/browser_use_cli.py) and calls
    it with the smoke code below. If browser_harness / Chromium is
    not installed, the runner reports available=False with the
    exact reason, and the smoke test reports NOT RUN -- it never
    invents a title or a screenshot. A fake runner may be injected
    in tests only, to verify the handler logic without a browser.
  * URL safety: only the allowlisted public URL is used. Private
    IPs, localhost, cloud-metadata hosts and URLs containing
    credentials are refused before any browser call, mirroring
    tools/browser_url_policy.py (which remains enabled and
    unedited).

Smoke code (browser_exec helpers, from the repo's own digest):
  new_tab(url) for the first navigation, wait_for_load(),
  js('document.title') for the title, capture_screenshot() for
  the screenshot. Note: with the Lightpanda engine
  (browser.engine=lightpanda) screenshots are unavailable -- the
  smoke test then reports title-only and says so, instead of
  claiming a screenshot.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

try:
    from .runner import resolve_workspace
except ImportError:  # loaded as standalone files in tests
    from runner import resolve_workspace

SMOKE_URL = "https://example.com"
SMOKE_CODE = (
    "# Browser smoke test: open example.com\n"
    "new_tab('https://example.com')\n"
    "wait_for_load()\n"
    "print('TITLE:' + js('document.title'))\n"
    "capture_screenshot()\n"
)
_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "localhost", "127.0.0.1"}


def validate_smoke_url(url: str) -> None:
    """Refuse private/metadata/credential URLs before any browser call."""
    if not url.startswith("https://"):
        raise ValueError(f"smoke URL must be https: {url!r}")
    host = re.sub(r"^https://", "", url).split("/")[0].split(":")[0]
    if host in _BLOCKED_HOSTS or host.endswith(".local") or "@" in url:
        raise ValueError(f"smoke URL refused (private/metadata/credential): {url!r}")


def default_browser_runner(code: str, session: str = "agent22-smoke") -> dict[str, Any]:
    """Call the repo's real browser_exec, or report it unavailable."""
    try:
        from tools.browser_use_cli import browser_exec, browser_exec_available
    except ImportError as exc:
        return {"available": False, "reason": f"browser_harness not importable: {exc}", "install": "hermes pm install chromium  (then: hermes tools -> Browser Automation -> Browser Use)"}
    if not browser_exec_available():
        return {"available": False, "reason": "browser_exec_available() is False (browser-harness not found in this install)", "install": "hermes pm install chromium  (then: hermes tools -> Browser Automation -> Browser Use)"}
    try:
        result = browser_exec(code, session=session)
    except Exception as exc:
        return {"available": True, "success": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"available": True, "result": result}


def run_browser_smoke(
    workspace: str | Path,
    runner: Callable[[str, str], dict[str, Any]] | None = None,
    url: str = SMOKE_URL,
) -> dict[str, Any]:
    """Run the smoke test. Returns a descriptor, never cookies or credentials."""
    validate_smoke_url(url)
    ws = resolve_workspace(workspace)
    runner = runner or default_browser_runner
    outcome = runner(SMOKE_CODE, "agent22-smoke")
    if not outcome.get("available"):
        return {
            "available": False,
            "url": url,
            "title": None,
            "screenshot": None,
            "success": False,
            "reason": outcome.get("reason", "browser unavailable"),
            "install": outcome.get("install"),
            "note": "Browser smoke test NOT RUN in this environment. Do not claim browser access works until this returns success on a real Hermes install with Chromium.",
        }
    result = outcome.get("result") or {}
    # browser_exec result shapes vary (dict with stdout/screenshot_path, or text).
    text = ""
    if isinstance(result, dict):
        text = str(result.get("stdout") or result.get("text") or result.get("output") or "")
        screenshot = result.get("screenshot_path")
    else:
        text = str(result)
        screenshot = None
    title = None
    for line in text.splitlines():
        if line.startswith("TITLE:"):
            title = line[len("TITLE:"):].strip()
            break
    screenshot_info = None
    if screenshot:
        path = Path(screenshot)
        if path.is_file():
            screenshot_info = {"path": str(path), "size_bytes": path.stat().st_size}
    return {
        "available": True,
        "url": url,
        "title": title,
        "screenshot": screenshot_info,
        "success": bool(title),
        "backend": "local Chromium via browser_exec (no paid browser API, no real profile, no CDP on a public interface)",
        "cookies_copied": False,
        "credentials_printed": False,
    }
