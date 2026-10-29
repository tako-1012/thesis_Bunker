# Instructions for coding agents (Codex etc.)

This repository holds a master's student's research on terrain-aware path
planning for a tracked UGV (AgileX BUNKER). The active, trustworthy code is in
`conference/`. Everything outside `conference/` is legacy thesis material:
do not use it, do not modify it.

## Setup and checks
```bash
pip install numpy scipy matplotlib pandas
cd conference
python3 -m tests.test_planners        # must pass before and after your change
```
Run every test file under `conference/tests/` before you finish.

## Branches
- `realtime-map`: base branch for new research work. Open pull requests
  against `realtime-map`, never against `main` or `claude/laughing-tesla-igaehc`.
- Commit `ac9d9e7` is the ICAROB 2026 submission state. Never rewrite history.

## Protected paths (do not modify, unless a task file explicitly says so)
- `conference/paper/` (paper, generated tables, figures)
- `conference/results/*.csv`, `conference/results/*.json`, `conference/results/explore/`,
  `conference/results/online/`
- `conference/tapp/planners.py`, `metrics.py`, `scenario.py`, `terrain.py`,
  `traversability.py`, `config.py`, `aniso.py`
- `conference/experiments/run_all.py`, `analyze*.py`, `run_weight_opt.py`, `run_roll.py`,
  `run_infeasible.py`
Existing results must stay reproducible bit-for-bit. Add new behaviour in new
modules or behind new keyword arguments whose default keeps the old behaviour.

## Research-integrity rules (strict)
- Never hard-code, model or "fill in" experimental results. Every number must come
  from running the planners. If something cannot be computed, say so in the PR.
- Never tune parameters on the test seeds (`range(10)`). Validation seeds are
  `range(100, 105)`.
- All randomness must be seeded and must not depend on Python's `hash()`.
- Do not weaken or delete tests to make them pass.

## Style
- Python 3, numpy/scipy only (no new heavy dependencies). Match the existing style:
  short module docstring explaining the method, comments only where needed.
- Results of new experiments go to a new folder `conference/results/<task-name>/`
  (CSV + the printed summary as `*_log.txt`). Keep files < 5 MB.

## Reporting (PR description)
1. What was implemented (files, functions).
2. Exact commands run and their full test output.
3. The summary table printed by the experiment script (copy it verbatim).
4. Anything you could not do or are unsure about.

Task specifications live in `conference/tasks/`. Follow the task file exactly;
if it is ambiguous, choose the simpler option and state the choice in the PR.
