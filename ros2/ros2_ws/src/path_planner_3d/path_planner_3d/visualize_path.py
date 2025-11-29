import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# JSONファイルのパス（カレントディレクトリ基準）
json_path = "./unity_data/demo_small_moderate.json"

# JSONデータの読み込み
with open(json_path, "r") as f:
    data = json.load(f)

# 地形情報
terrain = data["terrain"]
grid_size = terrain["gridSize"]
resolution = terrain["resolution"]
cost_map = np.array(terrain["costMap"])

# 地形点群生成（コスト値が閾値以上の点のみプロット）
x = np.arange(grid_size[0]) * resolution
y = np.arange(grid_size[1]) * resolution
xx, yy = np.meshgrid(x, y)
zz = np.zeros_like(xx)

# cost_mapの形状に合わせて点群を生成
cost_threshold = 0.2  # 低コスト地形のみ表示
mask = cost_map > cost_threshold
terrain_x = xx[mask]
terrain_y = yy[mask]
terrain_z = zz[mask]

# スタート・ゴール
start = terrain["start"]
goal = terrain["goal"]

# 経路（ADAPTIVE）
path = np.array(data["paths"]["ADAPTIVE"]["path"])

# 3Dプロット
fig = plt.figure(figsize=(8, 8))
ax = fig.add_subplot(111, projection="3d")

# 地形点群（グレー）
ax.scatter(terrain_x, terrain_y, terrain_z, c="gray", s=2, alpha=0.5, label="Terrain")

# スタート地点（緑の丸）
ax.scatter(start[0], start[1], start[2], c="green", s=80, marker="o", label="Start")

# ゴール地点（赤の丸）
ax.scatter(goal[0], goal[1], goal[2], c="red", s=80, marker="o", label="Goal")

# 経路（青い線）
ax.plot(path[:,0], path[:,1], path[:,2], c="blue", linewidth=2, label="Path")

# 軸ラベル
ax.set_xlabel("X [m]")
ax.set_ylabel("Y [m]")
ax.set_zlabel("Z [m]")

# 見やすい角度
ax.view_init(elev=45, azim=135)

# 凡例
ax.legend()

# タイトル
ax.set_title("Path Planning Visualization (demo_small_moderate)")

# 解像度300dpiで保存
plt.tight_layout()
plt.savefig("path_visualization.png", dpi=300)
plt.close()

