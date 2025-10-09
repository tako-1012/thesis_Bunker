# TerrainInfo.msg
# 地形情報メッセージ

std_msgs/Header header

# 統計情報
float32 avg_slope          # 平均傾斜角度 [度]
float32 max_slope          # 最大傾斜角度 [度]
float32 min_slope          # 最小傾斜角度 [度]
float32 traversable_ratio  # 走行可能割合 [0-1]

# ボクセル情報
int32 total_voxels         # 総ボクセル数
int32 ground_voxels        # 地面ボクセル数
int32 obstacle_voxels      # 障害物ボクセル数

# リスク情報
float32 avg_risk           # 平均リスクスコア [0-1]
float32 max_risk           # 最大リスクスコア [0-1]

# コスト情報
float32 avg_cost           # 平均走行コスト
float32 impassable_ratio   # 走行不可割合 [0-1]

# 処理情報
float32 processing_time    # 処理時間 [秒]
int32 point_count          # 処理点数