from path_planner_3d.adaptive_hybrid_astar_3d import AdaptiveHybridAStar3D

def main():
    # construct with defaults (avoid passing point_cloud if import resolves to variant)
    planner = AdaptiveHybridAStar3D()

    print("=== 現在のAHA*パラメータ ===\n")

    params = [
        'max_iterations',
        'initial_epsilon',
        'refinement_epsilon',
        'final_epsilon',
        'epsilon_decay',
        'goal_bias',
        'max_samples',
        'timeout',
        'heuristic_weight',
        'phase1_iterations',
        'phase2_iterations',
        'phase3_iterations'
    ]

    for param in params:
        value = getattr(planner, param, 'N/A')
        print(f"{param}: {value}")

if __name__ == '__main__':
    main()
