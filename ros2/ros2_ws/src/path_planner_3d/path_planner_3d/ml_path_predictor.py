"""
機械学習による経路予測

学習した経路パターンから高速に予測
"""
import numpy as np
from typing import List, Tuple, Dict
import pickle
from pathlib import Path

class MLPathPredictor:
    """機械学習経路予測クラス"""
    
    def __init__(self):
        """初期化"""
        self.trained = False
        self.model = None
        self.scaler = None
    
    def extract_features(self, start: Tuple, goal: Tuple, 
                        terrain_type: str = None) -> np.ndarray:
        """
        特徴量抽出
        
        Args:
            start: スタート位置
            goal: ゴール位置
            terrain_type: 地形タイプ
        
        Returns:
            特徴量ベクトル
        """
        features = []
        
        # 1. 距離
        distance = np.linalg.norm(np.array(goal) - np.array(start))
        features.append(distance)
        
        # 2. 方向（極座標）
        dx = goal[0] - start[0]
        dy = goal[1] - start[1]
        angle = np.arctan2(dy, dx)
        features.extend([np.cos(angle), np.sin(angle)])
        
        # 3. 高低差
        dz = goal[2] - start[2]
        features.append(dz)
        features.append(abs(dz))
        
        # 4. 地形エンコーディング（one-hot）
        terrain_types = ['flat', 'gentle', 'steep', 'complex', 'extreme']
        if terrain_type:
            terrain_idx = terrain_types.index(terrain_type) if terrain_type in terrain_types else 0
            terrain_onehot = [1 if i == terrain_idx else 0 for i in range(len(terrain_types))]
        else:
            terrain_onehot = [0] * len(terrain_types)
        features.extend(terrain_onehot)
        
        return np.array(features)
    
    def train(self, training_data: List[Dict]):
        """
        経路データから学習
        
        Args:
            training_data: 学習データ
                [{'start': [...], 'goal': [...], 'path': [...], 
                  'terrain': '...', 'success': True/False}, ...]
        """
        try:
            from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            print("scikit-learnが必要です: pip install scikit-learn")
            return
        
        # 特徴量とラベルの準備
        X_success = []  # 成功予測用
        y_success = []
        
        X_time = []  # 計算時間予測用
        y_time = []
        
        for data in training_data:
            features = self.extract_features(
                data['start'],
                data['goal'],
                data.get('terrain')
            )
            
            X_success.append(features)
            y_success.append(1 if data.get('success', False) else 0)
            
            if data.get('success', False):
                X_time.append(features)
                y_time.append(data.get('computation_time', 0))
        
        # 正規化
        self.scaler = StandardScaler()
        X_success_scaled = self.scaler.fit_transform(X_success)
        
        # 成功予測モデル
        self.success_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.success_model.fit(X_success_scaled, y_success)
        
        # 計算時間予測モデル
        if X_time:
            X_time_scaled = self.scaler.transform(X_time)
            self.time_model = RandomForestRegressor(n_estimators=100, random_state=42)
            self.time_model.fit(X_time_scaled, y_time)
        
        self.trained = True
        print(f"✅ 学習完了: {len(training_data)}サンプル")
        print(f"   成功予測精度: {self.success_model.score(X_success_scaled, y_success):.3f}")
    
    def predict_success(self, start: Tuple, goal: Tuple, 
                       terrain_type: str = None) -> float:
        """
        経路計画の成功確率を予測
        
        Returns:
            成功確率（0-1）
        """
        if not self.trained:
            return 0.5
        
        features = self.extract_features(start, goal, terrain_type)
        features_scaled = self.scaler.transform([features])
        
        prob = self.success_model.predict_proba(features_scaled)[0][1]
        return prob
    
    def predict_computation_time(self, start: Tuple, goal: Tuple,
                                terrain_type: str = None) -> float:
        """
        計算時間を予測
        
        Returns:
            予測計算時間（秒）
        """
        if not self.trained or not hasattr(self, 'time_model'):
            return 0.0
        
        features = self.extract_features(start, goal, terrain_type)
        features_scaled = self.scaler.transform([features])
        
        time_pred = self.time_model.predict(features_scaled)[0]
        return max(0.0, time_pred)
    
    def save_model(self, filepath: str):
        """モデルを保存"""
        if not self.trained:
            print("モデルが学習されていません")
            return
        
        model_data = {
            'success_model': self.success_model,
            'time_model': self.time_model if hasattr(self, 'time_model') else None,
            'scaler': self.scaler
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)
        
        print(f"✅ モデル保存: {filepath}")
    
    def load_model(self, filepath: str):
        """モデルを読み込み"""
        if not Path(filepath).exists():
            print(f"モデルファイルが見つかりません: {filepath}")
            return
        
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)
        
        self.success_model = model_data['success_model']
        self.time_model = model_data['time_model']
        self.scaler = model_data['scaler']
        self.trained = True
        
        print(f"✅ モデル読み込み: {filepath}")

# 学習データを既存の実験結果から作成
def create_training_data_from_results(results_file: str):
    """実験結果から学習データを作成"""
    import json
    
    with open(results_file) as f:
        data = json.load(f)
    
    training_data = []
    
    if 'results' not in data:
        return training_data
    
    for terrain, terrain_results in data['results'].items():
        terrain_short = terrain.split('_')[0]  # 'flat', 'gentle', etc.
        
        for algo, algo_results in terrain_results.items():
            for result in algo_results:
                training_data.append({
                    'start': result.get('start', [0, 0, 0]),
                    'goal': result.get('goal', [0, 0, 0]),
                    'path': result.get('path', []),
                    'terrain': terrain_short,
                    'success': result.get('success', False),
                    'computation_time': result.get('computation_time', 0),
                    'algorithm': algo
                })
    
    return training_data

if __name__ == '__main__':
    # テスト
    predictor = MLPathPredictor()
    
    # 既存の実験結果から学習
    training_data = create_training_data_from_results(
        '../results/efficient_terrain_results.json'
    )
    
    if training_data:
        predictor.train(training_data)
        predictor.save_model('../models/path_predictor.pkl')
        
        # テスト予測
        prob = predictor.predict_success(
            start=(0, 0, 0.2),
            goal=(20, 20, 0.2),
            terrain_type='flat'
        )
        
        time_pred = predictor.predict_computation_time(
            start=(0, 0, 0.2),
            goal=(20, 20, 0.2),
            terrain_type='flat'
        )
        
        print(f"\n予測結果:")
        print(f"  成功確率: {prob:.1%}")
        print(f"  推定時間: {time_pred:.2f}秒")



