# LAS砂浜6か所でA*とTA*-SをGazebo比較する

`conference/` で実行する。既存のworld・地図・結果には書き込まない。

```bash
bash ros2_jazzy/gz_checks/run_compare_checks.sh results/gazebo_compare
# 既存のイメージを指定する場合
THESIS_ROS_IMAGE=thesis/jazzy-gz:1 bash ros2_jazzy/gz_checks/run_compare_checks.sh /tmp/gazebo-compare-run
# 記録を移動した後も再集計できる
python3 experiments/gz_compare_report.py /tmp/gazebo-compare-run
python3 -m tests.test_gz_compare  # ROS2不要。運動学の試験用記録だけを生成する
```

world生成だけを先に確認する場合（ROS2・Gazebo不要。一時ファイルは終了時に消える）：

```bash
python3 - <<'PY'
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from ros2_jazzy.gz_checks.compare_checks import prepare_cases
with TemporaryDirectory() as directory:
    root = Path(directory)
    manifest = prepare_cases(root / "output", root / "worlds")
    print(json.dumps({k: manifest[k] for k in ("world_exports", "world_errors")},
                     ensure_ascii=False, indent=2))
PY
```

既定イメージ `thesis/jazzy-gz:1` がない場合、既存 `gz_checks/Dockerfile` でビルドする。
これは `osrf/ros:jazzy-desktop-full` にpandasを加えたもの。`THESIS_ROS_IMAGE` で変えられる。
ROSビルド先とworldはコンテナの一時フォルダ、ソースは読取専用、出力だけを `/output` へマウントする。
既定ROS_DOMAIN_IDは49で、`THESIS_ROS_DOMAIN_ID` で変更できる。出力フォルダに既存manifestがある場合は上書きせず止める。

シナリオは `shizuoka_beach_las` のtest先頭6砂浜、200m、seed 0、漂着物なし。
`build_real` の開始・終了点から、既定重みの `run_planner_exact('A*'/'TA*-S')` で計画する。
同じworldを毎方法で新規起動し、同じ初期位置・yaw=0からBUNKERを5秒静置してから出発する。
走り方は既存path_followerの先読み1m・最大速度1m/s・最大角速度1rad/s・到着許容0.3m・停滞10秒を使う。
worldの形状・摩擦は既存exporter/modelの仮定を引き継ぎ、test走行からパラメータを調整しない。
world自体は一時保存だけで、復元用の地図・経路・環境・高さ画像の誤差をmanifestに残す。
既存exporterの誤差上限0.1mを満たせない場合は、その地形の両方法を実行失敗として記録し、他の地形を続ける。
地形や誤差上限を変更せず、全ケースを表に残し、最後の終了コードを非0にする。

`manifest.json` と `raw/` が原記録、`maps/` が解析用地図、`report/` が再計算した表・図。
解析は `analyze_run` を使い、元のmission JSONを書き換えず、一時ビューで地図パスを解決する。
roll/pitchの95%と最大は記録の絶対角度から算出し、登りは記録zの正の増分の総和。ノイズ除去をしていないので登りには揺れも含む。
地図からの値は計画経路に `evaluate` を適用したものを併記する。記録xyの地図推定角も別列で区別する。
エネルギーを集計しない。6か所だけの記述比較なので検定しない。時間や傾きの対の差は両方法完走の組だけで出し、未完走や未実行は一覧に残す。
Gazeboを実行できない環境では、物理の測定値を埋めずに「未実行」と報告する。
