# thesis_Bunker

クローラー型ロボット AgileX BUNKER のための、地形を考慮した経路計画の研究リポジトリです。
（卒論 → ICAROB 2026 → 修論）

## フォルダ構成
| 場所 | 中身 | 扱い |
|---|---|---|
| `conference/` | 作り直した実験一式（プランナー、実験、ICAROB の論文、探索的な実験）。**新しい作業はすべてここで行う**。詳しくは `conference/README.md` | 現役 |
| `conference/tasks/` | Codex などに渡す指示書（`AGENTS.md` も参照） | 現役 |
| `ros2/` | ロボット用の ROS2 ワークスペース。大部分は研究室のリポジトリ `hayashilab/bunker_ros2` と `hayashilab/bunker_unity` から持ってきたもの | ここでは変更しない |
| `unity/`、`archive/unity_scripts/`、`scripts/launch_*.sh` | 経路の Unity 可視化と、その起動スクリプト | 保管 |
| `thisis_write/` | 卒論の原稿（LaTeX）と図 | 保管 |
| `scripts/`、`analysis/`、`benchmark_results/`、`results/`、`tables/`、`figures/`、`terrain_test_scenarios/` | 卒論の図表を作るのに使ったスクリプトとデータだけを残したもの | 保管 |
| `documents/` | 参考文献のリストとメモ | 参考 |

## 注意
- **卒論の数値には問題があります**（パラメータ調整の結果が実測ではない、統計値が矛盾している、など）。詳しくは `conference/AUDIT_ja.md` を参照してください。卒論の数値は再利用しないでください。
- 卒論に使っていない古い実験コードと結果は削除しました。Git の履歴からは取り出せます（例：ICAROB に出した時点のコミット `ac9d9e7`）。

## ブランチ
- `main`：確認済みの内容
- `realtime-map`：修論に向けた開発（リアルタイムの地図・再計画）。Codex の作業はここに取り込む

## すぐ試す
```bash
pip install numpy scipy matplotlib pandas
cd conference
python3 -m tests.test_planners
python3 -m tests.test_online
```
