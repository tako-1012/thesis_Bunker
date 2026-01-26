import numpy as np
import json
import os

class ComplexityEvaluator:
    """地形複雑度評価の基底クラス"""

    def normalize(self, value, max_value):
        """0-1に正規化"""
        if max_value == 0:
            return 0.0
        return min(value / max_value, 1.0)


class Method1_Slope(ComplexityEvaluator):
    """勾配重視型"""

    def calculate(self, scenario):
        slopes = self._calculate_slopes(scenario.get('height_map', []))

        slope_mean = float(np.mean(slopes)) if slopes.size > 0 else 0.0
        slope_var = float(np.var(slopes)) if slopes.size > 0 else 0.0
        heights = np.array(scenario.get('height_map', [])).flatten()
        height_range = float(np.max(heights) - np.min(heights)) if heights.size > 0 else 0.0

        complexity = (
            0.6 * self.normalize(slope_mean, 30.0) +
            0.3 * self.normalize(slope_var, 100.0) +
            0.1 * self.normalize(height_range, 10.0)
        )

        return {
            'complexity': float(complexity),
            'method': 'Method1_Slope',
            'slope_mean': slope_mean,
            'slope_var': slope_var,
            'height_range': height_range
        }

    def _calculate_slopes(self, height_map):
        height_array = np.array(height_map)
        if height_array.size == 0:
            return np.array([])
        grad_x = np.gradient(height_array, axis=1)
        grad_y = np.gradient(height_array, axis=0)
        slopes = np.sqrt(grad_x ** 2 + grad_y ** 2)
        return np.degrees(np.arctan(slopes)).flatten()


class Method2_Obstacle(ComplexityEvaluator):
    """障害物重視型"""

    def calculate(self, scenario):
        obstacle_density = float(scenario.get('obstacle_ratio', 0))

        obstacle_map = np.array(scenario.get('obstacle_map', []))
        if obstacle_map.size > 0:
            obstacle_clustering = float(self._calculate_clustering(obstacle_map))
        else:
            obstacle_clustering = 0.0

        complexity = (
            0.6 * obstacle_density +
            0.4 * obstacle_clustering
        )

        return {
            'complexity': float(complexity),
            'method': 'Method2_Obstacle',
            'obstacle_density': obstacle_density,
            'obstacle_clustering': obstacle_clustering
        }

    def _calculate_clustering(self, obstacle_map):
        # scipy が無ければ numpy だけで簡易ローカル密度を計算
        try:
            from scipy import ndimage
            local_density = ndimage.uniform_filter(obstacle_map.astype(float), size=3)
            return float(np.std(local_density))
        except Exception:
            # simple sliding window mean
            arr = obstacle_map.astype(float)
            if arr.size == 0:
                return 0.0
            kernel = np.ones((3, 3)) / 9.0
            # pad
            pad = np.pad(arr, pad_width=1, mode='constant', constant_values=0)
            h, w = arr.shape
            local = np.zeros_like(arr)
            for i in range(h):
                for j in range(w):
                    local[i, j] = np.sum(pad[i:i+3, j:j+3] * kernel)
            return float(np.std(local))


class Method3_Balanced(ComplexityEvaluator):
    """総合型（バランス）"""

    def calculate(self, scenario):
        slopes = self._calculate_slopes(scenario.get('height_map', []))
        slope_mean = float(np.mean(slopes)) if slopes.size > 0 else 0.0
        slope_var = float(np.var(slopes)) if slopes.size > 0 else 0.0

        obstacle_density = float(scenario.get('obstacle_ratio', 0))

        heights = np.array(scenario.get('height_map', [])).flatten()
        height_std = float(np.std(heights)) if heights.size > 0 else 0.0

        complexity = (
            0.3 * self.normalize(slope_mean, 30.0) +
            0.2 * self.normalize(slope_var, 100.0) +
            0.3 * obstacle_density +
            0.2 * self.normalize(height_std, 3.0)
        )

        return {
            'complexity': float(complexity),
            'method': 'Method3_Balanced',
            'slope_mean': slope_mean,
            'slope_var': slope_var,
            'obstacle_density': obstacle_density,
            'height_std': height_std
        }

    def _calculate_slopes(self, height_map):
        height_array = np.array(height_map)
        if height_array.size == 0:
            return np.array([])
        grad_x = np.gradient(height_array, axis=1)
        grad_y = np.gradient(height_array, axis=0)
        slopes = np.sqrt(grad_x ** 2 + grad_y ** 2)
        return np.degrees(np.arctan(slopes)).flatten()


class Method4_Statistical(ComplexityEvaluator):
    """統計的分散型"""

    def calculate(self, scenario):
        slopes = self._calculate_slopes(scenario.get('height_map', []))
        heights = np.array(scenario.get('height_map', [])).flatten()

        slope_entropy = float(self._calculate_entropy(slopes)) if slopes.size > 0 else 0.0
        height_entropy = float(self._calculate_entropy(heights)) if heights.size > 0 else 0.0

        obstacle_density = float(scenario.get('obstacle_ratio', 0))

        surface_roughness = float(np.std(slopes)) if slopes.size > 0 else 0.0

        complexity = (
            0.25 * self.normalize(slope_entropy, 4.0) +
            0.25 * self.normalize(height_entropy, 4.0) +
            0.25 * obstacle_density +
            0.25 * self.normalize(surface_roughness, 10.0)
        )

        return {
            'complexity': float(complexity),
            'method': 'Method4_Statistical',
            'slope_entropy': slope_entropy,
            'height_entropy': height_entropy,
            'obstacle_density': obstacle_density,
            'surface_roughness': surface_roughness
        }

    def _calculate_slopes(self, height_map):
        height_array = np.array(height_map)
        if height_array.size == 0:
            return np.array([])
        grad_x = np.gradient(height_array, axis=1)
        grad_y = np.gradient(height_array, axis=0)
        slopes = np.sqrt(grad_x ** 2 + grad_y ** 2)
        return np.degrees(np.arctan(slopes)).flatten()

    def _calculate_entropy(self, data):
        if data.size == 0:
            return 0.0
        hist, _ = np.histogram(data, bins=20)
        s = np.sum(hist)
        if s == 0:
            return 0.0
        probs = hist / s
        probs = probs[probs > 0]
        entropy = -np.sum(probs * np.log2(probs))
        return float(entropy)


def evaluate_all_methods(scenario):
    methods = [
        Method1_Slope(),
        Method2_Obstacle(),
        Method3_Balanced(),
        Method4_Statistical()
    ]

    results = {}
    for method in methods:
        result = method.calculate(scenario)
        method_name = result['method']
        results[method_name] = result

    return results


if __name__ == "__main__":
    root = os.getcwd()
    scenarios_path = os.path.join(root, 'dataset2_scenarios.json')
    outdir = os.path.join(root, 'benchmark_results')
    os.makedirs(outdir, exist_ok=True)
    out_path = os.path.join(outdir, 'complexity_method_comparison.json')

    try:
        with open(scenarios_path, 'r') as f:
            scenarios = json.load(f)
    except Exception as e:
        print(f"Failed to load scenarios: {e}")
        scenarios = []

    all_results = []
    summary = {}

    for i, sc in enumerate(scenarios):
        res = evaluate_all_methods(sc)
        entry = {
            'scenario_id': sc.get('id', i),
            'methods': res
        }
        all_results.append(entry)

    # compute per-method averages
    method_names = ['Method1_Slope', 'Method2_Obstacle', 'Method3_Balanced', 'Method4_Statistical']
    averages = {}
    for m in method_names:
        vals = [e['methods'][m]['complexity'] for e in all_results if m in e['methods']]
        averages[m] = float(np.mean(vals)) if len(vals) > 0 else 0.0

    summary['averages'] = averages
    summary['count'] = len(all_results)

    with open(out_path, 'w') as f:
        json.dump({'summary': summary, 'results': all_results}, f, indent=2)

    print('Complexity evaluation complete')
    print('Summary:')
    for k, v in averages.items():
        print(f"  {k}: {v:.4f}")
    print(f"Saved: {out_path}")
