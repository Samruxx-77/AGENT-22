# Troubleshooting and FAQs

- **Tests fail on `ruamel` import:** the repo conftest needs the pm test environment. For mission-control tests only, use `--noconftest` in a plain venv (see README). For the full suite, use `scripts/run_tests.sh` on a pm environment.
- **browser_exec not visible:** check `agent.disabled_toolsets`.
- **Browser smoke NOT RUN:** install Chromium via `hermes pm install chromium` on a real Hermes install; see `docs/browser.md`.
- **Discord/WhatsApp denied:** check identity mapping and allowlists; display names never authorize.
- **Mission waiting_for_approval:** `hermes mission approve <id>`.
- **Costs are estimates:** router/budget figures are not bills.
- **Is AGENT 22 human?** No. Companion Mode states it is an AI.
