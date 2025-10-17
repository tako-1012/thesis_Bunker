# Path3D.msg
# Unity統合用の3D経路メッセージ

std_msgs/Header header

# 経路点のリスト
geometry_msgs/Point[] points

# 各点での勾配情報（度）
float32[] slopes

# 各点でのコスト値
float32[] costs

# 経路の総コスト
float32 total_cost

# 経路の総長
float32 total_length

# 計算時間（秒）
float32 computation_time

# 成功フラグ
bool success

# エラーメッセージ（失敗時）
string error_message
