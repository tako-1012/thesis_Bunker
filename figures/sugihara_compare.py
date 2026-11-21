"""就活の動画（ヤマハ発動機インターンのエントリー）用：改善前と改善後の経路を、地形の走りにくさの地図の上で比べる図。

使うのはリポジトリの実際の結果だけ：
  - 砂浜は ICAROB 要旨の図と同じ規則で選んだもの（conference/experiments/abstract_figure.py の rule_first、08OB86_-0205）。
  - 経路は同じ設定で計画し直し、保存済みの conference/results/real_beach_las/offline.csv と一致することを確かめてから描く（一致しなければ止まる）。
  - 背景の色は、計画に使う地形の走りにくさ（傾きと凸凹から作るコスト、TraversabilityMap.cost）。
  - 「走りにくさの合計」は、経路に沿った走りにくさの合計（長さ × 経路上の平均コスト）。図には丸めた割合だけを書く。
改善前＝地形を考えない最短経路（A*）、改善後＝地形を考えた経路（TA*-S）。図にはアルゴリズム名を書かない。

実行：python3 figures/sugihara_compare.py（リポジトリの直下から）
出力：figures/sugihara_compare.png（1600×900、背景は白）
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "conference"))
from experiments.abstract_figure import OFFLINE, paths_for  # noqa: E402
from tapp.config import RESOLUTION  # noqa: E402

PATCH = "08OB86_-0205"
OUT = ROOT / "figures" / "sugihara_compare.png"
NAVY, TEAL = "#14213D", "#0B8793"
FONTS = ["Meiryo", "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Hiragino Kaku Gothic Pro",
         "IPAGothic", "IPAPGothic", "Noto Sans CJK JP"]


def japanese_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in FONTS:
        if name in available:
            return name
    raise RuntimeError("日本語のフォントが見つかりません（メイリオかヒラギノ角ゴを入れてください）")


def main():
    font = japanese_font()
    plt.rcParams.update({"font.family": font, "font.size": 28})
    offline = pd.read_csv(OFFLINE)
    sc, paths = paths_for(PATCH, offline)
    for label, p in paths.items():
        if not all(ok for _, _, ok in p["check"].values()):
            raise RuntimeError(f"{label}: 保存済みの結果と一致しない")
    tm = sc["tmap"]
    totals = {k: p["metrics"]["length_xy"] * p["metrics"]["mean_cost"] for k, p in paths.items()}
    ratio = totals["TA*-S"] / totals["A*"]
    print(f"font={font}  走りにくさの合計  改善前 {totals['A*']:.3f}  改善後 {totals['TA*-S']:.3f}  比 {ratio:.3f}")

    # 1600×900 px（16:9）、背景は白。右下の約 25%（x>1200, y>675 px）には何も置かない。
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor="white")

    # 地図：経路の範囲（横に長い帯）に合わせた窓。上側の全幅に置く。
    pts = np.vstack([(p["path"] + 0.5) * RESOLUTION for p in paths.values()])
    x0, x1 = pts[:, 0].min() - 22, pts[:, 0].max() + 22
    ax_w_px, ax_h_px = 1500, 470
    yc = (pts[:, 1].min() + pts[:, 1].max()) / 2
    half_h = (x1 - x0) * ax_h_px / ax_w_px / 2
    y0, y1 = yc - half_h, yc + half_h
    ax = fig.add_axes([50 / 1600, 1 - (140 + ax_h_px) / 900, ax_w_px / 1600, ax_h_px / 900])
    n = tm.shape[0]
    cmap = LinearSegmentedColormap.from_list("difficulty", ["#FFFFFF", "#D9DEE4", "#8A939E", "#3E4652"])
    image = ax.imshow(np.clip(tm.cost, 0, 1).T, origin="lower", extent=[0, n * RESOLUTION, 0, n * RESOLUTION],
                      cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
    before = (paths["A*"]["path"] + 0.5) * RESOLUTION
    after = (paths["TA*-S"]["path"] + 0.5) * RESOLUTION
    ax.plot(before[:, 0], before[:, 1], color=NAVY, lw=5, ls=(0, (2.2, 1.4)), solid_capstyle="round")
    ax.plot(after[:, 0], after[:, 1], color=TEAL, lw=6, solid_capstyle="round")
    for xy, text, align in [(before[0], "出発", "right"), (before[-1], "到着", "left")]:
        ax.plot(*xy, marker="o", ms=16, mfc="white", mec=NAVY, mew=4, ls="none", zorder=5)
        ax.annotate(text, xy, xytext=(-22 if align == "right" else 22, 0), textcoords="offset points",
                    ha=align, va="center", fontsize=28, color=NAVY, weight="bold")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")  # 窓の縦横を軸の縦横に合わせてあるので、ゆがまない
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#B8C0C8")

    # 見出し（左上）
    fig.text(50 / 1600, 1 - 70 / 900, "地形の走りにくさで、経路を比べる", fontsize=40, color=NAVY, weight="bold", va="center")

    # 色の目盛り（地図の下、左側）
    cax = fig.add_axes([50 / 1600, 1 - 680 / 900, 420 / 1600, 26 / 900])
    bar = fig.colorbar(image, cax=cax, orientation="horizontal", ticks=[])
    bar.outline.set_edgecolor("#B8C0C8")
    fig.text(50 / 1600, 1 - 720 / 900, "走りやすい", fontsize=28, color=NAVY, va="top")
    fig.text(470 / 1600, 1 - 720 / 900, "走りにくい", fontsize=28, color=NAVY, va="top", ha="right")

    # 凡例（色の目盛りの右、中央より左）
    lx, ly = 560, 640
    for i, (label, color, style, lw) in enumerate([("改善前", NAVY, (0, (2.2, 1.4)), 5), ("改善後", TEAL, "-", 6)]):
        y = 1 - (ly + i * 62) / 900
        fig.add_artist(plt.Line2D([lx / 1600, (lx + 90) / 1600], [y, y], color=color, lw=lw, ls=style,
                                  transform=fig.transFigure))
        fig.text((lx + 110) / 1600, y, label, fontsize=30, color=NAVY, va="center")

    # 結果のひとこと（下の左、右下の 25% には入れない）
    lead = fig.text(50 / 1600, 1 - 820 / 900, "走りにくさの合計が", fontsize=30, color=NAVY, va="center")
    fig.canvas.draw()
    lead_right = lead.get_window_extent().x1 / fig.bbox.width  # 文字の幅に合わせて、重ならないよう右に続ける
    fig.text(lead_right + 12 / 1600, 1 - 820 / 900, "約半分に", fontsize=44, color=TEAL, weight="bold", va="center")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=100, facecolor="white")
    plt.close(fig)
    print("saved", OUT)


if __name__ == "__main__":
    main()
