import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# ファイルパス
json_path = "./unity_data/demo_large_moderate.json"

# JSON読み込み
with open(json_path, "r") as f:
    data = json.load(f)

terrain = data["terrain"]
grid_size = terrain["gridSize"]
resolution = terrain["resolution"]
cost_map = np.array(terrain["costMap"])

# 高さ情報としてコスト値を利用（例: 0.1~2.0）
x = np.arange(grid_size[0]) * resolution
y = np.arange(grid_size[1]) * resolution
xx, yy = np.meshgrid(x, y)
zz = cost_map

# スタート・ゴール
start = terrain["start"]
goal = terrain["goal"]

# 経路
path = np.array(data["paths"]["ADAPTIVE"]["path"])

fig = plt.figure(figsize=(14, 12))
ax = fig.add_subplot(111, projection="3d")

# 地形メッシュ（高さをカラーマップで色分け、半透明、間引き描画）
skip = 10  # 描画負荷軽減のため間引き
surf = ax.plot_surface(xx[::skip,::skip], yy[::skip,::skip], zz[::skip,::skip], cmap="jet", alpha=0.5, linewidth=0, antialiased=False)
fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label="Height / Cost")

# スタート地点（大きい緑の球）
ax.scatter(start[0], start[1], start[2], c="green", s=300, marker="o", label="Start")

# ゴール地点（大きい赤の球）
ax.scatter(goal[0], goal[1], goal[2], c="red", s=300, marker="o", label="Goal")

# 経路（太い青い線）
ax.plot(path[:,0], path[:,1], path[:,2], c="blue", linewidth=5, label="Planned Path")

# 軸ラベル
ax.set_xlabel("X [m]", fontsize=14)
ax.set_ylabel("Y [m]", fontsize=14)
ax.set_zlabel("Z [m]", fontsize=14)

# タイトル
ax.set_title("Terrain-Aware Path Planning on Complex Terrain", fontsize=18)

# 見やすい角度
ax.view_init(elev=60, azim=120)

# 凡例
ax.legend(loc="upper right", fontsize=13)

# 解像度300dpiで保存
plt.tight_layout()
plt.savefig("path_with_terrain.png", dpi=300)
plt.close()
print("画像を保存しました: path_with_terrain.png")
