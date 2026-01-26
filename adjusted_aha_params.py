# adjusted_aha_params.py

# 調整案1: 探索を抑制
ADJUSTED_PARAMS_V1 = {
    'max_iterations': 10000,
    'initial_epsilon': 2.0,
    'timeout': 30,
}

# 調整案2: より慎重な探索
ADJUSTED_PARAMS_V2 = {
    'max_iterations': 20000,
    'initial_epsilon': 1.5,
    'refinement_epsilon': 1.2,
    'timeout': 60,
}

# 調整案3: 極端に簡素化
ADJUSTED_PARAMS_V3 = {
    'max_iterations': 5000,
    'initial_epsilon': 3.0,
    'timeout': 15,
}
