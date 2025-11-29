import json
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# 元データのパス
json_path = "./unity_data/demo_large_moderate.json"

# JSON読み込み
with open(json_path, "r") as f:
    data = json.load(f)

terrain = data["terrain"]
grid_size = terrain["gridSize"]
resolution = terrain["resolution"]
cost_map = np.array(terrain["costMap"])

# --- 複雑な地形を人工的に生成 ---
# 1. ランダム障害物（高コスト領域）
np.random.seed(42)
for _ in range(10):
    cx, cy = np.random.randint(100, 900, size=2)
    r = np.random.randint(20, 50)
    cost_map[max(0,cx-r):min(grid_size[0],cx+r), max(0,cy-r):min(grid_size[1],cy+r)] += 1.0

# 2. 壁状障害物
cost_map[400:600, 200:220] += 2.0
cost_map[700:720, 600:900] += 1.5

# 3. 谷（低コスト領域）
cost_map[100:300, 700:900] -= 0.08
cost_map = np.clip(cost_map, 0.05, 3.0)

# 4. 起伏（sin波）
x = np.arange(grid_size[0])
y = np.arange(grid_size[1])
xx, yy = np.meshgrid(x, y)
cost_map += 0.15 * np.sin(xx/60) * np.cos(yy/80)
cost_map = np.clip(cost_map, 0.05, 3.0)

# --- 可視化 ---
xm = np.arange(grid_size[0]) * resolution
ym = np.arange(grid_size[1]) * resolution
xxm, yym = np.meshgrid(xm, ym)
zzm = cost_map

start = terrain["start"]
goal = terrain["goal"]
path = np.array(data["paths"]["ADAPTIVE"]["path"])

fig = plt.figure(figsize=(14, 12))
ax = fig.add_subplot(111, projection="3d")

skip = 10
surf = ax.plot_surface(xxm[::skip,::skip], yym[::skip,::skip], zzm[::skip,::skip], cmap="jet", alpha=0.5, linewidth=0, antialiased=False)
fig.colorbar(surf, ax=ax, shrink=0.5, aspect=10, label="Height / Cost")

ax.scatter(start[0], start[1], start[2], c="green", s=300, marker="o", label="Start")
ax.scatter(goal[0], goal[1], goal[2], c="red", s=300, marker="o", label="Goal")
ax.plot(path[:,0], path[:,1], path[:,2], c="blue", linewidth=5, label="Planned Path")

ax.set_xlabel("X [m]", fontsize=14)
ax.set_ylabel("Y [m]", fontsize=14)
ax.set_zlabel("Z [m]", fontsize=14)
ax.set_title("Terrain-Aware Path Planning on Artificial Complex Terrain", fontsize=18)
ax.view_init(elev=60, azim=120)
ax.legend(loc="upper right", fontsize=13)
plt.tight_layout()
plt.savefig("path_with_artificial_terrain.png", dpi=300)
plt.close()
print("画像を保存しました: path_with_artificial_terrain.png")
