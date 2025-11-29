import json
import numpy as np
import matplotlib.pyplot as plt

# ファイルパス
json_path = "./unity_data/demo_large_moderate.json"

# JSON読み込み
with open(json_path, "r") as f:
    data = json.load(f)

terrain = data["terrain"]
cost_map = np.array(terrain["costMap"])

# ヒストグラム可視化
plt.figure(figsize=(8,6))
plt.hist(cost_map.flatten(), bins=100, color='royalblue', alpha=0.7)
plt.xlabel('Height / Cost Value')
plt.ylabel('Frequency')
plt.title('Distribution of Terrain Height/Cost (demo_large_moderate)')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('terrain_cost_histogram.png', dpi=300)
plt.close()
print('地形コスト値のヒストグラム画像を保存しました: terrain_cost_histogram.png')
