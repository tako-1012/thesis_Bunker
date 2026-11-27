# 共通走行集計の定義

CSV の空欄は欠測または適用外。runs.csv の missing_reasons に列別の理由を JSON で記録する。0 は、対応する記録で件数や長さがゼロと確認できた場合。分位値は NumPy の線形補間。

## runs.csv

| 列 | 定義 |
|---|---|
| `run` | 記録ディレクトリ。作業ディレクトリ内は相対パス。 |
| `experiment` | 実験名。--experiment または入力ディレクトリ名。 |
| `patch` | 砂浜。走行メタデータ、raw の直下のフォルダ名の順。 |
| `condition` | 条件。対応表、run_conditions、<条件>_r<反復番号>、manifest の設定の順。 |
| `rep` | 反復番号。run_conditions またはフォルダ名。 |
| `exit_code` | exit.txt のプロセス終了コード。0 から完走は推定しない。 |
| `target_rtf` | 目標倍率。manifest または run_conditions。 |
| `recorded_status` | mission.json の status（なければ manifest の termination）。 |
| `status` | 転倒、壁時計打ち切り、v2 の傾き反復、合流拒否、地点不足を反映した終了状態。 |
| `outcome` | status に加えて、028b で近くまで・回れない地点が残った完走を partial に分類した結果。 |
| `completed` | outcome が completed なら true。 |
| `data_source` | mission.json の data_source。 |
| `goals_reached` | 順に指定された最初の5地点のうち、中心軌跡が半径0.3 mの円に入った地点の数。 |
| `returned_to_start` | 最後の中心位置と指定の出発点の距離が0.3 m以下。 |
| `elapsed_s` | 走行時間（sim s）。mission の時刻を優先し、欠けた端点は軌跡で補う。 |
| `sim_to_wall_ratio` | mission の開始・終了の sim 時刻差 ÷ wall_elapsed_s。軌跡からは補わない。 |
| `record_error` | 軌跡の読み取りまたは検証エラー。 |
| `online_error` | mission または manifest のエラー文字列（空は明示的なエラーなし、欠落は欠測）。 |
| `no_path_type` | 結果が no_path のときの最後の失敗計画の型。空の型は欠測、既知4分類外は other。 |
| `board_outcome` | ボード集計で用いる分類。wall_timeout は静止が記録された場合に stuck とする。 |
| `sim_end_t` | 軌跡の最後の時刻（sim s）。 |
| `stationary_tail_s` | 最後の位置から5 cm超離れた最後の標本の次から終了まで（sim s）。 |
| `rolled_over` | 軌跡の roll の絶対値が90°を超えた標本がある。 |
| `rollover_t_s` | 最初の転倒標本の時刻（sim s）。 |
| `rollover_elapsed_s` | 軌跡の先頭から転倒標本まで（sim s）。 |
| `rollover_x_m` | 最初の転倒標本の x（m）。 |
| `rollover_y_m` | 最初の転倒標本の y（m）。 |
| `roll_p95_deg` | 軌跡の |roll| の p95（度）。 |
| `roll_max_deg` | 軌跡の |roll| の max（度）。 |
| `pitch_p95_deg` | 軌跡の |pitch| の p95（度）。 |
| `pitch_max_deg` | 軌跡の |pitch| の max（度）。 |
| `truth_reference` | 照合した評価用NPZのパス。 |
| `lethal_cells` | 中心軌跡の線分が交差した真値通行不可のユニーク粗格子数。 |
| `debris_cells` | 中心軌跡の線分が交差した漂着物のユニーク粗格子数。 |
| `out_of_bounds_samples` | 中心座標が粗格子の中心の範囲外にある軌跡標本数。 |
| `truth_lethal_len_m` | 真値通行不可マス内の中心軌跡の線分長（m）。 |
| `truth_lethal_entries` | 真値通行不可マスへの標本ベースの連続進入回数。開始時に内側なら1回。 |
| `debris_len_m` | 漂着物マス内の中心軌跡の線分長（m）。 |
| `debris_entries` | 漂着物マスへの標本ベースの連続進入回数。開始時に内側なら1回。 |
| `truth_footprints` | debris_footprints.csv に記録された衝突箱の数。 |
| `min_truth_clearance_m` | 中心軌跡の全線分と実際の閉じた衝突箱のXY投影との最短距離（m）。箱0個の場合は空欄。 |
| `truth_below_radius_s` | 真値箱までの中心の距離が厳密に0.5 m未満の時間（sim s、線形補間、重複区間は一度）。 |
| `truth_below_radius_entries` | 真値箱までの中心の距離が厳密に0.5 m未満の連続区間の数。 |
| `min_observed_clearance_m` | clearance.csv にある細粒度検出障害物への距離の最小標本値（m）。 |
| `deviation_mean_m` | 有効な経路がある軌跡標本の偏差の平均（m）。 |
| `deviation_max_m` | 有効な経路がある軌跡標本の偏差の最大（m）。 |
| `deviation_p95_m` | 有効な経路がある軌跡標本の偏差の95%値（m）。 |
| `deviation_samples` | 対応する経路のあった軌跡標本数。 |
| `deviation_over_075_samples` | 偏差が0.75 mを超えた標本数。 |
| `deviation_max_t_s` | 最大偏差の最初の標本時刻（sim s）。 |
| `deviation_max_x_m` | 最大偏差の標本の x（m）。 |
| `deviation_max_y_m` | 最大偏差の標本の y（m）。 |
| `deviation_max_path_t_s` | 最大偏差の標本に対応する経路版の時刻（sim s）。 |
| `deviation_max_curvature_inv_m` | 最近線分の端点にある内点のうち、射影点に最も近い頂点とその前後の3点で求めた符号なし Menger 曲率（1/m）。内点がないか退化した場合は空欄。 |
| `n_plans` | plans.csv の計画呼び出し数。 |
| `n_replans` | plans.csv の reason が start_leg 以外の呼び出し数。 |
| `replans_lethal_changed` | plans.csv の lethal_changed 呼び出し数。 |
| `failed_plans` | plans.csv の success=False の数。 |
| `last_failure_class` | plans.csv の最後の失敗呼び出しの failure_class。 |
| `fail_goal_cell` | plans.csv の失敗呼び出しのうち、型が goal_cell の件数。 |
| `fail_start_cell` | plans.csv の失敗呼び出しのうち、型が start_cell の件数。 |
| `fail_start_steep` | plans.csv の失敗呼び出しのうち、型が start_steep の件数。 |
| `fail_corridor` | plans.csv の失敗呼び出しのうち、型が corridor の件数。 |
| `fail_other` | plans.csv の失敗呼び出しのうち、型が other の件数。 |
| `fail_unclassified` | plans.csv の失敗呼び出しのうち、型が unclassified の件数。 |
| `plan_s_median` | plans.csv の全呼び出しの実時間 median（s）。 |
| `plan_s_p95` | plans.csv の全呼び出しの実時間 p95（s）。 |
| `plan_s_max` | plans.csv の全呼び出しの実時間 max（s）。 |
| `calls_over_1s` | 1秒（実時間）を超えた計画呼び出し数。 |
| `plan_fail_snapshots` | diag の plan_fail_*.npz の数。 |
| `ev_join_accepted` | safety_events.csv の join_accepted の出現回数。 |
| `ev_join_rejected` | safety_events.csv の join_rejected の出現回数。 |
| `ev_join_rejected_timeout` | safety_events.csv の join_rejected_timeout の出現回数。 |
| `ev_unsafe_tilt` | safety_events.csv の unsafe_tilt の出現回数。 |
| `ev_off_path` | safety_events.csv の off_path の出現回数。 |
| `ev_safety_replanned` | safety_events.csv の safety_replanned の出現回数。 |
| `ev_unsafe_tilt_repeat` | safety_events.csv の unsafe_tilt_repeat の出現回数。 |
| `join_accepted_with_blocked` | 合流受理ログの blocked_cells が空でない件数。 |
| `stops_replanned_30s` | off_path・unsafe_tilt の停止から30 sim s以内に safety_replanned があった停止数。 |
| `stops_replanned_and_moved_30s` | 同じ30 sim sの窓で再計画後の標本が停止位置から1 m超離れた停止数。 |
| `stops_detail` | 停止ごとの時刻・型・30秒以内の再計画と最大移動・終了までの最大移動のJSON。035と同じ丸め。 |
| `stops_then_moved` | 035と同じく、終了までの丸め後の最大移動が1 mを超えた停止数。 |
| `stops_then_stationary` | 035と同じく、終了までの丸め後の最大移動が1 m以下の停止数。 |
| `snapshots` | diag_all の周期保存で、有効な経路版が存在した地図の数。 |
| `snap_handoff_n` | 上記のうち、経路引き渡し後1 sim s以内だった数。 |
| `snap_handoff_with_lethal` | 引き渡し後1 sim s以内で、残経路が地図の通行不可マス（車体中心のマスを除く）と交差した数。 |
| `snap_any_with_lethal` | 残経路が地図の通行不可マス（車体中心のマスを除く）と交差した地図の数。 |
| `stops_arrived` | endpoint_status.json の arrived の地点数。帰着分を含む。 |
| `stops_nearby` | endpoint_status.json の nearby の地点数。帰着分を含む。 |
| `stops_unreachable` | endpoint_status.json の unreachable の地点数。帰着分を含む。 |
| `retries` | endpoint_status.json に記録された retries。 |
| `start_applications` | endpoint_status.json に記録された start_applications。 |
| `goal_applications` | endpoint_status.json に記録された goal_applications。 |
| `relaxed_cells` | endpoint_status.json に記録された relaxed_cells。 |
| `relaxed_len_m` | endpoint_trajectory.csv と endpoint_masks の有効時刻を合わせた、許可マス内の中心軌跡長（m）。 |
| `relaxed_truth_lethal_len_m` | 許可マス内の中心軌跡長のうち、真値通行不可マスの長さ（m）。 |
| `relaxed_applied_plans` | endpoint_masks で applied が true の数。 |
| `map_source` | 最終 pointcloud_map.npz、なければ diag の最新周期保存。 |
| `map_seen_cells` | 保存地図で観測したセル数。 |
| `map_lethal_cells` | 観測済みで推定が通行不可のセル数。 |
| `truth_lethal_cells` | 観測済みで真値が通行不可のセル数。 |
| `map_fp_cells` | 023の誤って通行不可。観測済みで推定は不可、真値は可。 |
| `map_fn_cells` | 023の見落とし。観測済みで推定は可、真値は不可。 |
| `map_fp_steep_cells` | 誤って通行不可のうち、推定標高の急斜面の0.5 m膨張内のセル数。 |
| `map_fp_obstacle_only_cells` | 誤って通行不可のうち、推定急斜面の膨張外のセル数。 |
| `map_fp_box_adjacent_cells` | 誤って通行不可のうち、真値の漂着物箱の4近傍の数。 |
| `clearance_fp_cells` | 真値不可に真値急斜面の0.5 m膨張を足した場合の観測済み偽陽性。 |
| `clearance_fn_cells` | 真値不可に真値急斜面の0.5 m膨張を足した場合の観測済み偽陰性。 |
| `detected_obstacle_cells` | 観測済みかつ水・欠測域外の推定検出セル数。 |
| `truth_obstacle_cells` | 観測済みかつ水・欠測域外の真値漂着物セル数。 |
| `detector_fp_cells` | 観測済みかつ水・欠測域外で、真値漂着物のない検出セル数。 |
| `detector_fn_cells` | 観測済みかつ水・欠測域外で、検出しなかった真値漂着物セル数。 |
| `detector_fp_box_adjacent_cells` | 上記の検出偽陽性のうち真値箱の4近傍。 |
| `detector_on_unusable_cells` | 観測済みで水・欠測域内の検出セル数。 |
| `height_abs_error_median_m` | 最終保存地図の観測済みセルの絶対標高誤差の median（m）。 |
| `height_abs_error_p95_m` | 最終保存地図の観測済みセルの絶対標高誤差の p95（m）。 |
| `queue_drops` | sensor_status.json の全センサー累積キュー落ち数。なければ mission.perception。 |
| `sensor_error` | sensor_status.json または mission.perception のエラー。 |
| `cloud_age_sim_max_s` | probe.csv の点群の古さの最大（sim s）。 |
| `cmd_vel_hz_sim` | probe.csv の running 区間の cmd_count 合計 ÷ sim 時間差（Hz）。最初の標本の区間は除く。 |
| `probe_rtf` | probe.csv の running の最初と最後の sim 時間差 ÷ wall 時間差。 |
| `map_updates` | map_updates.csv の status=ok の数。 |
| `map_failed_updates` | map_updates.csv の status が ok 以外の数。 |
| `map_update_s_median` | map_updates.csv の status=ok の更新処理時間の median（実時間 s）。 |
| `map_update_s_p95` | map_updates.csv の status=ok の更新処理時間の p95（実時間 s）。 |
| `map_update_s_max` | map_updates.csv の status=ok の更新処理時間の max（実時間 s）。 |
| `update_over_period_count` | ミッションの開始から終了までに受信した点群の成功更新で、処理時間が0.1 sim s ÷ 実測倍率の実時間周期を超えた件数。 |
| `update_over_period_share` | 実測周期を超えた件数 ÷ 同じミッション区間の有効な成功更新数（0–1）。 |
| `lidar_map_updates` | map_updates.csv の status=ok の数。 |
| `lidar_map_failed_updates` | map_updates.csv の status が ok 以外の数。 |
| `lidar_map_update_s_median` | map_updates.csv の status=ok の更新処理時間の median（実時間 s）。 |
| `lidar_map_update_s_p95` | map_updates.csv の status=ok の更新処理時間の p95（実時間 s）。 |
| `lidar_map_update_s_max` | map_updates.csv の status=ok の更新処理時間の max（実時間 s）。 |
| `lidar_update_over_period_count` | ミッションの開始から終了までに受信した点群の成功更新で、処理時間が0.1 sim s ÷ 実測倍率の実時間周期を超えた件数。 |
| `lidar_update_over_period_share` | 実測周期を超えた件数 ÷ 同じミッション区間の有効な成功更新数（0–1）。 |
| `lidar_queue_drops_last` | センサーの更新ログの最後の累積キュー落ち数。 |
| `lidar_updates_over_target_period` | 成功更新時間が0.1 sim s ÷ 目標倍率を超えた件数（035互換）。 |
| `camera1_map_updates` | map_updates.csv の status=ok の数。 |
| `camera1_map_failed_updates` | map_updates.csv の status が ok 以外の数。 |
| `camera1_map_update_s_median` | map_updates.csv の status=ok の更新処理時間の median（実時間 s）。 |
| `camera1_map_update_s_p95` | map_updates.csv の status=ok の更新処理時間の p95（実時間 s）。 |
| `camera1_map_update_s_max` | map_updates.csv の status=ok の更新処理時間の max（実時間 s）。 |
| `camera1_update_over_period_count` | ミッションの開始から終了までに受信した点群の成功更新で、処理時間が0.1 sim s ÷ 実測倍率の実時間周期を超えた件数。 |
| `camera1_update_over_period_share` | 実測周期を超えた件数 ÷ 同じミッション区間の有効な成功更新数（0–1）。 |
| `camera1_queue_drops_last` | センサーの更新ログの最後の累積キュー落ち数。 |
| `camera1_updates_over_target_period` | 成功更新時間が0.1 sim s ÷ 目標倍率を超えた件数（035互換）。 |
| `camera2_map_updates` | map_updates.csv の status=ok の数。 |
| `camera2_map_failed_updates` | map_updates.csv の status が ok 以外の数。 |
| `camera2_map_update_s_median` | map_updates.csv の status=ok の更新処理時間の median（実時間 s）。 |
| `camera2_map_update_s_p95` | map_updates.csv の status=ok の更新処理時間の p95（実時間 s）。 |
| `camera2_map_update_s_max` | map_updates.csv の status=ok の更新処理時間の max（実時間 s）。 |
| `camera2_update_over_period_count` | ミッションの開始から終了までに受信した点群の成功更新で、処理時間が0.1 sim s ÷ 実測倍率の実時間周期を超えた件数。 |
| `camera2_update_over_period_share` | 実測周期を超えた件数 ÷ 同じミッション区間の有効な成功更新数（0–1）。 |
| `camera2_queue_drops_last` | センサーの更新ログの最後の累積キュー落ち数。 |
| `camera2_updates_over_target_period` | 成功更新時間が0.1 sim s ÷ 目標倍率を超えた件数（035互換）。 |
| `missing_reasons` | 空欄の理由の JSON。@ で始まるキーは JSON ファイル単位のエラー。 |

偏差は、時刻が標本以下の最新 path_revisions の折れ線全体への最短距離。版の切替時刻が同じ場合は最後の版を使用する。往復や経路の交差では、残経路を測る追従器内部の偏差と異なりうる。035・037 の runs.csv の最大・平均と同じ定義。
曲率は最近線分につながる局所の3点から求め、符号は付けない。等距離はログ順、線分順、頂点順を優先する。
停止位置は停止時刻以降の最初の姿勢標本。停止通知は safety_events の実測を数え、0.75 m の標本超過数からは推定しない。

真値の粗格子では030・035と同じく truth_rock & ~prior_rock を漂着物マスとする。ユニーク数には線分と閉じた格子の交差を数える。進入回数は粗格子に丸めた標本の連続区間を数えるため、標本の間だけを横切ると長さが正でも回数が0になる。037の個別接触分析では丸めと範囲外の扱いが異なる。
真値箱の時間と回数には、0.5 m の開いた近傍と区分線形の中心軌跡との交差を使う。車体接触を物理的に測った値ではない。箱CSVがない場合、粗格子で代用せず箱の列を空欄にする。

検出地図までの距離は、その時点のマスを使った診断標本の最小値。真値箱との連続軌跡の最小値とは集計方法が異なる。
センサー列がない更新ログは旧式の単一 LiDAR として扱う。センサー列がある場合、行がないセンサーの列は空欄。実測倍率による周期超過と、035 の目標倍率による超過は別の列。
生ログに軌跡がない完走は、mission の記録済み状態を集計する。到達地点数・帰着・転倒の軌跡による再検証は空欄。
壁時計打ち切りは、停止時間が記録上の stall_timeout_s（従来の既定10 sim s）以上のとき、ボード上で「止まったまま」。runs.csv の outcome には旧集計と同じ wall_timeout が残る。
観測地図は記録の評価用真値と比較する。検出誤りの内訳は LAS の元地形から再現した真値障害物マスクの膨張が保存真値と一致する場合のみ算出する。--reference-root は同じ走行真値を別に保存した場合にだけ指定する。

## summary.csv

`experiment,patch,condition` ごとの `n` とボード分類の件数。`other_error` は既知のその他終了、`unknown` は結果が判定できない走行。数値列の `_count` は有効値の数、`_min/_median/_max` は有効値の最小・中央値・最大。真偽値は真を1、偽を0として要約する。有効値がない統計は空欄。

## outcomes_board.csv

実験・砂浜・条件と、完走・一部・経路なし・止まったまま・転倒の各件数。その他・未確定の走行数は summary.csv で確認できる。
同一群で結果が一件も分からないときは5つの件数を空欄とする。
