# thesis_Bunker

Terrain-aware path planning for the tracked UGV AgileX BUNKER
(bachelor's thesis → ICAROB 2026 → master's thesis).

## Layout
| Path | Content | Status |
|---|---|---|
| `conference/` | Reproducible re-implementation and evaluation (planners, experiments, ICAROB paper, exploratory work). **Use this for all new work.** See `conference/README.md`. | active |
| `conference/tasks/` | Task specifications for coding agents (see `AGENTS.md`). | active |
| `ros2/` | ROS2 workspace for the robot; most packages come from the lab repositories `hayashilab/bunker_ros2` and `hayashilab/bunker_unity`. | do not modify here |
| `unity/`, `archive/unity_scripts/`, `scripts/launch_*.sh` | Unity visualisation of planned paths and launch scripts. | kept |
| `thisis_write/` | Bachelor's thesis manuscript (LaTeX) and its figures. | archived |
| `scripts/`, `analysis/`, `benchmark_results/`, `results/`, `tables/`, `figures/`, `terrain_test_scenarios/` | Only the scripts and data used for the bachelor's thesis figures and tables. | archived |
| `documents/` | Literature lists and notes. | reference |

The bachelor's thesis numbers have known problems (hard-coded parameter-tuning
results, inconsistent statistics); see `conference/AUDIT_ja.md`. Do not reuse
them. Experiment code and results that were not used in the thesis were
removed; they remain available in the git history (e.g. commit `ac9d9e7`,
the ICAROB submission state).

## Quick start
```bash
pip install numpy scipy matplotlib pandas
cd conference
python3 -m tests.test_planners
```
