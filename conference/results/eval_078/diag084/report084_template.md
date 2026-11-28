# 084　LiDAR の車体反射と位置推定

078 の 3 走行の **{{SCANS}} スキャン**で、モデルから求めた車体の箱に入る点と LiDAR から 1.0 m 未満の点はともに 0 点だった。追加の除外をかけても、076 の 3 通りの誤差、GICP の収束、固有値と弱い向きがすべて一致した。この 3 走行では、車体反射が位置推定を狂わせたという仮説を支持する点は観測されなかった。

地図との重ね合わせで未収束だった 1,385 試行のうち、1,384 試行で最小固有値が 1 以下だった。弱い向きは海岸沿い 1,038 試行、海岸横断 347 試行で、水平方向に集中した。平らな地形で水平方向の位置を決めにくいという説明と整合する。対応点の取り方や初期位置の影響もあり、地形が未収束の原因としてどれほど効いたか、KISS-ICP の積み上げが大きくずれた直接の原因は、今回の比較では特定できていない。

## 近くの点と車体の範囲

砂浜は 1417 が `08OB88_-1417`、0205 が `08OB86_-0205`。点の数は有限の XYZ を持つ戻り点で、距離帯は 0.1 m 以上 1.0 m 未満、1.0 m 以上 2.0 m 未満。x・y・z の欄は、その距離帯に入る全点の最小・中央値・最大。記録されなかった戻り点は集計に含めていない。

{{POINTS}}

1417・160・0 の 1〜2 m の戻り点は、最初のスキャンから 17.5〜35.3 秒の間の 44 スキャンに出た。すべて走行中で、17,658 点すべてが LiDAR より下にあった。前／後は 8,959／8,699 点、左／右は 13,465／4,193 点だった。

車体と車輪の衝突形状を、記録にある LiDAR の取り付け位置 `(-0.24, 0, 1.40) m` で LiDAR 座標に移し、軸に沿った外接箱の各面に 5 cm 加えた。範囲は x が −0.3215〜0.8015 m、y が −0.4395〜0.4395 m、z が −1.450〜−0.795 m。箱の中で最も浅い俯角でも約 41°で、モデルの最も下向きの光線は下向き 15°だった。モデル上の LiDAR の測距下限は 0.9 m。

同じ LiDAR 座標に出続けるかは 5 cm の立方格子で調べた。正解の位置のスキャン間移動から、0.05 m/s 以下を静止、0.2 m/s 以上を走行とし、間の速度と速度を求められない先頭スキャンはこの比較から外した。双方で点を観測した同一格子はなかった。0205・40・1 は静止と判定したスキャンがなく、静止中との比較ができていない。

{{MOTION}}

スキャンごとの点数は [near_points_by_scan.csv](near_points_by_scan.csv)、距離帯別の方向と点数は [near_points_by_band.csv](near_points_by_band.csv)、車体の箱は [body_geometry.csv](body_geometry.csv)、静止・走行中の照合は [near_point_recurrence.csv](near_point_recurrence.csv) に保存した。

## 076 の除外前後の比較

車体の箱に入る点、または 1.0 m 未満の点を除外するスキャンを逐次生成し、同じ参照点群と初期値で 076 の `localize` をそれぞれ実行した。初期ずれ（海岸沿い 0.5 m、向き 2°）、組み合わせの補正間隔（積み上げ距離で 5 m）、ボクセル幅、GICP、採否の基準は元の値を使用した。正解位置と同期できなかったスキャンは 0。誤差は同時刻の正解の車体位置からの 3 次元距離。積み上げ単独について、076 は収束試行数を記録していない。

表は **除外前と後で共通**。誤差の CSV と、全重ね合わせ試行の CSV を、処理名の列を除いた全列で照合し、3 走行とも一致した。各条件の行は [replay_comparison.csv](replay_comparison.csv) に両方ある。

{{REPLAY}}

## 収束しなかった試行の固有値と方向

最小固有値は 076 が返す、対応点数で正規化した回転と並進を含む Hessian の値。回転を 1 m の腕の長さで換算し、最小固有値の固有ベクトルを世界座標に移したうえで、076 の規則で向きを分類した。下の 1 は 076 の「組み合わせ」が収束後の採用に使うしきい値。固有値が 1 以下の試行と、GICP が未収束だった試行は別に数えた。0205・40・1 の組み合わせの 1 試行は収束したが、情報量の基準で不採用になった。

{{FAILED}}

各試行の時刻、固有値、世界座標の固有ベクトル 6 成分は、`replay/<走行>/<raw または filtered>/alignments.csv` に保存した。両条件を含む集計は [failed_alignment_summary.csv](failed_alignment_summary.csv) に保存した。

## 実行と確認

- 実行先は `hayashi:~/thesis_Bunker_rtf/conference`。実行コードは `{{PIN}}`。出力のブランチは `claude/084-self-hit`。再生は {{START}} に始まり、{{END}} に完了した。
- 既存の `.venv-localization` を使った。KISS-ICP 1.3.0、small_gicp 1.0.1。全環境の版は [localization_pip_freeze.txt](localization_pip_freeze.txt) に保存した。
- 研究 PC の独立した作業ツリーで、実行コードに対して全 {{TESTS}} テストモジュールを実行した。終了コード {{TEST_EXIT}}。モジュール別の終了コードと出力は [tests/summary.txt](tests/summary.txt) と `tests/` のログを参照。オフライン位置推定と記録読み込みのテストはスキップなし。
- 参照地図とセンサーの生データは研究 PC に保管。パスと SHA-256 は [not_committed.txt](not_committed.txt) と [input_sha256.txt](input_sha256.txt) に記載し、再生後に照合した。

研究 PC の `conference/` で実行したコマンド。再生とテストに `nice -n 19` と 2 論理 CPU の上限を設定した。テストは再生の終了後に走る。

```bash
cpus=$(.venv-localization/bin/python -c 'import os; print(",".join(map(str, sorted(os.sched_getaffinity(0))[:2])))')
diag=results/eval_078/diag084
tmux new-session -d -s replay-084 "nice -n 19 taskset -c $cpus bash $diag/run084.sh > $diag/run084_log.txt 2>&1"
tmux new-session -d -s tests-084 "nice -n 19 taskset -c $cpus bash $diag/verify084.sh > $diag/verify084_log.txt 2>&1"
nice -n 19 taskset -c "$cpus" .venv-localization/bin/python "$diag/render084.py"
```

[run084.sh](run084.sh) が [self_hit084.py](self_hit084.py) で全スキャンの集計と計 6 本の再生を実行し、[render084.py](render084.py) が両条件を照合して表を作った。Gazebo の新規走行は 0 本。

## この比較で残ったこと

検証したのは 078 の 3 記録。車体の箱はシミュレーションの車体と車輪を対象にしており、実機にあるカメラの筐体や取り付け具などの反射は評価していない。未収束時の固有値はその時点の対応点に基づくため、地形そのものの観測しやすさと、推定位置が外れて対応点が変わった影響は切り分けられない。
