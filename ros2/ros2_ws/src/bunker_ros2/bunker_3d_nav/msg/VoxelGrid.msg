# ボクセルグリッドメッセージ
std_msgs/Header header
float32 voxel_size
geometry_msgs/Point32[] centers
geometry_msgs/Vector3[] normals
int32[] point_counts
int32[] classifications  # 0:unknown, 1:ground, 2:obstacle
