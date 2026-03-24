import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap

# Output directory
OUT_DIR = "figures_presentation"
os.makedirs(OUT_DIR, exist_ok=True)

# Global style
plt.rcParams["font.family"] = [
    "Noto Sans CJK JP",
    "DejaVu Sans",
]
plt.rcParams["axes.titlesize"] = 12
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["xtick.labelsize"] = 10
plt.rcParams["ytick.labelsize"] = 10
plt.rcParams["legend.fontsize"] = 10

# Helper for saving both SVG and PNG

def save_fig(fig, name_base, dpi=200):
    svg_path = os.path.join(OUT_DIR, f"{name_base}.svg")
    png_path = os.path.join(OUT_DIR, f"{name_base}.png")
    fig.savefig(svg_path, bbox_inches="tight", facecolor="white")
    fig.savefig(png_path, bbox_inches="tight", dpi=dpi, facecolor="white")
    plt.close(fig)
    return svg_path, png_path


def _normalize_with_percentile_clip(a, p_low=2, p_high=98):
    low, high = np.percentile(a, [p_low, p_high])
    if high - low < 1e-9:
        return np.zeros_like(a)
    clipped = np.clip(a, low, high)
    return (clipped - low) / (high - low)

# ① Tc heatmaps

def make_tc_heatmaps():
    np.random.seed(7)
    n = 80
    x = np.linspace(-1, 1, n)
    y = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(x, y)

    # Base terrain: gentle hills + noise
    Z = (
        0.7 * np.exp(-((X + 0.2) ** 2 + (Y + 0.1) ** 2) / 0.15)
        + 0.5 * np.exp(-((X - 0.4) ** 2 + (Y - 0.3) ** 2) / 0.08)
        + 0.2 * np.exp(-((X + 0.5) ** 2 + (Y - 0.5) ** 2) / 0.2)
    )
    Z += 0.05 * np.random.randn(n, n)

    # Metrics
    # h_diff: local difference magnitude
    h_diff = np.abs(np.gradient(Z)[0]) + np.abs(np.gradient(Z)[1])
    # slope: gradient magnitude
    gx, gy = np.gradient(Z)
    theta_slope = np.sqrt(gx**2 + gy**2)
    # roughness: local std (approx by gradient variance)
    r_rough = np.sqrt((gx - gx.mean()) ** 2 + (gy - gy.mean()) ** 2)

    # Normalize to [0,1]
    def norm(a):
        a = a - a.min()
        return a / (a.max() + 1e-9)

    h_diff_n = norm(h_diff)
    theta_n = norm(theta_slope)
    rough_n = norm(r_rough)

    # Tc
    alpha, beta, gamma = 0.4, 0.4, 0.2
    tc = alpha * h_diff_n + beta * theta_n + gamma * rough_n
    tc_n = norm(tc)

    # Colormap
    cmap = LinearSegmentedColormap.from_list(
        "tcmap", ["#f7f7f7", "#d9e2f3", "#9ab0d6", "#6b7fa8"]
    )

    fig, axes = plt.subplots(1, 4, figsize=(12, 3.6))
    titles = ["標高差 h_diff", "傾斜角 θ_slope", "表面粗さ r_rough", "統合指標 Tc"]
    data_list = [h_diff_n, theta_n, rough_n, tc_n]

    for i, ax in enumerate(axes):
        im = ax.imshow(data_list[i], cmap=cmap, origin="lower")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(titles[i])

        # Low/High legend
        ax.text(0.02, 0.05, "Low", color="#333333", transform=ax.transAxes, fontsize=9)
        ax.text(0.85, 0.05, "High", color="#333333", transform=ax.transAxes, fontsize=9)

        # Emphasize Tc panel
        if i == 3:
            for spine in ax.spines.values():
                spine.set_linewidth(1.5)
                spine.set_edgecolor("#4e5f7c")

    # Formula below
    fig.text(
        0.5,
        -0.02,
        "Tc = α·h_diff + β·θ_slope + γ·r_rough  (α=0.4, β=0.4, γ=0.2)",
        ha="center",
        va="top",
        fontsize=11,
    )

    fig.tight_layout()
    return save_fig(fig, "tc_heatmaps")


def make_tc_heatmaps_fixed():
    np.random.seed(7)
    n = 90
    x = np.linspace(-1, 1, n)
    y = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(x, y)

    # Base terrain: gentle hills + noise
    Z = (
        0.7 * np.exp(-((X + 0.2) ** 2 + (Y + 0.1) ** 2) / 0.15)
        + 0.5 * np.exp(-((X - 0.4) ** 2 + (Y - 0.3) ** 2) / 0.08)
        + 0.2 * np.exp(-((X + 0.5) ** 2 + (Y - 0.5) ** 2) / 0.2)
    )
    Z += 0.05 * np.random.randn(n, n)

    # Metrics
    h_diff = np.abs(np.gradient(Z)[0]) + np.abs(np.gradient(Z)[1])
    gx, gy = np.gradient(Z)
    theta_slope = np.sqrt(gx**2 + gy**2)
    r_rough = np.sqrt((gx - gx.mean()) ** 2 + (gy - gy.mean()) ** 2)

    # Normalize with percentile clipping for higher contrast
    h_diff_n = _normalize_with_percentile_clip(h_diff)
    theta_n = _normalize_with_percentile_clip(theta_slope)
    rough_n = _normalize_with_percentile_clip(r_rough)

    alpha, beta, gamma = 0.4, 0.4, 0.2
    tc = alpha * h_diff_n + beta * theta_n + gamma * rough_n
    tc_n = _normalize_with_percentile_clip(tc)

    # Higher contrast colormap
    cmap = LinearSegmentedColormap.from_list(
        "tcmap_strong",
        ["#f7f7f7", "#c9d6ee", "#8aa5d0", "#4e5f7c", "#2f3e5a"],
    )

    fig, axes = plt.subplots(1, 4, figsize=(11.5, 3.6))
    titles = ["標高差 h_diff", "傾斜角 θ_slope", "表面粗さ r_rough", "統合指標 Tc（提案）"]
    data_list = [h_diff_n, theta_n, rough_n, tc_n]

    for i, ax in enumerate(axes):
        im = ax.imshow(
            data_list[i],
            cmap=cmap,
            origin="lower",
            interpolation="bilinear",
            vmin=0,
            vmax=1,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(titles[i])

        # Colorbar
        cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cbar.ax.tick_params(labelsize=8)

        # Emphasize Tc panel
        if i == 3:
            for spine in ax.spines.values():
                spine.set_linewidth(2.2)
                spine.set_edgecolor("#2f3e5a")

            # Optional annotation for high-cost area
            ax.annotate(
                "丘（高コスト領域）",
                xy=(0.62, 0.58),
                xytext=(0.72, 0.85),
                textcoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color="#2f3e5a", lw=1.5),
                fontsize=9,
                color="#2f3e5a",
                ha="left",
            )

    # Formula below
    fig.text(
        0.5,
        -0.02,
        "Tc = α·h_diff + β·θ_slope + γ·r_rough  (α=0.4, β=0.4, γ=0.2)",
        ha="center",
        va="top",
        fontsize=11,
    )

    fig.tight_layout()
    return save_fig(fig, "tc_heatmaps_fixed", dpi=220)


def make_tc_heatmaps_final():
    np.random.seed(7)
    n = 90
    x = np.linspace(-1, 1, n)
    y = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(x, y)

    # Base terrain: gentle hills + noise
    Z = (
        0.7 * np.exp(-((X + 0.2) ** 2 + (Y + 0.1) ** 2) / 0.15)
        + 0.5 * np.exp(-((X - 0.4) ** 2 + (Y - 0.3) ** 2) / 0.08)
        + 0.2 * np.exp(-((X + 0.5) ** 2 + (Y - 0.5) ** 2) / 0.2)
    )
    Z += 0.05 * np.random.randn(n, n)

    # Metrics
    h_diff = np.abs(np.gradient(Z)[0]) + np.abs(np.gradient(Z)[1])
    gx, gy = np.gradient(Z)
    theta_slope = np.sqrt(gx**2 + gy**2)
    r_rough = np.sqrt((gx - gx.mean()) ** 2 + (gy - gy.mean()) ** 2)

    # Normalize with percentile clipping for higher contrast
    h_diff_n = _normalize_with_percentile_clip(h_diff)
    theta_n = _normalize_with_percentile_clip(theta_slope)
    rough_n = _normalize_with_percentile_clip(r_rough)

    alpha, beta, gamma = 0.4, 0.4, 0.2
    tc = alpha * h_diff_n + beta * theta_n + gamma * rough_n
    tc_n = _normalize_with_percentile_clip(tc)

    # Higher contrast colormap
    cmap = LinearSegmentedColormap.from_list(
        "tcmap_strong",
        ["#f7f7f7", "#c9d6ee", "#8aa5d0", "#4e5f7c", "#2f3e5a"],
    )

    fig, axes = plt.subplots(1, 4, figsize=(12.5, 3.6))
    titles = ["標高差 h_diff", "傾斜角 θ_slope", "表面粗さ r_rough", "統合指標 Tc（提案）"]
    data_list = [h_diff_n, theta_n, rough_n, tc_n]

    im = None
    for i, ax in enumerate(axes):
        im = ax.imshow(
            data_list[i],
            cmap=cmap,
            origin="lower",
            interpolation="bilinear",
            vmin=0,
            vmax=1,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(titles[i], fontsize=13)

        # Emphasize Tc panel
        if i == 3:
            for spine in ax.spines.values():
                spine.set_linewidth(3.0)
                spine.set_edgecolor("#2f3e5a")

            # Optional annotation for high-cost area
            ax.annotate(
                "丘（高コスト領域）",
                xy=(0.86, 0.80),
                xytext=(0.78, 0.90),
                textcoords="axes fraction",
                arrowprops=dict(arrowstyle="->", color="#2f3e5a", lw=1.5),
                fontsize=10,
                color="#2f3e5a",
                ha="left",
                va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#2f3e5a", lw=0.8),
            )

    # Shared colorbar (right side)
    cbar = fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02)
    cbar.ax.tick_params(labelsize=9)

    # Formula below
    fig.text(
        0.5,
        -0.01,
        "Tc = α·h_diff + β·θ_slope + γ·r_rough  (α=0.4, β=0.4, γ=0.2)",
        ha="center",
        va="top",
        fontsize=12,
    )

    fig.tight_layout(pad=0.3)
    return save_fig(fig, "tc_heatmaps_final", dpi=220)


def make_tc_heatmaps_presentation():
    np.random.seed(7)
    n = 90
    x = np.linspace(-1, 1, n)
    y = np.linspace(-1, 1, n)
    X, Y = np.meshgrid(x, y)

    # Base terrain: gentle hills + noise
    Z = (
        0.7 * np.exp(-((X + 0.2) ** 2 + (Y + 0.1) ** 2) / 0.15)
        + 0.5 * np.exp(-((X - 0.4) ** 2 + (Y - 0.3) ** 2) / 0.08)
        + 0.2 * np.exp(-((X + 0.5) ** 2 + (Y - 0.5) ** 2) / 0.2)
    )
    Z += 0.05 * np.random.randn(n, n)

    # Metrics
    h_diff = np.abs(np.gradient(Z)[0]) + np.abs(np.gradient(Z)[1])
    gx, gy = np.gradient(Z)
    theta_slope = np.sqrt(gx**2 + gy**2)
    r_rough = np.sqrt((gx - gx.mean()) ** 2 + (gy - gy.mean()) ** 2)

    # Normalize with percentile clipping
    h_diff_n = _normalize_with_percentile_clip(h_diff)
    theta_n = _normalize_with_percentile_clip(theta_slope)
    rough_n = _normalize_with_percentile_clip(r_rough)

    alpha, beta, gamma = 0.4, 0.4, 0.2
    tc = alpha * h_diff_n + beta * theta_n + gamma * rough_n
    tc_n = _normalize_with_percentile_clip(tc, p_low=5, p_high=95)

    # Higher contrast colormap
    cmap = LinearSegmentedColormap.from_list(
        "tcmap_strong",
        ["#f7f7f7", "#c9d6ee", "#8aa5d0", "#4e5f7c", "#2f3e5a"],
    )

    fig = plt.figure(figsize=(12.5, 6.2))
    gs = fig.add_gridspec(2, 3, height_ratios=[1, 1.25])

    # Top row (small)
    top_titles = ["標高差 h_diff", "傾斜角 θ_slope", "表面粗さ r_rough"]
    top_data = [h_diff_n, theta_n, rough_n]
    for i in range(3):
        ax = fig.add_subplot(gs[0, i])
        ax.imshow(
            top_data[i],
            cmap=cmap,
            origin="lower",
            interpolation="bilinear",
            vmin=0,
            vmax=1,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(top_titles[i], fontsize=12)

    # Bottom row (Tc, large)
    ax_tc = fig.add_subplot(gs[1, :])
    im = ax_tc.imshow(
        tc_n,
        cmap=cmap,
        origin="lower",
        interpolation="bilinear",
        vmin=0,
        vmax=1,
    )
    ax_tc.set_xticks([])
    ax_tc.set_yticks([])
    ax_tc.set_title("統合指標 Tc（提案）", fontsize=14, pad=8)
    ax_tc.text(
        0.5,
        1.02,
        "Tc = α·h_diff + β·θ_slope + γ·r_rough  (α=0.4, β=0.4, γ=0.2)",
        transform=ax_tc.transAxes,
        ha="center",
        va="bottom",
        fontsize=10,
        color="#2f3e5a",
    )

    for spine in ax_tc.spines.values():
        spine.set_linewidth(3.0)
        spine.set_edgecolor("#2f3e5a")

    # Short arrow + label with bbox for high-cost area
    ax_tc.annotate(
        "高コスト領域",
        xy=(0.88, 0.78),
        xytext=(0.82, 0.84),
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="->", color="#2f3e5a", lw=1.5),
        fontsize=11,
        color="#2f3e5a",
        ha="left",
        va="center",
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#2f3e5a", lw=0.9),
    )

    # Shared colorbar for Tc only
    cbar = fig.colorbar(im, ax=ax_tc, fraction=0.02, pad=0.02)
    cbar.ax.tick_params(labelsize=9)

    fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.04, wspace=0.03, hspace=0.15)
    return save_fig(fig, "tc_heatmaps_presentation", dpi=220)


def make_tc_definition_flow():
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    box_style = dict(boxstyle="round,pad=0.35", fc="#f2f4f7", ec="#4e5f7c", lw=1.5)
    out_style = dict(boxstyle="round,pad=0.35", fc="#e9f0fa", ec="#2f3e5a", lw=2.0)

    # Input boxes
    ax.text(0.18, 0.75, "標高差 h_diff", ha="center", va="center", fontsize=13, bbox=box_style)
    ax.text(0.18, 0.50, "傾斜角 θ_slope", ha="center", va="center", fontsize=13, bbox=box_style)
    ax.text(0.18, 0.25, "表面粗さ r_rough", ha="center", va="center", fontsize=13, bbox=box_style)

    # Integration block
    ax.text(
        0.52,
        0.50,
        "重み付き和\n（α=0.4, β=0.4, γ=0.2）",
        ha="center",
        va="center",
        fontsize=13,
        bbox=box_style,
    )

    # Output block
    ax.text(0.85, 0.50, "統合指標 Tc（提案）", ha="center", va="center", fontsize=14, bbox=out_style)

    # Arrows from inputs to integration (longer to make the flow explicit)
    arrow_kwargs = dict(arrowstyle="->", lw=1.6, color="#2f3e5a")
    ax.annotate("", xy=(0.45, 0.75), xytext=(0.30, 0.75), arrowprops=arrow_kwargs)
    ax.annotate("", xy=(0.45, 0.50), xytext=(0.30, 0.50), arrowprops=arrow_kwargs)
    ax.annotate("", xy=(0.45, 0.25), xytext=(0.30, 0.25), arrowprops=arrow_kwargs)

    # Arrow to output
    ax.annotate("", xy=(0.75, 0.50), xytext=(0.64, 0.50), arrowprops=arrow_kwargs)

    # Formula
    ax.text(
        0.5,
        0.06,
        "Tc = 0.4h_diff + 0.4θ_slope + 0.2 r_rough",
        ha="center",
        va="center",
        fontsize=12,
        color="#2f3e5a",
    )

    fig.tight_layout()
    return save_fig(fig, "tc_definition_flow", dpi=220)


def make_tc_definition_merge():
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    box_style = dict(boxstyle="round,pad=0.4", fc="#f2f4f7", ec="#4e5f7c", lw=1.8)
    out_style = dict(boxstyle="round,pad=0.4", fc="#e9f0fa", ec="#2f3e5a", lw=2.2)

    # Input boxes (left, vertical)
    ax.text(0.12, 0.75, "標高差 h_diff", ha="center", va="center", fontsize=14, weight="bold", bbox=box_style)
    ax.text(0.12, 0.50, "傾斜角 θ_slope", ha="center", va="center", fontsize=14, weight="bold", bbox=box_style)
    ax.text(0.12, 0.25, "表面粗さ r_rough", ha="center", va="center", fontsize=14, weight="bold", bbox=box_style)

    # Merge point
    merge_x, merge_y = 0.38, 0.50
    arrow_kwargs = dict(arrowstyle="->", lw=1.8, color="#2f3e5a")
    ax.annotate("", xy=(merge_x, merge_y), xytext=(0.24, 0.75), arrowprops=arrow_kwargs)
    ax.annotate("", xy=(merge_x, merge_y), xytext=(0.24, 0.50), arrowprops=arrow_kwargs)
    ax.annotate("", xy=(merge_x, merge_y), xytext=(0.24, 0.25), arrowprops=arrow_kwargs)

    # Formula box at merge
    ax.text(
        0.55,
        0.50,
        "Tc = 0.4 h_diff + 0.4 θ_slope + 0.2 r_rough",
        ha="center",
        va="center",
        fontsize=15,
        weight="bold",
        bbox=box_style,
    )

    # Output block
    ax.annotate("", xy=(0.80, 0.50), xytext=(0.68, 0.50), arrowprops=arrow_kwargs)
    ax.text(0.88, 0.50, "統合指標 Tc（提案）", ha="center", va="center", fontsize=15, weight="bold", bbox=out_style)

    fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.08)
    return save_fig(fig, "tc_definition_merge", dpi=220)


def make_path_comparison():
    """経路比較図（Regular A* vs TA*）"""
    fig, ax = plt.subplots(figsize=(12.8, 7.2))
    
    # Create terrain with hill in center
    n = 200
    x = np.linspace(-1.5, 1.5, n)
    y = np.linspace(-1.2, 1.2, n)
    X, Y = np.meshgrid(x, y)
    
    # Hill in center
    Z = (
        1.2 * np.exp(-((X) ** 2 + (Y) ** 2) / 0.25)
        + 0.4 * np.exp(-((X + 0.7) ** 2 + (Y - 0.4) ** 2) / 0.15)
        + 0.3 * np.exp(-((X - 0.6) ** 2 + (Y + 0.3) ** 2) / 0.12)
    )
    Z += 0.05 * np.random.RandomState(42).randn(n, n)
    
    # Terrain colormap
    terrain_cmap = LinearSegmentedColormap.from_list(
        "terrain", ["#88cc88", "#bbdd99", "#ddddaa", "#ccaa88", "#aa8866", "#886644"]
    )
    
    ax.imshow(Z, cmap=terrain_cmap, origin="lower", extent=[x.min(), x.max(), y.min(), y.max()], alpha=0.9)
    
    # Start and Goal
    start_pos = (-1.2, 0.0)
    goal_pos = (1.2, 0.0)
    
    # Regular A* path (straight through hill)
    regular_path_x = np.linspace(start_pos[0], goal_pos[0], 100)
    regular_path_y = np.zeros_like(regular_path_x)
    ax.plot(regular_path_x, regular_path_y, color='#d62728', linewidth=4, label='直進経路', zorder=3)
    
    # TA* path (detour around hill)
    t = np.linspace(0, 1, 150)
    ta_path_x = start_pos[0] + (goal_pos[0] - start_pos[0]) * t
    ta_path_y = 0.65 * np.sin(np.pi * t) * np.exp(-((t - 0.5) ** 2) / 0.2)
    ax.plot(ta_path_x, ta_path_y, color='#1f77b4', linewidth=4, label='迂回経路', zorder=3)
    
    # Start/Goal markers
    ax.scatter([start_pos[0]], [start_pos[1]], s=150, color='white', edgecolors='black', linewidths=2, zorder=4, marker='o')
    ax.scatter([goal_pos[0]], [goal_pos[1]], s=150, color='white', edgecolors='black', linewidths=2, zorder=4, marker='s')
    
    ax.text(start_pos[0], start_pos[1] - 0.18, 'Start', ha='center', va='top', fontsize=13, weight='bold', 
            bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='black', lw=1))
    ax.text(goal_pos[0], goal_pos[1] - 0.18, 'Goal', ha='center', va='top', fontsize=13, weight='bold',
            bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='black', lw=1))
    
    # Hill annotation
    ax.text(0.0, 0.2, '丘（高標高領域）', ha='center', va='center', fontsize=12, 
            bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='#886644', lw=1.5, alpha=0.9))
    
    ax.set_xlim(x.min(), x.max())
    ax.set_ylim(y.min(), y.max())
    ax.set_xticks([])
    ax.set_yticks([])
    ax.legend(loc='upper right', fontsize=13, frameon=True, fancybox=True, shadow=True)
    
    fig.tight_layout()
    return save_fig(fig, "path_comparison", dpi=220)


def _generate_perlin_like_terrain(size, complexity_seed):
    """Perlinノイズ風の地形を生成"""
    np.random.seed(complexity_seed)
    
    # Multiple frequency noise layers
    terrain = np.zeros((size, size))
    for octave in range(4):
        freq = 2 ** octave
        amplitude = 1.0 / (freq ** 0.8)
        noise = np.random.randn(size // freq + 2, size // freq + 2)
        
        # Simple bilinear interpolation upsampling
        from scipy.ndimage import zoom
        upsampled = zoom(noise, freq, order=1, mode='wrap')[:size, :size]
        terrain += amplitude * upsampled
    
    return terrain


def make_dataset3_terrain_examples():
    """Dataset3の地形例（複雑度別）- 3D表示"""
    import json
    from mpl_toolkits.mplot3d import Axes3D
    from scipy.ndimage import gaussian_filter
    
    # Load dataset3 scenarios (it's a list)
    with open('dataset3_scenarios.json', 'r') as f:
        dataset3_list = json.load(f)
    
    # Use specific scenario IDs selected for clear visual differences
    selected_ids = {
        '単純': 'dataset3_1_2_9',   # Height range: 5.05, Roughness: 1.07
        '中程度': 'dataset3_2_3_6',   # Height range: 13.06, Roughness: 1.33
        '複雑': 'dataset3_3_3_6'   # Height range: 39.93, Roughness: 2.44
    }
    
    # Find scenarios by ID
    examples = {
        '単純': None,
        '中程度': None,
        '複雑': None
    }
    
    for scenario_data in dataset3_list:
        scenario_id = scenario_data.get('id', '')
        
        if scenario_id == selected_ids['単純']:
            examples['単純'] = scenario_data
        elif scenario_id == selected_ids['中程度']:
            examples['中程度'] = scenario_data
        elif scenario_id == selected_ids['複雑']:
            examples['複雑'] = scenario_data
        
        if all(v is not None for v in examples.values()):
            break
    
    fig = plt.figure(figsize=(15, 5))
    
    # Use viridis-like colormap for better visibility
    terrain_cmap = 'viridis'
    
    labels = ["単純", "中程度", "複雑"]
    # Update info to show actual height ranges
    complexity_info = [
        "標高差: 5.1m",   # 単純
        "標高差: 13.1m",  # 中程度
        "標高差: 39.9m"   # 複雑
    ]
    
    # First pass: collect all terrain data and compute global min/max
    terrain_data = []
    for i, label in enumerate(labels):
        if examples[label] is not None and 'height_map' in examples[label]:
            terrain = np.array(examples[label]['height_map'])
        else:
            terrain = _generate_perlin_like_terrain(100, i * 100) * (0.5 + i * 0.8)
        
        terrain_smooth = gaussian_filter(terrain, sigma=1.5)
        terrain_data.append((terrain_smooth, examples[label]))
    
    # Compute global z-axis range for unified scale
    all_terrain = np.concatenate([t[0].flatten() for t in terrain_data])
    global_zmin = all_terrain.min()
    global_zmax = all_terrain.max()
    
    # Second pass: plot with unified z-scale
    for i, (label, info) in enumerate(zip(labels, complexity_info)):
        ax = fig.add_subplot(1, 3, i + 1, projection='3d')
        
        terrain_smooth, scenario = terrain_data[i]
        
        # Get grid resolution
        grid_res = scenario.get('grid_resolution', 0.2) if scenario is not None else 0.2
        
        # Create coordinate arrays in meters - less aggressive subsampling
        height, width = terrain_smooth.shape
        step = max(1, height // 100)  # Increase resolution
        terrain_sub = terrain_smooth[::step, ::step]
        
        h_sub, w_sub = terrain_sub.shape
        x = np.arange(w_sub) * grid_res * step
        y = np.arange(h_sub) * grid_res * step
        X, Y = np.meshgrid(x, y)
        
        # 3D surface plot with Gouraud shading and UNIFIED z-scale
        surf = ax.plot_surface(X, Y, terrain_sub, cmap=terrain_cmap, 
                               linewidth=0, antialiased=True, alpha=0.95,
                               shade=True, rcount=100, ccount=100,
                               vmin=global_zmin, vmax=global_zmax)
        
        ax.set_xlabel('X [m]', fontsize=10)
        ax.set_ylabel('Y [m]', fontsize=10)
        ax.set_zlabel('標高 [m]', fontsize=10)
        ax.set_zlim(global_zmin, global_zmax)  # Unified z-axis range
        ax.set_title(f"{label}\n{info}", fontsize=12, weight='bold', pad=10)
        ax.view_init(elev=25, azim=45)
        ax.tick_params(labelsize=8)
        
        # Add colorbar
        cbar = fig.colorbar(surf, ax=ax, fraction=0.03, pad=0.08, shrink=0.8)
        cbar.ax.tick_params(labelsize=8)
    
    fig.suptitle("Dataset3の地形例（複雑度別）- 3D表示", fontsize=16, weight='bold', y=0.98)
    fig.text(0.5, 0.01, "3Dサーフェス表示 - 実データより", ha='center', fontsize=11, style='italic', color='#555555')
    
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    return save_fig(fig, "dataset3_terrain_examples", dpi=220)

# ② Method comparison diagram

def make_method_compare():
    fig = plt.figure(figsize=(12, 6))
    gs = fig.add_gridspec(2, 2, height_ratios=[4, 1.6])

    # Left: TA*
    ax_left = fig.add_subplot(gs[0, 0])
    ax_left.set_title("TA*")
    ax_left.set_xlim(0, 10)
    ax_left.set_ylim(0, 6)
    ax_left.set_aspect("equal")
    ax_left.set_xticks([])
    ax_left.set_yticks([])

    # Grid
    for x in np.arange(0, 10.1, 1):
        ax_left.plot([x, x], [0, 6], color="#e6e6e6", linewidth=0.6)
    for y in np.arange(0, 6.1, 1):
        ax_left.plot([0, 10], [y, y], color="#e6e6e6", linewidth=0.6)

    # Jagged path
    path_x = [0.5, 2, 2, 4, 4, 6.5, 6.5, 9.2]
    path_y = [0.8, 0.8, 2.2, 2.2, 3.8, 3.8, 5.2, 5.2]
    ax_left.plot(path_x, path_y, color="#4e5f7c", linewidth=3)

    # Feature text
    ax_left.text(0.2, 5.6, "・グリッド探索", fontsize=10, color="#333333")
    ax_left.text(0.2, 5.2, "・地形コスト Tc を考慮", fontsize=10, color="#333333")
    ax_left.text(0.2, 4.8, "・経路が折れやすい", fontsize=10, color="#333333")
    ax_left.text(0.2, 4.4, "・計算時間が長い", fontsize=10, color="#333333")

    # Right: Field D* Hybrid
    ax_right = fig.add_subplot(gs[0, 1])
    ax_right.set_title("Field D* Hybrid")
    ax_right.set_xlim(0, 10)
    ax_right.set_ylim(0, 6)
    ax_right.set_aspect("equal")
    ax_right.set_xticks([])
    ax_right.set_yticks([])

    # Grid
    for x in np.arange(0, 10.1, 1):
        ax_right.plot([x, x], [0, 6], color="#e6e6e6", linewidth=0.6)
    for y in np.arange(0, 6.1, 1):
        ax_right.plot([0, 10], [y, y], color="#e6e6e6", linewidth=0.6)

    # Smooth path
    t = np.linspace(0, 1, 200)
    curve_x = 0.6 + 8.6 * t
    curve_y = 0.8 + 4.2 * (1 - np.cos(np.pi * t)) / 2
    ax_right.plot(curve_x, curve_y, color="#6b7fa8", linewidth=3)

    ax_right.text(0.2, 5.6, "・補間点を生成", fontsize=10, color="#333333")
    ax_right.text(0.2, 5.2, "・滑らかな経路", fontsize=10, color="#333333")
    ax_right.text(0.2, 4.8, "・地形コスト Tc を補間して計算", fontsize=10, color="#333333")
    ax_right.text(0.2, 4.4, "・高速", fontsize=10, color="#333333")

    # Bottom small table
    ax_table = fig.add_subplot(gs[1, :])
    ax_table.axis("off")
    cell_text = [
        ["手法特徴", "TA*", "Field D* Hybrid"],
        ["詳細な地形回避", "○", "○"],
        ["高速＋滑らか", "△", "◎"],
    ]

    table = ax_table.table(
        cellText=cell_text,
        cellLoc="center",
        loc="center",
        colWidths=[0.25, 0.35, 0.35],
    )
    table.scale(1, 1.4)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#cfcfcf")
        cell.set_linewidth(0.8)
        if row == 0:
            cell.set_facecolor("#f2f4f7")
            cell.set_text_props(weight="bold")

    fig.tight_layout()
    return save_fig(fig, "method_compare")

# ③ Result summary table

def make_result_table():
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.axis("off")

    columns = ["手法", "経路長 [m]", "地形コスト", "計算時間 [s]", "成功率 [%]"]
    data = [
        ["Regular A*", "20.85", "2.84", "", "100.0"],
        ["TA*", "21.27 (＋2.0%)", "2.38 (−16.2%)", "15.46", "96.88"],
        ["Field D* Hybrid", "23.60 (＋13.2%)", "2.52 (−11.3%)", "0.175", "100.0"],
    ]

    table = ax.table(
        cellText=data,
        colLabels=columns,
        cellLoc="center",
        colLoc="center",
        loc="center",
        colWidths=[0.22, 0.2, 0.16, 0.18, 0.14],
    )

    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 2.0)

    # Header
    for col in range(len(columns)):
        cell = table[0, col]
        cell.set_facecolor("#f2f4f7")
        cell.set_edgecolor("#cfcfcf")
        cell.set_text_props(weight="bold")

    # Highlight proposed methods rows
    highlight_color = "#eef3f8"
    for row in [2, 3]:
        for col in range(len(columns)):
            table[row, col].set_facecolor(highlight_color)

    # Borders
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#cfcfcf")
        cell.set_linewidth(0.8)

    fig.tight_layout()
    return save_fig(fig, "result_table")

# ④ Hill detour paths

def make_hill_detour_paths():
    fig, ax = plt.subplots(figsize=(12, 6))

    n = 200
    x = np.linspace(-1.2, 1.2, n)
    y = np.linspace(-1.0, 1.0, n)
    X, Y = np.meshgrid(x, y)

    # Gaussian hill
    Z = np.exp(-((X) ** 2 + (Y) ** 2) / 0.18)
    Z += 0.15 * np.exp(-((X + 0.6) ** 2 + (Y - 0.3) ** 2) / 0.1)

    cmap = LinearSegmentedColormap.from_list(
        "hill", ["#f7f7f7", "#d9e2f3", "#9ab0d6", "#6b7fa8", "#4e5f7c"]
    )

    ax.imshow(Z, cmap=cmap, origin="lower", extent=[x.min(), x.max(), y.min(), y.max()])

    # Paths
    # Regular A*: straight line through hill
    ax.plot([-1.0, 1.0], [0.0, 0.0], color="#d24d57", linewidth=3, label="Regular A*")

    # TA*: detour around hill
    t = np.linspace(0, 1, 200)
    path_x = -1.0 + 2.0 * t
    path_y = 0.55 * np.sin(np.pi * t) * np.exp(-((t - 0.5) ** 2) / 0.15)
    ax.plot(path_x, path_y, color="#2c7fb8", linewidth=3, label="TA*")

    # Start/Goal
    ax.scatter([-1.0, 1.0], [0.0, 0.0], color="#333333", s=40, zorder=5)
    ax.text(-1.05, -0.12, "Start", fontsize=11, color="#333333")
    ax.text(0.92, -0.12, "Goal", fontsize=11, color="#333333")

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title("hill detour 経路比較")
    ax.legend(loc="upper right", frameon=True)

    fig.tight_layout()
    return save_fig(fig, "hill_detour_paths")

# ⑤ Time comparison log bar chart

def make_time_compare_log():
    fig, ax = plt.subplots(figsize=(12, 6))

    methods = ["TA*", "Field D* Hybrid", "Theta*", "AHA*"]
    times = [15.46, 0.175, 0.234, 0.016]

    bars = ax.bar(methods, times, color=["#6b7fa8", "#8fa6c8", "#9fb7d5", "#b8cbe4"], edgecolor="#4e5f7c")
    ax.set_yscale("log")
    ax.set_ylabel("計算時間 [s]（対数スケール）")
    ax.set_title("計算時間の比較（対数スケール）")

    for bar, val in zip(bars, times):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val * 1.2,
            f"{val}",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#333333",
        )

    ax.grid(axis="y", which="both", linestyle="--", linewidth=0.5, color="#d0d0d0")

    fig.tight_layout()
    return save_fig(fig, "time_compare_log")


def make_field_d_interpolation():
    """Field D* Hybrid の補間効果を示す概念図"""
    fig = plt.figure(figsize=(12, 6))
    gs = fig.add_gridspec(1, 2, wspace=0.3)
    ax_left = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])
    
    # Common settings
    grid_size = 10
    x_range = np.arange(0, grid_size + 1)
    y_range = np.arange(0, grid_size + 1)
    
    # Start and Goal positions
    start = np.array([1, 8])
    goal = np.array([9, 2])
    
    # ===== LEFT: Grid-based path (zigzag) - THINNER LINE =====
    # Draw grid
    for x in x_range:
        ax_left.axvline(x, color='#cccccc', linewidth=0.8, alpha=0.6)
    for y in y_range:
        ax_left.axhline(y, color='#cccccc', linewidth=0.8, alpha=0.6)
    
    # Create zigzag path (grid-based)
    zigzag_x = [start[0], 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, goal[0]]
    zigzag_y = [start[1], 8, 7, 7, 6, 6, 5, 5, 4, 4, 3, 3, 2, 2, 2, 2, goal[1]]
    
    ax_left.plot(zigzag_x, zigzag_y, color='#1f77b4', linewidth=4, zorder=3)
    
    # Start and Goal markers
    ax_left.scatter([start[0]], [start[1]], s=200, color='#1f77b4', edgecolors='black', 
                    linewidths=2, zorder=4, marker='o')
    ax_left.scatter([goal[0]], [goal[1]], s=200, color='#d62728', edgecolors='black', 
                    linewidths=2, zorder=4, marker='s')
    
    ax_left.set_xlim(-0.5, grid_size + 0.5)
    ax_left.set_ylim(-0.5, grid_size + 0.5)
    ax_left.set_aspect('equal')
    ax_left.set_xticks([])
    ax_left.set_yticks([])
    ax_left.invert_yaxis()
    
    # ===== RIGHT: Interpolated smooth path (more linear blend) =====
    # Draw grid
    for x in x_range:
        ax_right.axvline(x, color='#cccccc', linewidth=0.8, alpha=0.6)
    for y in y_range:
        ax_right.axhline(y, color='#cccccc', linewidth=0.8, alpha=0.6)
    
    # Smooth interpolation: connect corners with diagonal segments (no waves, no arcs)
    pts = np.column_stack([zigzag_x, zigzag_y]).astype(float)
    diag = [pts[0]]
    i = 1
    while i < len(pts) - 1:
        prev_pt = pts[i - 1]
        curr_pt = pts[i]
        next_pt = pts[i + 1]
        v1 = curr_pt - prev_pt
        v2 = next_pt - curr_pt
        # If corner (perpendicular), skip the corner and connect diagonally
        if abs(np.dot(v1, v2)) < 1e-6:
            diag.append(next_pt)
            i += 2
        else:
            diag.append(curr_pt)
            i += 1
    if not np.allclose(diag[-1], pts[-1]):
        diag.append(pts[-1])
    diag = np.array(diag)
    smooth_x = diag[:, 0]
    smooth_y = diag[:, 1]
    
    ax_right.plot(smooth_x, smooth_y, color='#2ca02c', linewidth=4, zorder=3)
    
    # Start and Goal markers
    ax_right.scatter([start[0]], [start[1]], s=200, color='#1f77b4', edgecolors='black', 
                     linewidths=2, zorder=4, marker='o')
    ax_right.scatter([goal[0]], [goal[1]], s=200, color='#d62728', edgecolors='black', 
                     linewidths=2, zorder=4, marker='s')
    
    ax_right.set_xlim(-0.5, grid_size + 0.5)
    ax_right.set_ylim(-0.5, grid_size + 0.5)
    ax_right.set_aspect('equal')
    ax_right.set_xticks([])
    ax_right.set_yticks([])
    ax_right.invert_yaxis()
    
    # Center label only
    fig.text(0.5, 0.52, '補間', ha='center', va='center', fontsize=11,
             color='#666666', transform=fig.transFigure)
    
    fig.tight_layout()
    return save_fig(fig, "field_d_interpolation", dpi=220)



def make_dataset3_composition():
    """Dataset3の96シナリオ構成（マップサイズ×複雑度の3×3表）"""
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    # 3×3の構成データ（96シナリオ）
    sizes = ['Small\n(20×20m)', 'Medium\n(50×50m)', 'Large\n(100×100m)']
    complexities = ['単純\n(<0.15)', '中程度\n(0.15-0.55)', '複雑\n(≥0.55)']
    
    # 96シナリオの予定配分（3×3均等配分）
    data = [
        [11, 11, 10],  # Small
        [11, 11, 10],  # Medium
        [10, 11, 11],  # Large
    ]
    
    # テーブル作成
    cell_height = 0.12
    cell_width = 0.25
    start_x = 0.15
    start_y = 0.75
    
    # ヘッダー行（複雑度）
    ax.text(start_x - 0.05, start_y + cell_height, 'マップサイズ', 
            ha='center', va='center', fontsize=12, weight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#e0e0e0', edgecolor='black', linewidth=1.5))
    
    for j, complexity in enumerate(complexities):
        x = start_x + j * cell_width
        y = start_y + cell_height
        ax.text(x, y, complexity, ha='center', va='center', fontsize=11, weight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#d0d0ff', edgecolor='black', linewidth=1.5))
    
    # ヘッダー列（サイズ）
    for i, size in enumerate(sizes):
        x = start_x - 0.08
        y = start_y - i * cell_height
        ax.text(x, y, size, ha='center', va='center', fontsize=11, weight='bold',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffd0d0', edgecolor='black', linewidth=1.5))
    
    # データセル
    for i in range(3):
        for j in range(3):
            x = start_x + j * cell_width
            y = start_y - i * cell_height
            value = data[i][j]
            
            # 背景色の選択
            if i == 2 and j == 2:  # 右下（複雑×Large）
                bgcolor = '#ffe6e6'
            elif i == 0 and j == 0:  # 左上（単純×Small）
                bgcolor = '#e6ffe6'
            else:
                bgcolor = '#ffffcc'
            
            ax.text(x, y, str(value), ha='center', va='center', fontsize=13, weight='bold',
                    bbox=dict(boxstyle='round,pad=0.8', facecolor=bgcolor, edgecolor='black', linewidth=1))
    
    # 行合計
    for i in range(3):
        row_total = sum(data[i])
        x = start_x + 3 * cell_width
        y = start_y - i * cell_height
        ax.text(x, y, f'{row_total}', ha='center', va='center', fontsize=12, weight='bold',
                bbox=dict(boxstyle='round,pad=0.7', facecolor='#e0e0e0', edgecolor='black', linewidth=1))
    
    # 列合計
    for j in range(3):
        col_total = sum(data[i][j] for i in range(3))
        x = start_x + j * cell_width
        y = start_y - 3 * cell_height
        ax.text(x, y, f'{col_total}', ha='center', va='center', fontsize=12, weight='bold',
                bbox=dict(boxstyle='round,pad=0.7', facecolor='#e0e0e0', edgecolor='black', linewidth=1))
    
    # 全体合計
    grand_total = sum(sum(row) for row in data)
    x = start_x + 3 * cell_width
    y = start_y - 3 * cell_height
    ax.text(x, y, f'{grand_total}', ha='center', va='center', fontsize=12, weight='bold',
            bbox=dict(boxstyle='round,pad=0.7', facecolor='#ffcc99', edgecolor='black', linewidth=2))
    
    # 列ラベル（合計）
    ax.text(start_x + 3 * cell_width, start_y + cell_height, '合計', ha='center', va='center', 
            fontsize=11, weight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#e0e0e0', edgecolor='black', linewidth=1.5))
    
    # 行ラベル（合計）
    ax.text(start_x - 0.08, start_y - 3 * cell_height, '合計', ha='center', va='center',
            fontsize=11, weight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#e0e0e0', edgecolor='black', linewidth=1.5))
    
    # タイトル
    ax.text(0.5, 0.95, 'Dataset3 シナリオ構成（96シナリオ）', ha='center', va='top', 
            fontsize=14, weight='bold', transform=ax.transAxes)
    
    # 説明
    ax.text(0.5, 0.08, 'マップサイズ（Small/Medium/Large）と地形複雑度（単純/中程度/複雑）の組み合わせ',
            ha='center', va='top', fontsize=10, style='italic', transform=ax.transAxes)
    
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    fig.tight_layout()
    return save_fig(fig, "dataset3_composition", dpi=220)


def main():
    make_tc_heatmaps()
    make_tc_heatmaps_fixed()
    make_tc_heatmaps_final()
    make_tc_heatmaps_presentation()
    make_tc_definition_flow()
    make_tc_definition_merge()
    make_path_comparison()
    make_dataset3_terrain_examples()
    make_method_compare()
    make_result_table()
    make_hill_detour_paths()
    make_time_compare_log()
    make_field_d_interpolation()
    make_dataset3_composition()
    print(f"All figures generated in ./{OUT_DIR}")


if __name__ == "__main__":
    main()
