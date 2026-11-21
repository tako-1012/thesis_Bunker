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

    # 1600×900 px（16:9）、背景は白。左に正方形の地図、右上に文字。右下の約 25%（x>1200, y>675 px）には何も置かない。
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor="white")
    px = lambda x, y, w, h: [x / 1600, 1 - (y + h) / 900, w / 1600, h / 900]

    # 正方形の地図：出発から到着まで、経路全体が入る正方形の窓（地図の中に収める）。
    pts = np.vstack([(p["path"] + 0.5) * RESOLUTION for p in paths.values()])
    side = (pts.max(axis=0) - pts.min(axis=0)).max() + 20
    n_m = tm.shape[0] * RESOLUTION
    lo = np.clip((pts.max(axis=0) + pts.min(axis=0)) / 2 - side / 2, 0, n_m - side)
    hi = lo + side
    ax = fig.add_axes(px(40, 50, 800, 800))
    n = tm.shape[0]
    # 走りやすい（明るい砂色）→ 走りにくい（赤）。表示は 0.6 で頭打ち（それ以上は同じ赤）。
    cmap = LinearSegmentedColormap.from_list("difficulty", ["#FFF8E7", "#FFE08A", "#F4A259", "#D64933", "#8C1C13"])
    image = ax.imshow(np.clip(tm.cost, 0, 0.6).T, origin="lower", extent=[0, n * RESOLUTION, 0, n * RESOLUTION],
                      cmap=cmap, vmin=0, vmax=0.6, interpolation="bilinear")
    before = (paths["A*"]["path"] + 0.5) * RESOLUTION
    after = (paths["TA*-S"]["path"] + 0.5) * RESOLUTION
    # 海とデータのない所は水色（走らない場所）
    sea = np.asarray(sc["water"] | sc["nodata"], bool)
    ax.imshow(np.ma.masked_where(~sea.T, sea.T), origin="lower", extent=[0, n * RESOLUTION, 0, n * RESOLUTION],
              cmap=LinearSegmentedColormap.from_list("sea", ["#BFDDEB", "#BFDDEB"]), vmin=0, vmax=1,
              interpolation="nearest")
    for line, color in [(before, NAVY), (after, TEAL)]:
        ax.plot(line[:, 0], line[:, 1], color="white", lw=12, solid_capstyle="round", solid_joinstyle="round")
        ax.plot(line[:, 0], line[:, 1], color=color, lw=7, solid_capstyle="round", solid_joinstyle="round")
    for xy, text in [(before[0], "出発"), (before[-1], "到着")]:
        ax.plot(*xy, marker="o", ms=22, mfc="white", mec=NAVY, mew=5, ls="none", zorder=5)
        ax.annotate(text, xy, xytext=(0, 26), textcoords="offset points", ha="center", va="bottom",
                    fontsize=30, color=NAVY, weight="bold",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # 右上：見出し
    fig.text(900 / 1600, 1 - 95 / 900, "地形の走りにくさで", fontsize=40, color=NAVY, weight="bold", va="center")
    fig.text(900 / 1600, 1 - 160 / 900, "経路を比べる", fontsize=40, color=NAVY, weight="bold", va="center")

    # 凡例
    for i, (label, color) in enumerate([("改善前", NAVY), ("改善後", TEAL)]):
        y = 1 - (260 + i * 70) / 900
        fig.add_artist(plt.Line2D([900 / 1600, 1000 / 1600], [y, y], color=color, lw=9, solid_capstyle="round",
                                  transform=fig.transFigure))
        fig.text(1025 / 1600, y, label, fontsize=32, color=NAVY, va="center")

    # 色の目盛り
    cax = fig.add_axes(px(900, 440, 520, 30))
    bar = fig.colorbar(image, cax=cax, orientation="horizontal", ticks=[])
    bar.outline.set_edgecolor(NAVY)
    fig.text(900 / 1600, 1 - 485 / 900, "走りやすい", fontsize=28, color=NAVY, va="top")
    fig.text(1420 / 1600, 1 - 485 / 900, "走りにくい", fontsize=28, color=NAVY, va="top", ha="right")

    # 結果のひとこと（右下の 25% より上）
    fig.text(900 / 1600, 1 - 590 / 900, "走りにくさの合計が", fontsize=30, color=NAVY, va="center")
    fig.text(900 / 1600, 1 - 645 / 900, "約半分に", fontsize=48, color=TEAL, weight="bold", va="center")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=100, facecolor="white")
    plt.close(fig)
    print("saved", OUT)


if __name__ == "__main__":
    main()
