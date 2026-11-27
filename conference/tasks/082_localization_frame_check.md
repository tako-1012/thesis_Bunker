# 指示書 082：078 の記録で、位置の誤差が 12〜34m にもなった原因を調べる（座標の合い方の確かめ）

> **状態：実行中（研究 PC、チャット：研究PC実行。078 の走行は止めずに）**。コードは変えない。調べるためのスクリプトは `conference/results/eval_078/diag/` に足してよい。
> 最初に `AGENTS.md`、`CLAUDE.md`、`conference/RESEARCH_PC_ja.md`、`conference/tasks/075_landmark_world.md`・`076_offline_localization.md`・`077_recording_bridge.md`・`078_landmark_localization_eval.md`、
> それぞれの `results/` の `REPORT_ja.md`・`REVIEW_ja.md`、`conference/tapp/sensor_recording.py`、`conference/experiments/recording_bridge.py`・`offline_localization.py`、
> `conference/ros2_jazzy/gz_checks/sensor_recorder.py`・`landmark_sdf.py`、`conference/tapp/landmark_world.py`（`reference_cloud.npz` の作り方）、`conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/lidar.py`・`model.py` を読むこと。

## 背景（別の環境の会話は共有されないので、ここに書く）
- 078 の 1 回目（`08OB88_-1417`、目印 160 個/ha＝305 個、シード 0）の記録に 076 の道具をかけると、位置の誤差が、積み上げで平均 12m・最大 34m、**地図に重ねるだけでも平均 11m・最大 30m**になった。
- 最初の位置のずれは 0.5m・2° だけで、目印もたくさんあるので、本来は地図に重ねればすぐ正解に戻るはず。合成のデータ（076・077 のテスト）ではうまくいっていた。
- そのため、**記録（LiDAR の点・正解の位置・取り付け位置）と地図の点群（`reference_cloud.npz`）の座標が合っていない**疑いが強い。たとえば：LiDAR の点の座標の向き（どちらが前・左・上か）、取り付け位置の基準（モデルの原点か `base_link` か）、正解の位置の基準と時刻の合わせ方、地図の点群の座標（Gazebo の世界の座標か）。
- 078 の走行は続けてよい（記録を取ることは、この道具と関係ない）。

## やること（078 の走行を止めない。`nice -n 19`、スレッドは 2 つまで）
1. 078 の終わった回の記録から、3 回分（1 回目を含む）を選ぶ。
2. 各回の LiDAR のスキャンを 20 枚ほど取り、**正解の位置 × 取り付け位置（077 の `recording_bridge` で読んだもの）**で世界の座標に直し、`reference_cloud.npz` の点までの最近傍の距離（中央値・90% 値）を出す。座標が合っていれば、数 cm 程度になるはず。
3. 合わない場合に、どの取り違えで合うかを試す（いずれも、その回の記録とスキャンだけで試す。コードは変えない）：
   - 取り付け位置なし（LiDAR の点をそのまま正解の位置で動かす）、取り付け位置の高さを ±0.35m ずらす
   - LiDAR の点の x・y の入れ替え、向きの反転（x→−x など）、z 軸まわりに ±90°・180°
   - 正解の位置の時刻を ±0.1s・±0.5s ずらす
   - 正解の位置の向き（四元数）の並び（xyzw と wxyz）の取り違え
   どれで最近傍の距離が最も小さくなるかを表にする。
4. あわせて、正解の位置の軌跡（記録の `truth_values`）と、その回の `pose_trace` の正解の位置が同じかも確かめる。
5. 1 回目の走行が LiDAR の点群が古くなって止まった（実測 0.952 倍）ことについて、目印 160 個/ha の回の実測の倍率と、点群が古くなった回の数を、終わった回の分だけ一覧にする（走らせ直さない）。

## 守ること
- コードは変えない。値も変えない。078 の走行を止めない・遅くしない。
- 生の記録は研究 PC に置く。Git には、調べたスクリプトと、結果の表・ログだけを入れる（`conference/results/eval_078/diag/`）。push は Mac を経由する。

## Mac の Claude に持ち帰る報告
1. コミット ID、push、使ったスクリプトとコマンド。
2. 3 回分の、そのままの最近傍の距離（中央値・90% 値）と、取り違えを試した表（いちばん合ったもの）。
3. 正解の位置どうしの一致の確かめ。
4. 160 個/ha の回の実測の倍率と、点群が古くなった回の一覧。
5. できなかったこと、自信がないこと。
