Unity 可視化セットアップ手順

ファイル配置（事前準備）
- JSON ファイル（`demo_small_moderate.json`, `full_benchmark_results.json`）を `Assets/StreamingAssets/` に置いてください。
- 必要に応じて `Assets/Materials/` に `meshMaterial` を追加してください。

スクリプト
- `Assets/Scripts/TerrainVisualization.cs` : 地形の読み込み・メッシュ化・色分け
- `Assets/Scripts/PathVisualization.cs` : 経路描画＋アニメーション
- `Assets/Scripts/ComparisonDemo.cs` : 5 分割比較デモ
- `Assets/Scripts/CameraControl.cs` : マウス操作でのカメラ制御

推奨シーン作成手順
1. 新規 Scene を作成。Hierarchy に空 GameObject を作り `TerrainVisualization` をアタッチ。
2. `jsonFileName` を `demo_small_moderate.json` に設定。`StreamingAssets` に配置済みであることを確認。
3. 同じシーンに `PathVisualization` を追加して `full_benchmark_results.json` を指定。
4. 比較デモは別 Scene を作成し、`ComparisonDemo` を配置。5 個の子オブジェクトを `scenarioRoots` に割り当て、テキスト UI を用意して `timeTexts` に割り当てる。

スクリーンショットと動画の取得
- Unity Editor の `Game` ビューからスクリーンショットを撮る（メニュー: GameView -> Save Screenshot など）
- 長尺の録画は `Unity Recorder` を使う（Package Manager でインストール）。Recording を設定して MP4 を出力。

備考
- JSON のスキーマが異なる場合は `PointCloudJSON` / `BenchmarkJSON` のクラスを編集してください。
- 実行環境: Unity 2020 以降を推奨。
