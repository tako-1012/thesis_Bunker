# 🤖 バンカー3D経路可視化システム

## 🚀 超簡単！ワンクリック起動

### 人間がやること（たった3ステップ！）

1. **ターミナルでスクリプト実行**
```bash
   cd ~/thesis_work
   ./START_VISUALIZATION.sh
```

2. **Unity が起動したら（1-2分待つ）**
   - メニューバー > `PathPlanning` > `🚀 完全自動セットアップ`
   - ダイアログで `OK` をクリック
   - 30秒待つ

3. **Play ボタンをクリック**
   - ▶ ボタンを押す
   - 完了！バンカーが動きます！

---

## 🎮 操作方法

### キーボード
- `Space` : 再生/一時停止
- `R` : リセット
- `Escape` : 停止
- `1` / `2` / `3` : カメラ切り替え
- `N` / `P` : 次/前のシナリオ
- `F9` : デモ動画撮影開始
- `F10` : ハイライトリール撮影

### マウス
- UI ボタンをクリック
- スライダーで速度調整
- ドロップダウンでシナリオ選択

---

## 📹 デモ動画撮影

### 自動撮影
1. Play モードにする
2. `F9` キーを押す
3. 自動的に3つのシナリオを撮影
4. `/home/hayashi/thesis_work/demo_videos/` に保存

### 手動撮影
1. 好きなシナリオを選択
2. メニュー > `PathPlanning` > `📹 デモ動画撮影`
3. 撮影開始

---

## ⚠️ トラブルシューティング

### Unity が起動しない
```bash
# Unity Hub から手動で開く
# プロジェクト: /home/hayashi/thesis_work/simulation/Bunker_Simulation
```

### データが読み込めない
```bash
# データパスを確認
ls ~/thesis_work/ros2/ros2_ws/src/bunker_ros2/simulation_manager/scenarios/
ls ~/thesis_work/ros2/ros2_ws/src/bunker_ros2/simulation_manager/results/final_results.json
```

### バンカーが表示されない
1. Unity エディタで
2. メニュー > `PathPlanning` > `🚀 完全自動セットアップ`
3. 再度実行

---

## 🎯 システム動作確認

Play モード開始時に以下が表示されれば成功：
```
=================================
🎮 バンカー3D経路可視化システム
=================================

✅ シナリオ読み込み完了

📋 操作方法:
  Space    : 再生/一時停止
  ...
```

---

## 📊 完成！

人間の作業：**たった3クリック**

1. スクリプト実行
2. 自動セットアップ OK
3. Play ボタン

**あとは全自動で動きます！🎉**
