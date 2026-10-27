# Contributing to AGENT 22

Thank you for considering a contribution. AGENT 22 is a fork of Hermes Agent by Nous Research (MIT); upstream contributions should go to the upstream repository. Contributions here should target AGENT 22 additions, especially the mission-control plugin.

## Ground rules
- Keep changes in `plugins/mission-control/` where possible. Do not edit upstream core files without a documented fork reason in the PR and in `CHANGELOG.md` (the AGENT 22 identity edits are the documented exception).
- Add tests that mirror the source layout (`tests/plugins/`). Tests must never write to `~/.hermes/`. Prefer `scripts/run_tests.sh` on a pm environment; the mission-control tests also run with pytest `--noconftest` in a plain venv (see README).
- Never commit secrets, tokens, `.env` files, session databases, browser profiles, chat logs, personal memory files, or runtime store JSON. Health checks report env presence only, never values.
- Label every new feature honestly: implemented and tested, implemented but not live-tested, experimental/partially implemented, or planned. Never advertise a planned feature as operational.
- Do not remove license or attribution notices. Do not claim ownership of upstream code. Do not disable security checks to make tests pass.
- Follow upstream house rules where they apply: stdlib + pytest only for the mission-control plugin, skill `description` <= 60 chars, one sentence, ending with a period.

## How to contribute
1. Open an issue describing the change, with a reproduction or use case.
2. Fork, branch, implement, add/update tests, update README/CHANGELOG with the honest status label.
3. Run the mission-control test suite and `python3 -m py_compile` on changed Python files.
4. Open a pull request using `.github/PULL_REQUEST_TEMPLATE.md`, with a clear description, test evidence, and any security implications.

## Security reports
See `SECURITY.md`. Do not open public issues for vulnerabilities.
