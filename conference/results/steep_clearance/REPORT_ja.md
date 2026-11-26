# 065 急斜面までの距離を使う余白

ブランチは `codex/065-steep-clearance`。起点は `realtime-map` の `58379c12e30b99ad57042675a0c62abc32fd3180`。実装・テスト・再計算結果は `0ff8f12420557ecb99890cad11942188c85ad88d`。本報告は後続コミットに収録する。

## 1. 安全性

060と同じ053の14件の終了時地図と、047の記録にある失敗時の始点・目標を使った。地形 `sensor|prior`、障害物 `centre|distance`、急斜面 `centre|distance` の8条件で、通常と同じランタイムのA*と平滑化を実行した。保存地図の検出障害物を固定し、`sensor` ではその終了時の標高とコスト、`prior` では署名照合済みの事前標高を使った。急斜面 `centre` の経路成立、目標遮断、経路長、地形コスト、箱までの最短距離は、対応する060の結果と一致した。連続値の照合は絶対誤差 `1e-10` 以下。 [060の再計算](../distance_clearance/replay.py) · [065の走行別出力](runs.csv)

真の急斜面は、署名照合済みの評価用標高で25°を超える0.5 mセル。最短距離は連続経路の線分から、そのセルの閉矩形の縁までを測った。「急斜面本体」と「急斜面＋格子余白」は064と同じ通過長で、後者は既存の0.5 m膨張。別に、連続距離が0.5 m未満、1.0 m未満の区間の長さを求めた。箱は060と同じ方法で真値の漂着物から矩形を復元し、海と欠測を含めた岩マスクを署名付き真値と照合した。下表の長さは見つかった経路の合計。最小と中央値は各経路の最短距離から求めた。 [064の評価](../eval_064/REPORT_ja.md) · [集計CSV](summary.csv)

| 地形 | 障害物 | 急斜面 | 経路あり | 急斜面まで最小／中央値 m | 急斜面本体 m | 急斜面＋格子余白 m | 急斜面から0.5 m未満 m | 急斜面から1.0 m未満 m | 箱まで最小／中央値 m |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| sensor | centre | centre | 1 | 40.406 / 40.406 | 0 | 0 | 0 | 0 | 0.750 / 0.750 |
| sensor | centre | distance | 1 | 40.406 / 40.406 | 0 | 0 | 0 | 0 | 0.750 / 0.750 |
| sensor | distance | centre | 1 | 40.406 / 40.406 | 0 | 0 | 0 | 0 | 0.750 / 0.750 |
| sensor | distance | distance | 1 | 40.406 / 40.406 | 0 | 0 | 0 | 0 | 0.750 / 0.750 |
| prior | centre | centre | 10 | 0.354 / 41.843 | 0 | 0 | 2.476 | 66.259 | 0.354 / 0.655 |
| prior | centre | distance | 10 | 0.354 / 41.843 | 0 | 0 | 1.036 | 52.997 | 0.354 / 0.655 |
| prior | distance | centre | 10 | 0.354 / 41.843 | 0 | 0 | 2.476 | 66.259 | 0.354 / 0.791 |
| prior | distance | distance | 10 | 0.354 / 41.843 | 0 | 0 | 1.036 | 52.997 | 0.354 / 0.791 |

`prior` では、障害物余白のどちらの条件でも、急斜面の連続距離0.5 m未満と1.0 m未満の長さが減った。急斜面までの最小距離は0.354 mのまま。格子の0.5 m膨張は従来の格子マスクで、対角の位置や経路線分はその外でも急斜面セルの縁から0.5 m未満になり得る。両方を `distance` にしたとき、箱の最短距離の集計最小・中央値は060と同じだった。0167の一部の経路は箱に近づいたので、箱までの距離は走行別にも見る。

## 2. 経路と目標

地形コストは、060と同じソフトな事前地図を含む地形項の経路積分（コスト×m）。障害物と急斜面の距離コストは積分の指標から除いた。

| 地形 | 障害物 | 急斜面 | 目標遮断 / 14 | 経路あり / 14 | 平均経路長 m | 平均地形コスト × m |
|---|---|---|---:|---:|---:|---:|
| sensor | centre | centre | 13 | 1 | 2.736 | 0.492 |
| sensor | centre | distance | 13 | 1 | 2.699 | 0.537 |
| sensor | distance | centre | 13 | 1 | 2.736 | 0.492 |
| sensor | distance | distance | 13 | 1 | 2.699 | 0.537 |
| prior | centre | centre | 4 | 10 | 26.682 | 4.140 |
| prior | centre | distance | 4 | 10 | 27.516 | 4.226 |
| prior | distance | centre | 4 | 10 | 27.363 | 4.185 |
| prior | distance | distance | 4 | 10 | 28.088 | 4.280 |

`prior` で障害物 `distance` を使ったとき、急斜面距離コストの追加で、同じ10件の経路が平均0.725 m延び、積分地形コストは0.095コスト×m増えた。

### 3. 08OB88_-0167 の第5地点 (137, 294)

`sensor` では4地図すべてで目標が塞がった。下表のPは `prior` ＋障害物 `centre`、PDは `prior` ＋障害物 `distance`。矢印は急斜面余白 `centre → distance`。急斜面本体と格子余白の通過長は全条件0。P・PDの4地図で両方式とも経路が見つかった。 [各回の結果](visit_0167.csv)

| 元の記録 | 条件 | 急斜面までの最短 m | 急斜面から0.5 m未満 m | 急斜面から1.0 m未満 m | 箱までの最短 m | 経路長 m |
|---|---|---:|---:|---:|---:|---:|
| C0 r2 | P | 0.354 → 0.354 | 1.055 → 0.259 | 16.611 → 13.249 | 4.127 → 3.750 | 35.438 → 38.103 |
| C0 r2 | PD | 0.354 → 0.354 | 1.055 → 0.259 | 16.611 → 13.249 | 4.127 → 3.750 | 35.438 → 38.103 |
| C1 r1 | P | 0.354 → 0.354 | 0.183 → 0.259 | 16.518 → 13.249 | 3.679 → 3.250 | 42.482 → 43.954 |
| C1 r1 | PD | 0.354 → 0.354 | 0.183 → 0.259 | 16.518 → 13.249 | 3.679 → 3.250 | 42.482 → 43.954 |
| C1 r2 | P | 0.354 → 0.354 | 1.055 → 0.259 | 16.611 → 13.249 | 4.257 → 4.217 | 33.378 → 36.113 |
| C1 r2 | PD | 0.354 → 0.354 | 1.055 → 0.259 | 16.611 → 13.249 | 4.257 → 4.250 | 33.378 → 35.023 |
| C1 r3 | P | 0.354 → 0.354 | 0.183 → 0.259 | 16.518 → 13.249 | 3.694 → 3.250 | 42.982 → 44.454 |
| C1 r3 | PD | 0.354 → 0.354 | 0.183 → 0.259 | 16.518 → 13.249 | 3.694 → 3.250 | 42.982 → 44.454 |

1.0 m未満の長さは全4地図で減った。0.5 m未満の長さは2地図で減り、残り2地図はそれぞれ0.076 m増えた。0.354 mは固定された第5地点自体の距離で、すべての経路がこの値に達する。箱までの最短距離は全経路で3.25 m以上。064のP・PDの傾き停止は6件で、うち3件で実軌跡の格子余白通過は0だった。今回の距離指標から、傾き反復停止を解消できるかは分からない。 [064の停止結果](../eval_064/REPORT_ja.md) · [057のレビュー](../eval_057/REVIEW_ja.md) · [050のレビュー](../eval_050/REVIEW_ja.md)

## 4. 合成地形

25°を超える帯を矩形として定義し、0.5 mセル中心をサンプリングして急斜面マスクを作った。計画はそのマスクを参照し、最短距離は元の連続帯に対して測った。1.2 mと1.8 mの隙間はいずれも格子化で1.5 m相当になった。外側を岩で塞ぐ場合も調べた。全条件で目標は開き、経路が見つかった。 [走行別出力](synthetic.csv)

| 場面 | 経路長 centre → distance m | 急斜面まで最短 centre → distance m |
|---|---:|---:|
| 急斜面の横 | 13.000 → 13.472 | 0.750 → 1.750 |
| 1.2 mの隙間、迂回可 | 13.000 → 18.372 | 0.600 → 1.768 |
| 1.2 mの隙間のみ | 13.000 → 13.000 | 0.600 → 0.600 |
| 1.8 mの隙間、迂回可 | 13.000 → 18.372 | 0.900 → 1.768 |
| 1.8 mの隙間のみ | 13.000 → 13.000 | 0.900 → 0.900 |
| 2.5 mの隙間、迂回可・隙間のみ | 13.000 → 13.000 | 1.250 → 1.250 |

## 実装と差分

| ファイル（`conference/` 内） | 内容 |
|---|---|
| `tapp/steep_clearance.py`、`tapp/distance_clearance.py` | 060のタイル距離計算と二次コストを再利用。急斜面の追加・削除で、距離が変わり得るタイルだけを再計算する。平滑化と経路接続では、両距離を独立に比較する。 |
| `tapp/pointcloud_map_fine.py` | FineとMultiの地形レイヤーから距離を更新し、計画に同じ版の距離コストと矩形を渡す。 |
| `ros2_jazzy/gz_checks/distance_runtime.py`、`lidar_runtime.py`、`endpoint_runtime.py`、`plan_maps.py` | 計画の倍率に急斜面のコストを加算し、平滑化に適用。計画地図に `steep_cost` を保存する。 |
| 同じディレクトリの `lidar_checks.py`、`lidar_map.py`、`lidar_planner.py`、`run_lidar_checks.sh` | fine専用のオプション、manifest、ROSの受け渡し。 |
| `tests/test_steep_clearance.py` | 変更前と同環境のバイト比較、ハードマスク、距離と加算、経路と平滑化、追加・削除と全体再計算、manifest・ROS・偽Docker・記録の検証。 |
| `results/steep_clearance/` | 再計算スクリプト、全組み合わせ・集計・0167・合成地形のCSV、ログ、報告。 |

距離は粗格子中心から急斜面セルの縁まで。分類値は `sensor`・`prior`・`prior_veto` の既存の `steep` を使う。`R_hard=0.5` m、`R_soft=1.5` m、`w=1.0`。ソフト項は指示書の開区間で加算し、0.5 mの外から近づくと1に近づく。急斜面本体・既存の膨張・観測済みの扱いを保つ。未観測セルにも距離コストを加え、既存の観測マスクとハード判定は維持する。`no_inflate` は引き続き障害物内の急斜面からのハード膨張だけを抑える。急斜面が追加・削除されたときは、タイル単位の距離下限で影響範囲を絞る。初期化や最後の急斜面の消失では、正確な距離を求めるために全域を更新する場合がある。

## 研究PCでの評価案

064段階1と同じGPU描画・1.0倍、同じ砂浜・地点・反復番号で、まず0167の `prior` を固定する。障害物 `centre|distance` と急斜面 `centre|distance` の2×2を比較する。先に真の急斜面・余白への計画と軌跡の進入、箱の最短距離・漂着物通過、`unsafe_tilt` と再停止、転倒を記録する。第5区間では停止位置の25°判定と、余白への進入の有無を別に見る。その後に第5地点への到達、完走、経路長、地図更新・探索時間を見る。他の砂浜を加える場合は064と同じ地点で箱への接近と経路長を照合する。 [064の起動条件](../eval_064/run064.sh)

~~~bash
cd ~/thesis_Bunker_rtf/conference
for obstacle in centre distance; do
  for steep in centre distance; do
    THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH=08OB88_-0167 THESIS_ROS_DOMAIN_ID=66 \
      THESIS_RENDER=gpu THESIS_STALE_TIMEOUT_S=1.0 \
      bash ros2_jazzy/gz_checks/run_lidar_checks.sh \
        "$HOME/thesis_checks/065_0167_${obstacle}_${steep}_r1" \
        --patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2 \
        --sensors lidar_real+depth2 --diagnostics --real-time-factor 1.0 --save-plan-maps --pose-trace \
        --terrain-source prior --obstacle-clearance "$obstacle" --steep-clearance "$steep" || exit
  done
done
~~~

## 限界

Gazebo・研究PCは未使用。今回の0167は030の保存済み地図上の静的な再探索で、050・057・064の停止時点の生地図・実軌跡の再現、追従ずれ、停止頻度、オンラインの計算時間は未確認。急斜面の削除時は現存する急斜面の検索木を作り直し、影響のあり得るタイルで距離を引き直す。距離コストだけが変わった場合も、再計画を開始する条件は従来どおり。急斜面の距離コストは計画に渡る急斜面に基づくため、誤検出の解消や未検出の急斜面の回避は別の課題となる。合成地形は格子と帯の向きを固定しており、0.5 m格子の分解能や配置により狭い通路の結果は変わり得る。

## 実行コマンド

既存venv `/tmp/thesis036-venv` を使用した。Python 3.12.14、`pip check` は `No broken requirements found.`。Bashの構文確認も成功した。新規テストの初期3回では、障害物に覆われたセルを急斜面だけのハード判定に使ったことと、履歴サイズが既存の最小3点を下回ったことを修正した。実装の閾値は変更していない。

~~~bash
git fetch origin realtime-map
git merge-base --is-ancestor 58379c1 FETCH_HEAD
git switch -c codex/065-steep-clearance FETCH_HEAD
cd conference
mkdir -p /tmp/065-logs
export OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/065-mpl XDG_CACHE_HOME=/tmp/065-cache
/tmp/thesis036-venv/bin/python -u -m tests.test_planners > /tmp/065-logs/before.txt 2>&1
/tmp/thesis036-venv/bin/python --version
/tmp/thesis036-venv/bin/python -m pip check
bash -n ros2_jazzy/gz_checks/run_lidar_checks.sh
THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH=08OB88_-0167 \
  /tmp/thesis036-venv/bin/python -u ros2_jazzy/gz_checks/lidar_checks.py \
    --output /tmp/065-prepare --prepare-only --patch-count 3 --map fine --ground-estimate non_obstacle \
    --terrain-source prior --obstacle-clearance distance --steep-clearance distance \
    --sensors lidar_real+depth2 --online-fixes v2 --diagnostics --save-plan-maps --pose-trace \
    --real-time-factor 1.0 > /tmp/065-logs/prepare.txt 2>&1
mkdir -p /tmp/065-final /tmp/065-repro
for output in /tmp/065-final /tmp/065-repro; do
  /tmp/thesis036-venv/bin/python -u -m results.steep_clearance.replay --out "$output" > "$output/replay_log.txt"
done
diff -r /tmp/065-final /tmp/065-repro
cp /tmp/065-final/{runs.csv,summary.csv,visit_0167.csv,synthetic.csv,replay_log.txt} results/steep_clearance/
set -o pipefail
printf '%s\n' tests/test_*.py | sed 's/\.py$//;s|/|.|g' |
  xargs -P 4 -I '{}' bash -c '
    module=$1
    log=/tmp/065-logs/$module.txt
    printf "\$ /tmp/thesis036-venv/bin/python -u -m %s\n" "$module" > "$log"
    /tmp/thesis036-venv/bin/python -u -m "$module" >> "$log" 2>&1
    status=$?
    printf "\nexit=%s\n" "$status" >> "$log"
    printf "%s exit=%s\n" "$module" "$status"
    exit "$status"
  ' bash '{}'
# 上の一覧で既存52本を実行。新規テストは個別に実行。
/tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance
cd ..
git diff --cached --check
git commit -m '065: 急斜面からの距離コストを追加する'
git diff --check 58379c1..HEAD
git add conference/results/steep_clearance/REPORT_ja.md
git commit -m '065: 距離余白の比較とテスト結果を報告する'
git push -u origin codex/065-steep-clearance
git ls-remote --heads origin refs/heads/codex/065-steep-clearance
~~~

## 準備確認と再計算の出力全文

準備確認は0167のみを選び、manifestの急斜面と障害物の距離設定、記録オプションを確認した。再計算は2回で、CSVとログの全5ファイルがバイト単位で一致した。

~~~text
Task065 preparation only; Gazebo not executed: /tmp/065-prepare

summary.csv
terrain,obstacle_clearance,steep_clearance,maps,min_steep_m,median_steep_m,min_box_m,median_box_m,steep_m,steep_or_grid_halo_m,steep_below_05_m,steep_below_10_m,blocked_goals,routes,path_m_mean,terrain_cost_m_mean
sensor,centre,centre,14,40.40575454065918,40.40575454065918,0.75,0.75,0.0,0.0,0.0,0.0,13,1,2.73606797749979,0.49216981462022863
sensor,centre,distance,14,40.40575454065918,40.40575454065918,0.75,0.75,0.0,0.0,0.0,0.0,13,1,2.699172818834085,0.5367230285258453
sensor,distance,centre,14,40.40575454065918,40.40575454065918,0.75,0.75,0.0,0.0,0.0,0.0,13,1,2.73606797749979,0.49216981462022863
sensor,distance,distance,14,40.40575454065918,40.40575454065918,0.75,0.75,0.0,0.0,0.0,0.0,13,1,2.699172818834085,0.5367230285258453
prior,centre,centre,14,0.3535533905932738,41.842684339709855,0.3535533905932738,0.6545084971874737,0.0,0.0,2.4756103849851474,66.25872337871334,4,10,26.681825522755464,4.139634053641437
prior,centre,distance,14,0.3535533905932738,41.842684339709855,0.3535533905932738,0.6545084971874737,0.0,0.0,1.0360261019191745,52.99707208394574,4,10,27.51634080642544,4.225717659239565
prior,distance,centre,14,0.3535533905932738,41.842684339709855,0.3535533905932738,0.7905694150420949,0.0,0.0,2.4756103849851474,66.25872337871334,4,10,27.362797329837843,4.185275865319356
prior,distance,distance,14,0.3535533905932738,41.842684339709855,0.3535533905932738,0.7905694150420949,0.0,0.0,1.0360261019191745,52.99707208394574,4,10,28.088269954042865,4.280256410329132
visit_0167.csv
archive,patch,condition,rep,visit,start,goal,terrain,obstacle_clearance,steep_clearance,goal_blocked,route,path_m,terrain_cost_m,min_steep_m,start_steep_m,goal_steep_m,steep_m,steep_or_grid_halo_m,steep_below_05_m,steep_below_10_m,min_box_m
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",sensor,centre,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",sensor,centre,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",sensor,distance,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",sensor,distance,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",prior,centre,centre,False,True,35.437693787793975,8.036665258192935,0.3535533905932738,2.3717082451262845,0.3535533905932738,0.0,0.0,1.0547924906003545,16.61119316180248,4.1266829837210395
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",prior,centre,distance,False,True,38.10331536298846,8.178042391501736,0.3535533905932738,2.3717082451262845,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,3.75
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",prior,distance,centre,False,True,35.437693787793975,8.036665258192935,0.3535533905932738,2.3717082451262845,0.3535533905932738,0.0,0.0,1.0547924906003545,16.61119316180248,4.1266829837210395
results/eval_ground_endpoint/runs/08OB88_-0167/C0_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C0,2,5,"(146, 281)","(137, 294)",prior,distance,distance,False,True,38.10331536298846,8.178042391501736,0.3535533905932738,2.3717082451262845,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,3.75
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",sensor,centre,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",sensor,centre,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",sensor,distance,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",sensor,distance,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",prior,centre,centre,False,True,42.482431216295964,8.605334268579696,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.1830127018922193,16.518168527554195,3.6791183185934564
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",prior,centre,distance,False,True,43.954303149050354,8.883331241694048,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,3.25
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",prior,distance,centre,False,True,42.482431216295964,8.605334268579696,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.1830127018922193,16.518168527554195,3.6791183185934564
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r1/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,1,5,"(158, 280)","(137, 294)",prior,distance,distance,False,True,43.954303149050354,8.883331241694048,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,3.25
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",sensor,centre,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",sensor,centre,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",sensor,distance,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",sensor,distance,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",prior,centre,centre,False,True,33.378197370862544,7.803837073495323,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,1.0547924906003545,16.61119316180248,4.257346591481601
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",prior,centre,distance,False,True,36.113311366185265,7.9727700735569185,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,4.216628045805952
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",prior,distance,centre,False,True,33.378197370862544,7.803837073495323,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,1.0547924906003545,16.61119316180248,4.257346591481601
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r2/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,2,5,"(142, 282)","(137, 294)",prior,distance,distance,False,True,35.02288477153561,8.061739467673405,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,4.25
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",sensor,centre,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",sensor,centre,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",sensor,distance,centre,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",sensor,distance,distance,True,False,,,,,,,,,,
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",prior,centre,centre,False,True,42.98175781562215,8.681783430578616,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.1830127018922193,16.518168527554195,3.6938639860640485
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",prior,centre,distance,False,True,44.454303149050354,8.954312380075143,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,3.25
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",prior,distance,centre,False,True,42.98175781562215,8.681783430578616,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.1830127018922193,16.518168527554195,3.6938639860640485
results/eval_ground_endpoint/runs/08OB88_-0167/C1_r3/physical_1/raw/08OB88_-0167,08OB88_-0167,C1,3,5,"(159, 280)","(137, 294)",prior,distance,distance,False,True,44.454303149050354,8.954312380075143,0.3535533905932738,2.25,0.3535533905932738,0.0,0.0,0.25900652547979364,13.249268020986435,3.25
synthetic.csv
case,gap_m,forced,raster_gap_m,steep_clearance,goal_blocked,route,path_m,terrain_cost_m,detour_m,min_steep_m,start_steep_m,goal_steep_m,steep_m,steep_or_grid_halo_m,steep_below_05_m,steep_below_10_m,min_raster_steep_m
beside,,False,,centre,False,True,13.0,0.0,0.0,0.75,3.092329219213245,3.092329219213245,0.0,0.0,0.0,8.322875655532295,0.75
beside,,False,,distance,False,True,13.47213595499958,0.0,0.4721359549995796,1.75,3.092329219213245,3.092329219213245,0.0,0.0,0.0,0.0,1.75
gap,1.2,False,1.5,centre,False,True,13.0,0.0,0.0,0.5999999999999996,4.044749683231337,6.029925372672534,0.0,0.0,0.0,4.6,0.75
gap,1.2,False,1.5,distance,False,True,18.371630891611243,0.0,5.371630891611243,1.7677669529663689,4.044749683231337,6.029925372672534,0.0,0.0,0.0,0.0,1.4142135623730951
gap,1.2,True,1.5,centre,False,True,13.0,0.0,0.0,0.5999999999999996,4.044749683231337,6.029925372672534,0.0,0.0,0.0,4.6,0.75
gap,1.2,True,1.5,distance,False,True,13.0,0.0,0.0,0.5999999999999996,4.044749683231337,6.029925372672534,0.0,0.0,0.0,4.6,0.75
gap,1.8,False,1.5,centre,False,True,13.0,0.0,0.0,0.9000000000000004,4.1,6.067124524847006,0.0,0.0,0.0,3.871779788708133,0.75
gap,1.8,False,1.5,distance,False,True,18.371630891611243,0.0,5.371630891611243,1.7677669529663689,4.1,6.067124524847006,0.0,0.0,0.0,0.0,1.4142135623730951
gap,1.8,True,1.5,centre,False,True,13.0,0.0,0.0,0.9000000000000004,4.1,6.067124524847006,0.0,0.0,0.0,3.871779788708133,0.75
gap,1.8,True,1.5,distance,False,True,13.0,0.0,0.0,0.9000000000000004,4.1,6.067124524847006,0.0,0.0,0.0,3.871779788708133,0.75
gap,2.5,False,2.5,centre,False,True,13.0,0.0,0.0,1.25,4.190763653560053,6.128825336065631,0.0,0.0,0.0,0.0,1.25
gap,2.5,False,2.5,distance,False,True,13.0,0.0,0.0,1.25,4.190763653560053,6.128825336065631,0.0,0.0,0.0,0.0,1.25
gap,2.5,True,2.5,centre,False,True,13.0,0.0,0.0,1.25,4.190763653560053,6.128825336065631,0.0,0.0,0.0,0.0,1.25
gap,2.5,True,2.5,distance,False,True,13.0,0.0,0.0,1.25,4.190763653560053,6.128825336065631,0.0,0.0,0.0,0.0,1.25
~~~

## テスト出力全文

変更前のプランナーテスト、変更後の既存52本と新規1本がすべて通過した。以下に初期の新規テストの出力も収録する。

~~~text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_planners （変更前）
all planner tests passed
roll-aware tests passed
~~~

~~~text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance （初期の試行 1）
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: identical same-host Fine/Multi, map, manifest, mission, diagnostics and runtime bytes for centre
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis_Bunker/conference/tests/test_steep_clearance.py", line 224, in <module>
    test_masks_and_cost()
  File "/workspace/thesis_Bunker/conference/tests/test_steep_clearance.py", line 113, in test_masks_and_cost
    assert not lethal[11, 11] and field.distance_m[11, 11] < .5  # retain the original hard stencil
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

exit=1

$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance （初期の試行 2）
\$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: identical same-host Fine/Multi, map, manifest, mission, diagnostics and runtime bytes for centre
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis_Bunker/conference/tests/test_steep_clearance.py", line 225, in <module>
    test_masks_and_cost()
  File "/workspace/thesis_Bunker/conference/tests/test_steep_clearance.py", line 114, in test_masks_and_cost
    assert not entries['centre', 'distance'][2][11, 11] and field.distance_m[11, 11] < .5
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

exit=1

$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance （初期の試行 3）
$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: identical same-host Fine/Multi, map, manifest, mission, diagnostics and runtime bytes for centre
2 PASS: unchanged hard stencil, exact square distances and quadratic soft costs add to obstacle costs
3 PASS: route moves farther from slopes and all three forced gaps remain reachable
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis_Bunker/conference/tests/test_steep_clearance.py", line 227, in <module>
    test_shortcuts_and_updates()
  File "/workspace/thesis_Bunker/conference/tests/test_steep_clearance.py", line 164, in test_shortcuts_and_updates
    mapper = PointCloudMapFine(z, samples_per_cell=1, terrain_source=terrain,
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspace/thesis_Bunker/conference/tapp/pointcloud_map_fine.py", line 98, in __init__
    super().__init__(*args, **kwargs)
  File "/workspace/thesis_Bunker/conference/tapp/pointcloud_map.py", line 118, in __init__
    raise ValueError('invalid sample history size')
ValueError: invalid sample history size

exit=1

~~~

~~~text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_common_eval
beach beach centre n=1 no_path=1
1 runs -> /tmp/tmp62864cna/output
synthetic: geometry, revision boundaries, stops, timing, gzip, omissions and overwrite protection passed
030 08OB87_-0706 C0 n=3 completed=3
030 08OB87_-0706 C1 n=3 completed=3
030 08OB87_-0706 C2 n=3 completed=3
030 08OB88_-0167 C0 n=3 no_path=3
030 08OB88_-0167 C1 n=3 no_path=3
030 08OB88_-0167 C2 n=3 rollover=3
030 08OB88_-1417 C0 n=3 no_path=3
030 08OB88_-1417 C1 n=3 completed=3
030 08OB88_-1417 C2 n=3 completed=3
030 08OB89_-0347 C0 n=3 no_path=3
030 08OB89_-0347 C1 n=3 no_path=3
030 08OB89_-0347 C2 n=3 partial=3
030 08OB89_-0847 C0 n=3 no_path=3
030 08OB89_-0847 C1 n=3 completed=1 stuck=2
030 08OB89_-0847 C2 n=3 completed=2 partial=1
45 runs -> /tmp/tmp62864cna/030
030 compared per-field counts: {'exit_code': 45, 'outcome': 45, 'status': 45, 'recorded_status': 45, 'goals_reached': 45, 'returned_to_start': 45, 'truth_lethal_len_m': 45, 'truth_lethal_entries': 45, 'debris_len_m': 45, 'debris_entries': 45, 'lethal_cells': 45, 'debris_cells': 45, 'rolled_over': 45, 'deviation_mean_m': 45, 'deviation_max_m': 45, 'n_plans': 45, 'failed_plans': 45, 'fail_goal_cell': 45, 'fail_start_cell': 45, 'fail_start_steep': 45, 'map_fp_cells': 43, 'map_fn_cells': 43, 'map_fp_steep_cells': 43, 'map_fp_obstacle_only_cells': 43, 'detector_fp_cells': 43, 'detector_fn_cells': 43, 'map_updates': 45, 'map_update_s_p95': 45, 'stops_unreachable': 15, 'relaxed_len_m': 15, 'relaxed_truth_lethal_len_m': 15, 'rollover_t_s': 3}
035 08OB86_-0205 S1 n=1 completed=1
035 08OB86_-0205 S2 n=1 other_error=1
035 08OB87_-0706 P1 n=3 completed=3
035 08OB88_-0167 P1 n=3 no_path=3
035 08OB88_-1417 P1 n=3 completed=3
035 08OB89_-0347 P1 n=3 no_path=3
035 08OB89_-0847 P1 n=3 completed=3
17 runs -> /tmp/tmp62864cna/035
035 compared per-field counts: {'exit_code': 17, 'outcome': 17, 'status': 17, 'n_plans': 16, 'n_replans': 16, 'failed_plans': 16, 'fail_goal_cell': 16, 'ev_off_path': 16, 'ev_unsafe_tilt': 16, 'ev_safety_replanned': 16, 'map_updates': 16, 'map_update_s_median': 16, 'map_update_s_p95': 16, 'map_update_s_max': 16, 'queue_drops': 16} plus 6 sensor rows
037 08OB86_-0205 L n=3 unknown=3
037 08OB86_-0205 LC n=3 unknown=3
037 08OB88_-0167 L n=3 unknown=3
037 08OB88_-0167 LC n=3 unknown=3
037 08OB88_-1417 L n=3 unknown=3
037 08OB88_-1417 LC n=3 unknown=3
037 08OB88_00332 L n=3 unknown=3
037 08OB88_00332 LC n=3 unknown=3
037 08OB89_-0847 L n=3 unknown=3
037 08OB89_-0847 LC n=3 unknown=3
30 runs -> /tmp/tmp62864cna/037
037 matched 30 metadata/exit records; absent raw outcome, geometry, events and updates stayed blank
all common evaluation tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_distance_clearance
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: default/centre/overlap/overlap_goal match the base on this host for maps, plans, manifests and ROS dispatch
2 PASS: hard mask matches centre and exact rectangle distance; quadratic band and endpoint limits
3 PASS: distance increases box clearance and all three forced corridors remain passable
4 PASS: cost-acceptable shortcuts cannot reduce the exact segment-to-box minimum
5 PASS: local queries omit distant tiles and incremental distance/cost match the full rebuild
08OB86_00294 completed
integration PASS: metadata, Docker/ROS options, Multi terrain/safety modes and recorded obstacle costs
all task060 distance clearance tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_edge_margin
sampling: all ten frozen default/zero-margin outputs byte-identical; 12-point draws meet 10m, 5m separation and reachability
sampling boundaries: inclusive margin, no start snapping, invalid margins and zero goals passed
cohort: independently recomputed the five changed beaches; all other metadata exactly equals task021; archived world-height bytes retained
synthetic start fixture: an insufficient start margin excludes the tour before sampling or planning, without moving it
report: 40 rows mix untouched cached rows with synthetic reruns; incomplete outcomes stay unknown; descriptive pairs, no energy/tests of significance
real adapter preparation: partial controls and both selected LiDAR cohorts accept exactly the same new metadata without ROS
dispatch fixtures: only changed eligible beaches reach the old runners; identical tour/world inputs, matched LiDAR conditions and no legacy finalizer
Docker fixture: normal read-only-source wrapper forwards fixed 0.3x/1s and refuses an existing manifest
all edge-margin tests passed (ROS2/Gazebo not required; fixture records are not experimental data)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_endpoint_component
component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected
component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed
legacy bytes: only two corrected start_steep labels differ in replay; all other fields and four preparation variants unchanged
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
saved component contract: both start_steep cases clear ZERO cells, protect all raw masks, retry once and advance to the next stop
all task028b component tests passed (Python only; Gazebo not run)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_endpoint_policy
1 PASS: default original runtime, path and CSV bytes unchanged
2 PASS: fixed 0.5m start escape; all three raw masks remain blocked
3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths
5b PASS: time-aligned actual-travel audit; ROS callback holds zero velocity and retains run log
6 replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'none': 'no_path', 'escape': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 PASS: three saved failures reproduced without changing fixed constants
Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_false_steep_causes
1 PASS: geometry, exact slope labels, box halo, point counts, missing stencil, relief, sea/nodata and view angles
2 PASS: committed final/first/failure data produce CSVs and a missing run is explicitly skipped
all task053 false-steep-cause tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_footprint
dilation: 0.5m circle, rocks not doubled, zero radius, immutable costs/endpoints and raster rounding passed
proximity: analytic line-circle lengths, overlapping unions and tangencies passed
requested LAS case: inflated planner reports no_path without moving endpoints
online: zero radius preserves exact task014 trajectory and planning count
rollover: strict +/-90deg threshold, first time/position and immutable fake records passed
statistics: two sizes averaged within beach, incomplete pairs excluded, one fixed Holm family passed (synthetic fixtures only)
Gazebo selection: six fixed scenarios, inflated-only selection and explicit infeasibility passed
comparison: unknown physical outcomes stay unknown; rollover pairs excluded; explicit executed denominator passed (fixtures only)
three-method reports: each contrast uses its own completion cohort; third-method failure does not drop old pairs (fixtures only)
all footprint and rollover tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_geo
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
zone VIII reference differences [latitude_deg, longitude_deg]:
-4.25145429972e-09 2.46816966865e-09
-4.06389943919e-09 -3.64556740351e-09
2.36028796508e-09 -3.05306002701e-10
2.78198797332e-10 -4.38916458734e-10
projection round-trip max error [m]: 7.10133463144e-09
geographic sidecars: 13 maps; source axes, coastline anchor, half-cell offset, round trips and NPZ hashes passed
Web APIs: geographic map conversions, unavailable-map response and unchanged legacy metadata/image passed
all geographic conversion tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_goal_region
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host pre-change versus none manifest, ROS dispatch, command and runtime log bytes
selection PASS: nearest feasible ring, strict visibility/steep filters, blocked start and cost tie
2 PASS: box halo unmodified; centre/overlap_goal/distance, v1/v2, plan snapshots and no reachable candidate
3 PASS: steep halo, restore before arrival, stale substitution rejected by the preserved safety handoff
08OB86_00294 completed
configuration PASS: manifest, ROS options, direct CLI, Docker forwarding and incompatible mode
all task063 goal-region tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_gpu_rendering
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
Docker PASS: implicit/explicit CPU argv and env byte-identical to 045 and 056 bases; GPU mounts read-only vendor, forces EGL selection, rejects missing file before Docker, preserves toolkit errors
08OB86_00294 completed
08OB86_00294 completed
manifest PASS: CPU preparation and final mocked dispatch byte parity; GPU records passed EGL vendor only
renderer/cloud PASS: 054 Mesa/llvmpipe, sample NVIDIA and partial contexts; earliest pre-motion common stamp and matched pose range statistics
summary PASS: valid renderer/RTF/GPU usage kept when a cloud pair is unavailable
08OB86_00294 completed
GPU checkpoint PASS: run folder and Ogre2 verdict remain in the manifest before normal teardown
partial summary PASS: 054 GPU manifest without run_folder, interrupted mission and signal exit keep CPU fields
all task045/056 GPU rendering tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_ground_estimate
1 PASS: implicit/explicit all_returns match pre-change update JSON, snapshots, histories, NPZ and multi-sensor sidecar bytes
2 PASS: 0.55m box creates false steep neighbours only with all_returns; box detection/inflation and all evidence unchanged
ground_estimate x y slope_deg steep box_lethal
all_returns 9 10 28.810793742973065 True True
all_returns 11 10 28.810793742973065 True True
all_returns 10 9 28.810793742973065 True True
all_returns 10 11 28.810793742973065 True True
non_obstacle 9 10 0.0 False True
non_obstacle 11 10 0.0 False True
non_obstacle 10 9 0.0 False True
non_obstacle 10 11 0.0 False True
3 PASS: all-excluded cells retain prior height and seen status; last-64 ALL returns displace older ground, then ground observations resume
4 PASS: sub-0.3m terrain changes retained; bilinear prior and the unchanged >=0.3m obstacle boundary used
5 PASS: LiDAR+two cameras share unchanged 2+1 detection evidence, source attribution and filtering; ground-only median removes false steep cells
configuration PASS: byte-identical default manifests; opt-in factory, CLI, ROS parameter and actual node constructor propagation; invalid/coarse combinations rejected
all ground-estimate tests passed; requirement 6 is verified by running every conference/tests module separately (Python only)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_ground_near_obstacle
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host old/implicit/explicit keep map, sensor, plan, ROS and manifest bytes
2 PASS: low box wall induces a false steep cell only in keep; same detections, halo and coverage
3 PASS: the true ramp remains steep and detection is identical for prior and local reference
4 PASS: zero returns preserves prior/previous height; 0.2m boundary; dirty history agrees with full rebuild
08OB86_00294 completed
integration PASS: Fine/Multi, manifest, ROS and Docker args, distance/no_inflate/pose trace/plan maps, prior height only
all task062 ground-near-obstacle tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_lab_geometry
1 PASS: flat terrain and physical 5/12/22/30deg planes match independent eight-neighbour formula; all six cost stages and uint8 truncation
2 PASS: <=3 valid neighbours and absent centres stay unknown; fourth valid neighbour enables cost
3 PASS: pinned Jazzy setCostmap integer conversion, 253/254 blockage and allowed unknown=253
4 PASS: no raw obstacle contact/corner cuts; blocked starts and disconnected goals rejected; independent Dijkstra optimum; one 0.35m square-distance inflation
5 PASS: task013 A*/TA*-S all non-energy path metrics and scenario identifiers match clean/debris, 100/200m; times independently remeasured
all lab-geometry tests passed; requirement 6 is checked by the full conference/tests suite

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_lidar_figures
T4: 18 rows
T5: 26 rows
T6: 18 rows
F8–F10, T4–T6, numbers_lidar.tex and sources.json: /tmp/tmptx21rwur/archive
archive PASS: all figures/tables, macros recalculated from source CSVs and exact input hashes
missing/044 PASS: remaining outputs and missing-input message; common schema extends the figures
output guard PASS: existing results, pillar-one output and paper paths rejected
050 PASS: completion and both T5 scopes are recalculated from the committed CSV
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/eval_ground_endpoint/runs.csv
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/eval_035/runs.csv
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/real_sensors_compare/runs.csv
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/rtf_compare/stage_b/common_eval/runs.csv
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/waypoint_feasibility/goal_cell.csv
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/terrain_from_prior/goals.csv
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/map_speed/timing.csv
Skipped missing results file: /tmp/tmptx21rwur/terrain/results/rtf_compare/stage_b/sensor_updates.csv
T4: 10 rows
T5: 15 rows
T6: 4 rows
F8–F10, T4–T6, numbers_lidar.tex and sources.json: /tmp/tmptx21rwur/terrain/out
057 PASS: missing input is reported and an added CSV updates F10, the tables and input hashes
legacy PASS: same-environment 030–044 tables, F9 statistics and all prior numeric macros match
all LiDAR figure tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_local_speed
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmpxbx0lade/ten
024 08OB86_00294 start=[52, 195] points=[[309, 113], [273, 232], [104, 176], [46, 121], [250, 270]] unchanged=False
024 08OB86_-0205 start=[49, 270] points=[[114, 102], [114, 214], [42, 179], [135, 255], [93, 197]] unchanged=True
024 08OB87_-0706 start=[50, 200] points=[[89, 197], [263, 259], [59, 119], [347, 145], [39, 236]] unchanged=False
024 08OB88_-1417 start=[70, 169] points=[[337, 140], [313, 165], [199, 151], [264, 194], [203, 229]] unchanged=True
024 08OB88_-0167 start=[38, 231] points=[[137, 294], [249, 150], [202, 281], [31, 208], [348, 149]] unchanged=True
024 08OB88_00332 start=[45, 228] points=[[142, 207], [38, 131], [203, 180], [136, 171], [70, 116]] unchanged=True
024 08OB88_01832 start=[36, 214] points=[[223, 254], [335, 247], [159, 229], [264, 180], [133, 240]] unchanged=False
024 08OB89_00152 start=[48, 341] points=[[296, 173], [183, 372], [207, 192], [328, 186], [193, 222]] unchanged=False
024 08OB89_-0347 start=[55, 326] points=[[294, 224], [164, 169], [213, 144], [195, 352], [264, 374]] unchanged=False
024 08OB89_-0847 start=[70, 146] points=[[269, 98], [75, 211], [227, 332], [281, 117], [350, 279]] unchanged=True
024 PASS: 10/10 archived waypoint lists, 5/5 unchanged scenarios, default manifest bytes and wrapper forwarding
032 slope=0 box=False shift=0: fine/coarse=(0, 0)
032 slope=0 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0: fine/coarse=(0, 0)
032 slope=0 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0: fine/coarse=(0, 0)
032 slope=20 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0: fine/coarse=(0, 0)
032 slope=20 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0.4: fine/coarse=(0, 0)
CPU AMD EPYC 9V45 96-Core Processor
fixture sensor input accepted repeats before_median_s before_p95_s after_median_s after_p95_s fine_diff coarse_diff
synthetic lidar 28800 28800 12 3.227050 4.776116 0.134375 0.214227 0 0
synthetic camera1 26750 26750 12 9.698393 11.790774 0.054701 0.078762 0 0
saved_b0b lidar 28800 11741 1 2.712802 2.712802 0.094586 0.094586 1 1
saved_b0b camera1 26750 9604 1 3.219625 3.219625 0.024349 0.024349 0 0
saved_b0b camera2 26750 9242 1 2.531616 2.531616 0.113923 0.113923 0 0
all local speed tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_map_speed
byte-identical replay against the pre-038 implementation: 88 update states; states differing from the hashes stored on the recording machine: 0

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_mapfiles_sim
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 lossless scenario round trips, float32+residual, NaN, all 23 files and all 17 legacy IDs passed
straight completed True max_deviation_m 3.552713678800501e-15 elapsed_s 19.700000000000003
right_angle completed True max_deviation_m 0.20226302369017546 elapsed_s 39.650000000000006
closed completed True max_deviation_m 0.3173559828528229 elapsed_s 68.35000000000001
controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed
tour map=flat_test_100m.npz elapsed_s=248.15 deviation_mean_m=0.006614475997696592 deviation_max_m=0.33848962758007467 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
tour map=beach_gentle_200m_100.npz elapsed_s=418.45000000000005 deviation_mean_m=0.01568040573287969 deviation_max_m=0.20112452978749665 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
gazebo flat_test_100m.npz pixels 257 size_m 100.0 max_error_m 0.0 boxes 3
gazebo real_08OB87_-0206_200m_0.npz pixels 2049 size_m 200.0 max_error_m 0.06374200885325632 boxes 0
API: 40 maps, file metadata/PNG, five-point planning/simulation, 404/422, immediate 409 and guard recovery passed
all mapfiles/simulation tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_mission
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 synthetic + 12 validation, cache, PNG dimensions/orientation passed
parity: 5-point terrain order/cost/path and Euclidean order/physical legs passed
validation: outside, water, blocked, unreachable, counts, rounding, duplicate/invalid base passed
safety: synthetic/beach_gentle/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_steep/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_scarp/200/100, 5 points, terrain/euclid contact=0
safety: real/08OB87_-0206/200, 5 points, terrain/euclid contact=0
safety: real/08OB88_01332/200, 5 points, terrain/euclid contact=0
API: maps/info/PNG/plan/static, 404/422, responsive worker, immediate 409 and guard recovery passed
all mission tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_obstacle_clearance
1 PASS: centre default/explicit, prior/local, fine/multi; maps match the pre-041 implementation on this machine (recorded hashes also match); manifest, ROS-mocked commands and existing none/v1/v2 files match baseline
2 mode min_path_clearance_m lethal_cells path_grid
centre 0.477533728 4 [(10, 15), (11, 7)]
overlap 1.123456796 12 [(10, 15), (12, 10), (12, 8), (11, 7)]
3 PASS: full recompute after 20 updates across prior/local and fine/multi, plus dense/sparse edge cases
3 planning PASS: inferred overlap halo blocks unseen cells in normal and diagnostic planner snapshots
4 B PASS: periodic observed data incl. empty map, exact trajectory-to-box distance, CSV parts and truth-mask fallback
4 C1-C3 PASS: missing plan_history, shared path_distance (300 decisions, 23 rounding cases), class default
4 C4 and routing PASS: env-selected 1.0 honoured, overlap manifest, ROS command and wrapper
4 ROS constructor PASS: v2 runtime, overlap mapper and diagnostics selected together
all task041 obstacle clearance tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_mission
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
beach_gentle: no-prior/coarse exact trajectory and plan-count parity; contact=0
beach_steep: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB88_01332: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206 stale five-point tour: online contact=0; fixed debris cells= 11
08OB88_01332 stale five-point tour: online contact=0; fixed debris cells= 18
08OB89_-1597 stale five-point tour: online contact=0; fixed debris cells= 6
async: worker blocked while simulation time advances, old path/positive commands continue; latest-pose replacement, one trajectory, plan/event logs and stale/cross-run rejection passed
follower adapter: legacy completion/telemetry unchanged; intermediate-leg CSV stays open; final completion and stationary watchdog terminate the run
maps/API: debris elevations, cost/lethal/obstacle/water/nodata match; coarse prior, legacy telemetry, live path/count validation and online=false default passed
all online-mission tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_safety
1 PASS: implicit/explicit none match pre-change runtime command JSON, plans/diagnostic bytes, follower trajectory/mission bytes and manifests
2 PASS: LiDAR and perfect-radius joins exempt only the start cell; later lethal cells remain rejected
3 PASS: actual stuck_0847_C1_r2_t1345 fixture search and handoff
online_fixes search_success handoff path_points outside_start_lethal_cells start_lethal
none True False 0 0 True
v1 True True 5 0 True
4 PASS: consecutive join rejection terminates at exactly 10 simulation seconds; acceptance resets the interval
5 PASS: known free-to-lethal on remaining path triggers lethal_changed only in v1; off-path changes do not replan; pending changes reset on planning
6 PASS: +/-26deg roll/pitch and 0.8m deviation stop; 24/25deg and 0.7/0.75m do not; zero linear and angular speed
safety recovery PASS: stop invalidates old work, replans from measured position, accepts replacement, ignores stale status and ends on no-path
ROS adapter PASS: real callbacks publish zero/status, preserve the open run, relay the stop and resume on a replanned path
diagnostics/concurrency PASS: v1 records diagnostics without 028b relaxation; busy pre-stop work cannot hand off and recovery uses the latest pose
configuration PASS: v1 manifest/CLI and both ROS parameter commands; 028b unchanged and excluded from v1
all online-safety tests passed; requirement 7 is checked by the complete conference/tests run

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_overlap_goal
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default, explicit centre and overlap bytes for Fine/Multi, none/v1/v2, manifest, ROS launch, paths, diagnostics and plan maps
2 PASS: overlap-only goal opens even if unseen; centre halo, prior rock and steep halo still block; Fine/Multi and sensor/prior/prior_veto
3 PASS: intermediate and former goals retain overlap, old start handoff rules apply, latest centre blockage triggers v1/v2 replanning
08OB86_00294 completed
4 PASS: manifest, ROS and mocked Docker forwarding, fine-only validation, both synthetic paths and 12 archived goals
all task052 overlap goal tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_path_tracking
1 PASS: before/current same-host manifest, ROS states, commands, trajectory, replan and stop bytes for none/v1/v2
2 PASS: straight speed, 2m corner window, 60-degree 0.5 m/s cap and strict 45-degree spin
3 PASS: 0.3 s rise/decay, 80% steady turn response, no-lag trace equals robot_sim
wiring PASS: opt-in initial/replacement paths with none/v1/v2, manifest, ROS args and Docker stub
all task043 tracking tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_plan_map_snapshots
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default manifest, missions, commands, plan CSV and diagnostic NPZ bytes; opt-in forwarding
Plan map recording stopped at 4.5 sim s: storage limit
2 PASS: exact search maps, signed-zero/delta cost, paths, prior_veto mask, handoff association and byte cap
approach: 1 rows
goal_cell: 1 rows
skipped: 0 rows
/tmp/tmp_aonkejx/absent [approach and goal_cell] skipped: no saved search maps; cannot inspect box detection or first goal block
3 PASS: interpolated closest approach uses the last handed-off plan; first blocked goal and missing-record handling
all task051 plan map snapshot tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_pointcloud_map
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis_Bunker/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_pointcloud_map_fine
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_pose_trace
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default manifest, run files, ROS arguments, commands, timeout boundary and control bytes for none/v1/v2
2 PASS: shared upstream, follower receipt, follower processing, missing data, stamp fallback and CPU evidence
Task058 preparation only; Gazebo not executed: /tmp/tmp7jg46yga/prepared
08OB86_00294 completed
3 PASS: CLI/manifest, ROS trace destinations, fake Docker, bounded CSV rollover and CPU sample
all task058 pose trace tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_prior_free
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
2-4 PASS: flat/20deg plane and 0.4m boxes, with exact and +/-0.4m shifted priors
slope_deg box prior_shift_m reference false_positive_cells missed_cells
0.0 False 0.0 prior 0 0
0.0 False 0.0 local 0 0
0.0 False -0.4 prior 81 0
0.0 False -0.4 local 0 0
0.0 False 0.4 prior 0 0
0.0 False 0.4 local 0 0
0.0 True 0.0 prior 0 0
0.0 True 0.0 local 0 0
0.0 True -0.4 prior 80 0
0.0 True -0.4 local 0 0
0.0 True 0.4 prior 0 1
0.0 True 0.4 local 0 0
20.0 False 0.0 prior 0 0
20.0 False 0.0 local 0 0
20.0 False -0.4 prior 81 0
20.0 False -0.4 local 0 0
20.0 False 0.4 prior 0 0
20.0 False 0.4 local 0 0
20.0 True 0.0 prior 0 0
20.0 True 0.0 local 0 0
20.0 True -0.4 prior 80 0
20.0 True -0.4 local 0 0
20.0 True 0.4 prior 0 1
20.0 True 0.4 local 0 0
local support PASS: fewer than 3/collinear minima remain unclassified; both real sensor modes fuse sensor-only evidence and attribution
5 PASS: true world box tops equal component maximum; lower edges/footprints/collision-visual sizes and truth NPZ unchanged
6 PASS: SeedSequence reproducibility, distinct patch seeds, preserved sea/nodata, flat none and immutable input arrays
configuration PASS: factory/CLI/manifest/ROS command forwarding; invalid coarse/local rejected; Gazebo not started
all prior-free tests passed; requirement 7 is checked by the separate complete test-module run

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_beach
all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed
all 60 patches satisfy sea-to-land orientation
08OB86_00294: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_-0205: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_-0706: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-1417: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-0167: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_00294: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB86_-0205: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_-0706: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-1417: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-0167: exact offline and coarse R5 c10 online safety passed, clean/debris
real-beach test groups failed: 0
all real-beach tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_beach_las
data: all 60 LAS patches, 12/48 split, exact names/order/origin/axes, npts and sea-to-land orientation passed
quantized_0.1m_fraction: new_max 0.0035301084084904803 old_min 0.27882342564826246
defaults: implicit/explicit shizuoka_beach are bit-identical for the first 3 test patches
08OB86_00294: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_-0205: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB87_-0706: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-1417: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-0167: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_00294: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB86_-0205: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB87_-0706: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-1417: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-0167: exact offline and coarse R5 c10 safety, clean/debris contact=0
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_sensors
PASS legacy model SDF (with/without LiDAR) and fine-map NPZ SHA256 match pre-change bytes
PASS real preset mounts, symmetry, unchanged LiDAR spec and camera FOV/ranges without intrinsics
A2 camera1: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
A2 camera2: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
PASS A2: three camera-free SDFs byte-identical; depth SDF/spec change only prescribed resolution and intrinsics
PASS arbitrary sensor/model roll-pitch-yaw and translation match independent homogeneous transform
PASS both outward cameras: ground/box registration, shared 2+1 evidence, one inflation and saved provenance
PASS synthetic camera boxes in LiDAR blind zone at 1.5/2/3m; residual 1m blind zone disclosed
PASS per-sensor range/FOV/finite filtering and byte-identical task023 fusion/inflation for registered input
PASS manifest records all real specs/mounts; explicit fine selection; Docker wrapper forwards sensor flags
PASS A2 wrapper: unset flags preserve full legacy argv bytes; individual/both/empty supplied values forwarded (fake Docker only)
PASS analytic 4.105m LiDAR near bound, discrete-beam gap, rear blind zone and camera symmetry
PASS actual ROS adapter: bounded queues, fair sources, stamped transforms, logs and freshness (transport mocked)
all real sensor tests passed (synthetic/geometry only; Gazebo not run)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_review_fixes
1 PASS: none/v1 commands, ROS follower state and log bytes unchanged; full manifest hashes 8/8
A1 v1 second tilt after 9s: replanned
A1 v2 second tilt after 9s: terminal unsafe_tilt
A1 v2 second tilt after 10s: terminal unsafe_tilt
A1 v2 second tilt after 10.1s: replanned
A2 v1 duplicate segment, 0.8m: running
A2 v2 duplicate segment, 0.8m: off_path
A3 v1 near passed segment and 0.8m from remaining route: running
A3 v2 near passed segment and 0.8m from remaining route: off_path
B6 PASS: the box is detected with support 0.70m from its centre
B9 PASS: dense/cKDTree agree on 298 heights, including unknown support
B8 5f36770 local_ground_032.py SHA-256 5a57c07f09d31e0fcf7508de6ddc28e05253cca13939eeda767ffca2ef7491f5
B8 5f36770 pointcloud_map_multi_032.py SHA-256 710d81185c5a945e9c89d1d679414c6846832f779edbc6a9e9065823ba67dc96
v2 configuration PASS: manifest, CLI, both ROS parameters and async factory
B10 PASS: fine world input NPZ, world SDF and heightmap match byte for byte; coarse matching remains explicit
Task036 task023 aggregation skipped: the waypoint cohort differs from the cached task022 controls. Manifest and available raw results: /tmp/tmp5htj24yj/edge
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmp5htj24yj/coarse
Task036 task023 aggregation skipped: opt-in conditions require separate evaluation from task023. Manifest and available raw results: /tmp/tmp5htj24yj/opt-in
B11 PASS: standard aggregation selected only for a comparable fine cohort
B7 controlled scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 0
6 0 0 0
7 0 0 0
8 0 0 0
9 0 0 0
10 0 0 0
11 0 0 0
B7 review scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 2
6 2 2 1
7 4 2 0
8 8 2 0
9 10 3 5
10 13 3 0
11 11 2 0
all task040 review-fix tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_ros2_gz
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
model: 150kg box inertia, 0.699m spacing, 4 wheels/side, DiffDrive joints, IMU, world pose and opt-in external visual passed
packages: ament_python metadata, resource markers, node entry points, launch/bridge configuration and Python syntax passed
follower: bit-identical kinematic trajectory, completion, stationary watchdog and CSV fields passed
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 34.2 0.02959598405434589 0.3173397734180379 0
kinematic True 34.2 0.02959598405434589 0.3173397734180379 0
attitude actual_p95_deg map_p95_deg
roll 0.0 0.0
pitch 0.0 0.0
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 7.7 0.0 0.0 0
kinematic True 7.7 0.0 0.0 0
attitude actual_p95_deg map_p95_deg
roll 0.0 11.309932474020224
pitch 0.0 5.710593137499648
report: synthetic robot_sim CSV deviation/contact/time parity, kinematic comparison and plots passed (not Gazebo measurements)
API: send/fetch/id/204, telemetry/freshness, invalid map/path 422 and bridge map rejection passed
worlds: original PNG hashes/obstacle XML preserved, effective terrain transforms unchanged, sensors and IMU added
all ROS-free ROS2/Gazebo tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_rtf_option
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
default 0.3 PASS: omitted/explicit match, manifest and report match pre-change hashes (full manifest)
1.0 PASS: historical overlay manifest settings and world target match; stale=1.0, step=0.001, LiDAR=10Hz
validation PASS: explicit 0.3 overrides environment; legacy rtf_check still works; invalid factor, stale and coarse rejected
wrapper PASS: split and equals options forward unchanged, with identical Docker setup
run finalization PASS: explicit 1.0 preserves manifest and skips incompatible task023 summary
all task039 RTF option tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_stale_prior_risk
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: sensor and prior NPZ, snapshot, multi-sensor sidecar and mocked runner bytes match same-host base
2 PASS: cutoff at 32 of 63/64; unchanged height crossing triggers veto, 0.5m halo, subsequent clearing
3 PASS: unchanged real prior slopes in all three modes; both prior modes also forbid unobserved steep cells
08OB86_00294 completed
configuration PASS: manifest, ROS argument, planner CLI, Multi local/overlap, fine-only validation and fake Docker
all task048 stale-prior-risk tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: identical same-host Fine/Multi, map, manifest, mission, diagnostics and runtime bytes for centre
2 PASS: unchanged hard stencil, exact square distances and quadratic soft costs add to obstacle costs
3 PASS: route moves farther from slopes and all three forced gaps remain reachable
4 PASS: no clearance-reducing shortcuts; local add/remove and all terrain sources match rebuild
08OB86_00294 completed
integration PASS: CLI, manifest, ROS and fake Docker, Multi and both saved soft layers
all task065 steep clearance tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_near_obstacle
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host implicit and explicit keep, Fine/Multi, all terrain sources, manifests, ROS args and plan logs
2 PASS: covered slope stays lethal, external slope keeps inflation, obstacle/height/cost bytes agree
3 PASS: obstacle-only local update and later height changes match full rebuild for Fine/Multi and all clearances
prior/veto PASS: prior seeds and rocks kept, former inferred halo refreshed, overlap_goal and plan maps work with none/v1/v2
08OB86_00294 completed
CLI PASS: fine-only opt-in, manifest, ROS args and fake Docker forwarding
all task055 steep-near-obstacle tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_terrain_from_prior
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host before/after NPZ, update results, multi-sensor sidecars, snapshots and none/v1/v2 dispatch bytes
2 PASS: apparent steepness blocks the goal only with sensor terrain, with the same sensor elevation and box evidence
3 PASS: Fine/Multi × prior/local with overlap retains box and unobserved true steep hazards; v1/v2 tilt stop intact
08OB86_00294 completed
configuration PASS: manifest, production command, direct planner CLI, real-sensor factory and fake Docker
4 PASS: all 35 failures classified; 9/14 recovered on final maps, 3/6 on failure snapshots, 15 without either
all task047 terrain-source tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_thesis_figures

T1
 debris    metric  n    A_median   TAS_median  delta_median              p         p_holm
  False mean_cost 48 0.110342949 0.0767774554 -0.0352167333 7.10542736e-15 5.68434189e-14
  False     climb 48  1.50126915  0.890802236  -0.410943017 7.10542736e-15 5.68434189e-14
  False  p95_roll 48  5.45746622     3.567633   -1.89097743 7.10542736e-15 5.68434189e-14
  False length_xy 48         NaN          NaN   -2.00026809   0.0276182014   0.0552364028
   True mean_cost 48 0.154226921 0.0855587032 -0.0582350381 7.10542736e-15 5.68434189e-14
   True     climb 48  2.07159806   1.30575231  -0.803948405 2.13162821e-14 6.39488462e-14
   True  p95_roll 48  6.86720155   3.63401103   -2.80093993 7.10542736e-15 5.68434189e-14
   True length_xy 48         NaN          NaN  -0.764154874    0.947340222    0.947340222

T2
 radius_m   mode  runs  completed  touching   dJ_median     dJ_p90  replans_median  plan_s_median  plan_s_p95  plan_s_max
        5  fixed    48         48        46   3.8297614 10.8951737               0   0.0943159025 0.513914058  1.09228056
        5 online    48         46         0   1.9542052 10.2738521             101   0.0464642375  0.28593965  1.26618145
       10  fixed    48         48        46   3.8297614 10.8951737               0   0.0960627685 0.506711613  1.25659096
       10 online    48         46         0 0.945069248  6.6029207            94.5   0.0510014495 0.292423272  1.32438343
       15  fixed    48         48        46   3.8297614 10.8951737               0    0.094235528 0.485409814  1.26557115
       15 online    48         47         0 0.688622405 5.29694595              85    0.057362561 0.305458798  1.76405173

T3
                                world         mode  completed  path_lethal_cells  elapsed_s  roll_p95_actual_deg  pitch_p95_actual_deg  roll_p95_map_deg  pitch_p95_map_deg
              file/flat_test_100m.npz offline tour       True                  0    249.412       8.05631294e-09        6.79662109e-10                 0                  0
    file/real_08OB87_-0206_200m_0.npz offline tour       True                  0      348.2           4.76005563            6.20167607        4.58473933         6.31735413
file/real_las_08OB87_-0206_200m_0.npz offline tour       True                  0    289.516           3.83941424            2.47900287        3.84957483         2.58651471
       real_las_08OB87_-0206 / debris        fixed      False                  0      96.15           4.54713144            5.69114628        5.33797683         6.55378208
       real_las_08OB87_-0206 / debris       online       True                  0     190.95           4.31378469            4.21973305        4.30333238         3.67841423
thesis: F1-F7 PDF/PNG, T1-T3 LaTeX/Markdown and numbers.tex generated
statistics: 48 paired beaches, size means, medians and archived contact counts verified
outputs: no excluded measurement columns or values; all thesis figure tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_tracking_error
1 PASS: full-path distance, Menger curvature, slope, motion direction and command bins
2 PASS: pre-path samples, same-time revisions, causal switches and task042 percentile parity
approaches PASS: interpolated strict clearance and same-box attribution
3 PASS: committed archive tables, explicit skipped input and published event-evidence coverage
all task061 tracking-error tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_waypoint_feasibility
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
geometry PASS: statuses, 1 m boundary, closest A* cell/tie, no-corner-cut, off-grid and invalid start
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
none PASS: three same-environment manifests, and command/mission bytes at a mocked live dispatch
08OB86_00294 completed
substitute PASS: replanned closed tour, skips and stable order in manifest and published command
Task046 preparation only; Gazebo not executed: /tmp/tmp25opgmdg/cli
CLI/wrapper/API PASS: prepare-only, 028b conflict, forwarding and read-only preview
all waypoint feasibility tests passed

exit=0
~~~
