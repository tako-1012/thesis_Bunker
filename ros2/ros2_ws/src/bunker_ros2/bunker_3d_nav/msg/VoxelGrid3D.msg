# VoxelGrid3D.msg
# 3Dボクセルグリッドメッセージ

std_msgs/Header header

# ボクセルグリッド情報
float32 voxel_size         # ボクセルサイズ [m]
int32 num_voxels          # ボクセル数

# 境界情報
geometry_msgs/Point min_bound  # 最小境界点
geometry_msgs/Point max_bound  # 最大境界点
geometry_msgs/Vector3 size     # サイズ

# ボクセルデータ
int32[] voxel_indices     # ボクセルインデックス (x, y, z)
int32[] voxel_types       # ボクセルタイプ (0:空, 1:地面, 2:障害物)
float32[] voxel_slopes    # ボクセル傾斜角度 [度]
float32[] voxel_risks     # ボクセルリスクスコア [0-1]
float32[] voxel_costs     # ボクセル走行コスト