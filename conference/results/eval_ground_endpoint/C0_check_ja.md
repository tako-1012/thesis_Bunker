# C0（`--diagnostics` あり）のふるまいの確認（コードを読んだ結果、走らせる前）
コミット `14bcae7`（`origin/realtime-map`）。

**結論：C0 も、経路の失敗 1 回で走行が終わる。今までと同じ。**

1. `make_lidar_runtime`（`ros2_jazzy/gz_checks/endpoint_runtime.py`）は、`endpoint_policy='none'` かつ `diagnostics=False` のときだけ、今までの `LidarOnlineMission` を返す。
   `--diagnostics` を付けた C0 は `EndpointRuntime` になる。そのため、次の 2〜5 で中身を確かめた。
2. `EndpointRuntime._plan_work`：方針が `none` なら、計画器を `EndpointPlanner` にしたうえで `LidarOnlineMission._plan_work` をそのまま呼ぶ。
   待って計画し直す処理（`RetryState`・`hold`）と次の地点へ移る処理（`_advance`）は、方針が `none` 以外のときだけ動く。
3. `EndpointPlanner._plan`：方針が `none` なら `OnlinePlanner._plan` の結果をそのまま返す。
   `diagnostics` は、失敗の型（`failure_class`）を記録し、失敗の瞬間の地図を `diag/plan_fail_*.npz` に保存するだけ。
4. 終わり方：`AsyncOnlineMission.tick`（`thesis_bunker_mission/online_runtime.py`）は、計画の結果が `success=False` なら `finished=True` にし、`online_error` を出す。
   追従側（`path_follower.py`）はこれを受けて `no_path` で止まる。`EndpointRuntime.tick` は方針が `none` のとき、`plan_history` から `failure_class` を取り除くだけで、この流れを変えない。
5. `_join`（計画を今の位置につなぐ処理）も、方針が `none` なら今までの `LidarOnlineMission._join` を呼ぶ。

### 今までとの違い（終わり方には関係しない）
- 地図を読むとき、`mapper.snapshot()` ではなく `capture()` を使う。`seen`・`cost`・`lethal` は同じ配列で、取るロックが 1 つ多いだけ。
  あわせて計画用の地図の複製と、10 秒ごとの地図の保存（新しい 3 つを残す）をするため、計算の負担が少し増える。
- `plans.csv` に `failure_class` の列が増える。
- テスト `test_endpoint_policy` の 1・5 番が、既定の型の一致と、診断ありの失敗の記録を確かめている。
