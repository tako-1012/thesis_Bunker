std_msgs/Header header
float32 resolution           # Voxel size in meters
geometry_msgs/Point origin   # Grid origin point
int32 size_x                 # Number of voxels in X direction
int32 size_y                 # Number of voxels in Y direction
int32 size_z                 # Number of voxels in Z direction
uint8[] data                 # Voxel data (0: empty, 1: ground, 2: obstacle, 255: unknown)
float32[] slopes             # Slope angles for ground voxels in degrees
