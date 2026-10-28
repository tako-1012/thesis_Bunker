#!/usr/bin/env python3
"""Analyse E6 (weight optimisation). Selection uses the VALIDATION split only.

Mission profiles (objectives are alpha-independent, measured on ground truth):
  E  energy   : minimise median energy change vs. A*
  S  safety   : minimise median 95th-pct. slope s.t. median length change <= 10 %
  B  balanced : knee of the (energy, slope) Pareto front = config closest to the
                utopia point after min-max normalisation over the front

Outputs: paper/figures/weights.{pdf,png}, paper/generated/table_weights.tex,
paper/generated/numbers_weights.tex, results/weight_opt_summary.csv
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                    # noqa: E402
import pandas as pd                                   # noqa: E402

from analyze import GEN, FIG, RES, INK, MUTED, Numbers, KINDS  # noqa: E402

KEY = ["kind", "side_m", "seed"]
LEN_CAP = 10.0
PROFILES = {"E": "energy", "S": "safety", "B": "balanced"}
PCOLOR = {"E": "#2a78d6", "S": "#eb6834", "B": "#1baf7a", "D": "#6b6b6b"}
PMARK = {"E": "o", "S": "^", "B": "s", "D": "D"}


def load():
    d = pd.read_csv(os.path.join(RES, "weight_opt.csv"))
    ref = d[d.planner == "A*"].set_index(["split"] + KEY)
    t = d[d.planner == "TA*-S"].copy()
    t["alpha"] = t.alpha.fillna(-1.0)          # w=0 has no alpha
    j = t.join(ref[["energy_kj", "length_xy"]].rename(columns=lambda c: c + "_A"), on=["split"] + KEY)
    j["energy_rel"] = 100 * (j.energy_kj / j.energy_kj_A - 1)
    j["len_rel"] = 100 * (j.length_xy / j.length_xy_A - 1)
    j["rough_mm"] = 1000 * j.p95_rough
    return j


def summarise(j):
    return j.groupby(["w", "alpha"]).agg(
        energy=("energy_rel", "median"), length=("len_rel", "median"),
        slope=("p95_slope", "median"), rough=("rough_mm", "median"),
        maxslope=("max_slope", "median"), time=("time", "median"), n=("seed", "size")).reset_index()


def pareto(s):
    pts = s[["energy", "slope"]].to_numpy()
    keep = []
    for i, p in enumerate(pts):
        dominated = np.any(np.all(pts <= p, axis=1) & np.any(pts < p, axis=1))
        keep.append(not dominated)
    return s[np.array(keep)]


def select(s):
    out = {"E": s.loc[s.energy.idxmin()]}
    ok = s[s.length <= LEN_CAP]
    out["S"] = ok.sort_values(["slope", "length"]).iloc[0]
    f = pareto(s)
    e = (f.energy - f.energy.min()) / max(np.ptp(f.energy), 1e-9)
    sl = (f.slope - f.slope.min()) / max(np.ptp(f.slope), 1e-9)
    out["B"] = f.loc[np.hypot(e, sl).idxmin()]
    return out


def cfg(r):
    return (float(r["w"]), float(r["alpha"]))


def label(c):
    w, a = c
    return f"w={w:g}" + ("" if a < 0 else f", $\\alpha$={a:g}")


def main():
    N = Numbers()
    j = load()
    val, test = j[j.split == "val"], j[j.split == "test"]
    sv, st = summarise(val), summarise(test)
    sv.assign(split="val").to_csv(os.path.join(RES, "weight_opt_summary.csv"), index=False)
    st.assign(split="test").to_csv(os.path.join(RES, "weight_opt_summary.csv"), mode="a", header=False, index=False)
    N["woNConfigs"] = len(sv)
    N["woNVal"] = val.groupby(KEY).ngroups
    N["woNTest"] = test.groupby(KEY).ngroups
    sel = {p: cfg(r) for p, r in select(sv).items()}
    import json
    with open(os.path.join(RES, "selected_weights.json"), "w") as f:
        json.dump({"main_profile": "balanced",
                   "main": {"w": sel["B"][0], "alpha": sel["B"][1]},
                   "profiles": {PROFILES[p]: {"w": c[0], "alpha": c[1]} for p, c in sel.items()},
                   "selected_on": "validation split only", "len_cap_percent": LEN_CAP}, f, indent=2)

    # ---------- stability: bootstrap over validation scenarios ----------
    rng = np.random.default_rng(0)
    groups = [g for _, g in val.groupby(KEY)]
    counts = {p: {} for p in PROFILES}
    B = 300
    N["nBoot"] = B
    for _ in range(B):
        idx = rng.integers(0, len(groups), len(groups))
        sb = summarise(pd.concat([groups[i] for i in idx]))
        for p, r in select(sb).items():
            c = cfg(r)
            counts[p][c] = counts[p].get(c, 0) + 1
    # ---------- stability: leave one terrain family out ----------
    lofo = {p: [] for p in PROFILES}
    for k in KINDS:
        for p, r in select(summarise(val[val.kind != k])).items():
            lofo[p].append(cfg(r))

    # ---------- table: selected configs, test performance ----------
    rows = []
    test_idx = test.set_index(KEY)
    for p in ("E", "S", "B"):
        w, a = sel[p]
        d = test_idx[(test_idx.w == w) & (test_idx.alpha == a)]
        rows.append((p, (w, a), d, 100 * counts[p].get(sel[p], 0) / B, sum(c == sel[p] for c in lofo[p])))

    def line(name, c, d, extra):
        a = "--" if c[1] < 0 else f"{c[1]:g}"
        return (f"{name} & {c[0]:g} & {a} & {d.energy_rel.median():.1f} & {d.len_rel.median():.1f} & "
                f"{d.p95_slope.median():.1f} & {d.rough_mm.median():.1f} & {extra} \\\\")

    body = []
    for p, c, d, boot, same in rows:
        body.append(line(PROFILES[p].capitalize(), c, d, f"{boot:.0f}\\%, {same}/4"))
        tag = PROFILES[p].capitalize()
        N[f"wo{tag}W"] = f"{c[0]:g}"
        N[f"wo{tag}Alpha"] = "--" if c[1] < 0 else f"{c[1]:g}"
        N[f"wo{tag}Energy"] = f"{d.energy_rel.median():.1f}"
        N[f"wo{tag}Len"] = f"{d.len_rel.median():.1f}"
        N[f"wo{tag}Slope"] = f"{d.p95_slope.median():.1f}"
        N[f"wo{tag}Rough"] = f"{d.rough_mm.median():.1f}"
        N[f"wo{tag}Boot"] = f"{boot:.0f}"
        N[f"wo{tag}Lofo"] = same
    with open(os.path.join(GEN, "table_weights.tex"), "w") as f:
        f.write("% AUTO-GENERATED by analyze_weights.py\n\\begin{table}[t]\n\\centering\n"
                "\\caption{Weights selected on the validation split for three mission profiles and their "
                "performance on the test split (medians; $\\Delta$ relative to A$^*$). Stability: share of "
                f"{B} bootstrap resamples of the validation split that select the same weights / number of "
                "leave-one-terrain-family-out selections (out of 4) that agree.}\n"
                "\\label{tab:weights}\n\\setlength{\\tabcolsep}{1.5pt}\n"
                "\\begin{tabular}{lrrrrrrr}\n\\toprule\n"
                "Profile & $w$ & $\\alpha$ & $\\Delta E$ [\\%] & $\\Delta L$ [\\%] & slope$_{95}$ [$^\\circ$] & "
                "rough.$_{95}$ [mm] & stab. \\\\\n\\midrule\n"
                + "\n".join(body) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n")
    N.write(os.path.join(GEN, "numbers_weights.tex"))

    # ---------- figure ----------
    fig, axs = plt.subplots(1, 3, figsize=(7.16, 2.1), gridspec_kw={"width_ratios": [1, 1, 1.15]})
    ws = sorted(sv.w.unique())
    al = sorted(a for a in sv.alpha.unique() if a >= 0)
    for ax, col, title, cmap in ((axs[0], "energy", r"median $\Delta$energy [%]", "Blues_r"),
                                 (axs[1], "slope", r"median slope$_{95}$ [deg]", "Blues_r")):
        M = np.full((len(al), len(ws)), np.nan)
        for _, r in sv.iterrows():
            if r.alpha >= 0:
                M[al.index(r.alpha), ws.index(r.w)] = r[col]
            else:
                M[:, ws.index(r.w)] = r[col]
        im = ax.imshow(M, origin="lower", aspect="auto", cmap=cmap)
        for (yy, xx), v in np.ndenumerate(M):
            ax.text(xx, yy, f"{v:.1f}", ha="center", va="center", fontsize=4.6,
                    color="white" if (v - np.nanmin(M)) < 0.45 * np.nanmax(M - np.nanmin(M)) else INK)
        ax.set_xticks(range(len(ws)))
        ax.set_xticklabels([f"{w:g}" for w in ws], fontsize=5.5)
        ax.set_yticks(range(len(al)))
        ax.set_yticklabels([f"{a:g}" for a in al])
        ax.set_xlabel("terrain weight $w$")
        ax.set_ylabel(r"slope share $\alpha$")
        ax.set_title(title + " (validation)", fontsize=7)
        ax.grid(False)
        for p, (w, a) in sel.items():
            yy = al.index(a) if a >= 0 else 0
            ax.plot(ws.index(w), yy, PMARK[p], mfc="none", mec=PCOLOR[p], ms=9, mew=1.6)
    ax = axs[2]
    ax.plot(sv.energy, sv.slope, ".", color="#bdbdbd", ms=4, label="all configs")
    f = pareto(sv).sort_values("energy")
    ax.plot(f.energy, f.slope, "-", color=MUTED, lw=0.8, label="Pareto front")
    for p, (w, a) in sel.items():
        r = sv[(sv.w == w) & (sv.alpha == a)].iloc[0]
        ax.plot(r.energy, r.slope, PMARK[p], color=PCOLOR[p], ms=5.5, label=f"{PROFILES[p]}: {label((w, a))}")
    ax.set_xlabel(r"median $\Delta$energy vs. A$^*$ [%]")
    ax.set_ylabel(r"median slope$_{95}$ [deg]")
    ax.set_title("trade-off (validation)", fontsize=7)
    ax.legend(frameon=False, fontsize=5, loc="upper right")
    fig.tight_layout(pad=0.3)
    fig.savefig(os.path.join(FIG, "weights.pdf"))
    fig.savefig(os.path.join(FIG, "weights.png"))
    plt.close(fig)

    print("selected:", {PROFILES[p]: label(c) for p, c in sel.items()})
    print("bootstrap:", {PROFILES[p]: sorted(((v, label(c)) for c, v in counts[p].items()), reverse=True)[:3]
                         for p in PROFILES})
    print("LOFO:", {PROFILES[p]: [label(c) for c in v] for p, v in lofo.items()})
    print(open(os.path.join(GEN, "table_weights.tex")).read())


if __name__ == "__main__":
    main()
