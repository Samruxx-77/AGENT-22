# Installation

## Full Hermes agent (required for the gateway, models, and `hermes` CLI)
Follow upstream Hermes installation for your OS:
- Linux, macOS, WSL2: use the upstream install script from the Hermes docs site.
- Windows (native PowerShell): use the upstream PowerShell installer from the Hermes docs site.
- Termux/Android (aarch64): use the upstream Termux APT guide, NOT the desktop/server installer script. The pm Chromium build is not available on Termux, so local Chromium browser automation is limited there.
- Docker: see upstream `Dockerfile` and docs.

## Mission-control plugin tests only (no model, no secrets)
```bash
python3 -m venv /tmp/agent22-test-venv
/tmp/agent22-test-venv/bin/pip install -q pytest
/tmp/agent22-test-venv/bin/pytest tests/plugins/test_mission_control.py \
  tests/plugins/test_agent22_identity_security.py \
  tests/plugins/test_agent22_power.py \
  tests/plugins/test_agent22_platforms.py \
  tests/plugins/test_agent22_browser.py \
  tests/plugins/test_agent22_reflection.py \
  tests/skills/test_mission_control_skill.py -q -p no:cacheprovider --noconftest
```
Verified: 68 passed. The full upstream suite (`scripts/run_tests.sh`) needs the pm test environment and was not run in the build VM.

## After install
Copy `AGENT22_IDENTITY.md` to `~/.hermes/SOUL.md` to force the AGENT 22 persona on a running install, then run `hermes mission identity` and `hermes mission banner` to confirm.
