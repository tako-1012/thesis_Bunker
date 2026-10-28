# Terrain-Aware A* — reproducible conference package

Self-contained re-implementation and re-evaluation of the thesis work for an
international conference submission. See `AUDIT_ja.md` (Japanese) for why the
thesis numbers are not reused.

## Layout
```
tapp/            library: terrain generation, traversability, planners, metrics
tests/           correctness tests (A*/TA* optimality vs. scipy Dijkstra, ...)
experiments/     run_all.py (all experiments) and analyze.py (tables, figures, numbers)
results/         raw results (CSV), validation sweep, metadata, example paths
paper/           IEEE conference paper; generated/ and figures/ are produced by analyze.py
```

## Reproduce
```bash
pip install numpy scipy matplotlib pandas
cd conference
python3 -m tests.test_planners
python3 experiments/run_weight_opt.py  # grid over (w, alpha) on validation + test, ~6 min
python3 experiments/analyze_weights.py # selects weights on VALIDATION only -> results/selected_weights.json
python3 experiments/run_all.py         # main experiments with the selected weights, ~3 min
python3 experiments/run_infeasible.py   # maps without a feasible path
python3 experiments/run_roll.py         # roll-aware extension (TA*-S-R), ~1 min
python3 experiments/analyze.py
python3 experiments/analyze_roll.py
python3 experiments/demo_figures.py     # illustrative figures (paper/figures/demo/)
python3 experiments/demo_roll.py craters 0
cd paper && latexmk -pdf main.tex
```

Every number in the paper comes from `paper/generated/numbers.tex`, written by
`analyze.py` from `results/`. Do not edit numbers in `main.tex` by hand.
