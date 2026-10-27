---
name: mission-control
description: "Run bounded, resumable tasks with budgets and verification."
version: 0.1.0
author: SAM
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Missions, Planning, Budgets, Verification, Audit]
---

# Mission Control Skill

Run multi-step work as a mission that survives a restart, stays inside
a workspace, and is never called done without proof. It does not replace
the agent's normal tools; it wraps bounded work in state, limits and
verification.

## When to Use

- "Run this multi-step job and resume it if it stops."
- "Do this inside this folder only, and prove the output exists."
- "Stop if it costs more than this, or takes more than this many steps."
- "Audit my own file for dangerous patterns before I ship it."

Don't use for: a one-line question, a single file read, or any target
you do not own or are not authorised to test.

## Prerequisites

- The mission-control plugin in this repo (`plugins/mission-control/`).
- A workspace directory the steps are allowed to use.
- For audit only: explicit confirmation that you own or are authorised
  to test the target (`--i-own-this`).

## How to Run

```bash
hermes mission create "Write a summary" --plan "Read the notes" --step "write=python3 -c \"open('out.txt','w').write('hi')\""
hermes mission run <mission-id> --workspace /path/to/workspace
hermes mission status <mission-id>
hermes mission report <mission-id>
```

## Quick Reference

```bash
hermes mission pause <mission-id> | hermes mission resume <mission-id> | hermes mission cancel <mission-id>
hermes mission approve <mission-id>
hermes mission budget <task-id> --cost 0.04 --max-task-cost 0.25 --daily-budget 2.00
hermes mission audit <file> --workspace /path/to/workspace --i-own-this --mode analyse
```

## Procedure

### 1. Create the mission with a goal, a plan and steps

Steps are argv lists, never shell strings. No `;`, no pipes smuggled
in. Mark a step idempotent only if re-running it is safe.

### 2. Run it inside the workspace

Steps and verification checks stay inside `--workspace`. Output paths
that escape it, or touch protected files, are refused.

### 3. Check the report, not just the exit code

Every step that creates a deliverable gets a verification check
(`file_exists`, `file_nonempty`, `file_contains`). A mission with a
failed check is FAILED, never completed.

### 4. Respect limits and cancellation

Non-idempotent steps are never auto-retried. Idempotent steps retry
only on transient errors, bounded by max_retries, with backoff.
Cancellation and pause are checked before every step. A cancelled
mission starts no new step. Costs are estimates: never silently switch
to a pricier model; if no fallback fits the ceiling, stop and ask.

## Pitfalls

- Putting a secret into a goal, plan, step command or mission output.
  Never do this; mission records are persisted as JSON.
- Marking a destructive step idempotent so it auto-retries.
- Calling a mission done because its last command exited 0 while its
  verification check failed. The report's verification section decides.

## Verification

- `hermes mission report <mission-id>` shows status, steps completed,
  verification evidence, remaining issues and estimated cost.
- For audit, `analyse` flags patterns for the owner to review, `strings`
  extracts printable strings from your own binary, and `debug` runs
  your own `.py` file bounded, inside the workspace.
- Audit only files you own or are authorised to test, inside the
  workspace. No network targets, no other people's accounts or systems,
  no credential theft, no authentication bypass. If a target is not
  confirmed as yours, refuse and explain why.
