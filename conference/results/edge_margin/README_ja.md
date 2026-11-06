# 指示書024：端から10m以上の地点で4方式を比較する

`edge_margin_checks.py` は、021〜023の10か所を保持し、地点が変わった砂浜だけを走らせ直す。
地点の選択で変えるのは、候補の端からの距離を10m以上にする条件だけ。
同じ `SeedSequence([0,3000,200,patch_index])` で12点を選び、最初の5点を使う。
距離・到達可能性・巡回順・TA*-Sと膨張0.5mは従来どおり。スタートを移動しない。

## 距離と再利用

距離はセル中心の座標の端 `0..(shape-1)*0.5m` を基準とする。400×400では0〜199.5m。
この定義で、指示書の参考値（0m、0.5m、1m、3.5mなど）と一致する。
Gazeboのheightmap自体の外周は−0.25〜199.75mであり、セル中心の範囲を使う方が0.25m内側になる。
10mちょうどを許可する。開始点が10m未満のシナリオは対象外にして記録し、ずらさない。
10mは事前指定の固定値であり、他の値を試したり調整したりしていない。

旧地点・新地点・距離・開始点は `waypoints.csv` と `manifest.json` の `waypoint_audit` に保存する。
地点が変わらない砂浜は、地点・順番・初期経路を含む021のmetadataと完全一致することを確認し、元のCSVの値をそのまま使う。
元の記録は `gazebo_online/physical_run`、`gazebo_lidar/physical_10`、`lidar_fine/physical_10` に残す。

## Claudeが通常のDockerで走らせる

リポジトリ直下から：

```bash
docker build -t thesis/jazzy-gz:1 -f conference/ros2_jazzy/gz_checks/Dockerfile conference/ros2_jazzy/gz_checks
cd conference
bash ros2_jazzy/gz_checks/run_edge_margin_checks.sh results/edge_margin/physical_run
python3 experiments/edge_margin_report.py results/edge_margin/physical_run
```

既にmanifestがある出力先は拒否する。実走を最初から再試行する場合は、新しい名前の出力先を指定する。
ソースは読み取り専用でマウントし、build/install・world・入力地図は一時領域に置く。
新しい生の記録は出力先の `physical/controls`、`physical/lidar`、`physical/fine` 以下に保存する。
元と同じCSV分割処理を使い、CSV・プロセスログの各ファイルを5MB未満にする。
再実行した砂浜に新しい軌跡があれば、集計で `trajectory_<patch>.png` を作る。

4方式のworldの標高は、022の実走で保存した `evaluation_reference.npz` の配列を再利用する。
同じ開始点・地点・巡回順を渡し、固定/仮想センサーでは021のheightmapの見た目・速さ1倍を保つ。
LiDARは022/023と同じメッシュの見た目、heightmap衝突、速さ0.3倍・途切れ期限1.0秒。
これらはmanifestに記録し、異なるLiDARの速さ・期限は拒否する。
LiDARの仕様・取り付け高さ・ノイズ・判定の仮定は022/023から変更しない。
既存ランナーへ追加した引数を省略すると、今までの対象・設定・集計を使う。

## 今回の実行状態

通常Dockerのラッパーを実行したが、`thesis/jazzy-gz:1` がなくexit=125で終了した。
新地点での実走は**未実行**。チェックインした表は、変更なしの5か所×4方式の再利用20行と、
地点が変わった5か所×4方式の未実行20行である。未実行の時間・完走・転倒の数値を埋めていない。
今回の場所・地点の比較は実際の地図生成とプランナーの実行から得た値。

`record_origin=reused` は再利用、`rerun` は走らせ直す対象、`excluded` は対象外。
実際に実行したかは別の `execution` 列と `data_source` 列で確認する。
集計の `executed` は記録済みの分母、`unexecuted` は未実行の数。記録済み部分で転倒が0でも、10か所で転倒が消えたとはいえない。
端の条件は地点と開始点だけに加え、経路全体を内側へ制限していないので、実走後も転倒が残る可能性がある。

## 集計とテスト

`runs.csv` は10か所×4方式、`summary.csv` は記録済み部分の件数と走行単位の中央値。
`paired_differences.csv` は、同じ砂浜で両方とも5地点と帰還を完了した組だけの差の中央値と組数。
10か所なので検定はしない。エネルギーの列・集計はない。
接触セルは中心軌跡で評価する。車体全体の接触を保証する指標ではない。
仮想センサー/固定走行で地図更新の時間が保存されていない場合は欠測のまま。

```bash
cd conference
python3 -m tests.test_edge_margin
python3 results/edge_margin/verification/run_tests.py
python3 ros2_jazzy/gz_checks/edge_margin_checks.py --prepare-only --output /tmp/edge-margin-new
```

集計表示の全文は `edge_margin_log.txt`。全テストの出力と既存ファイルの保持の確認は `verification/`、
実装と未実行の詳細は `REPORT_ja.md` を参照する。偽の記録は一時領域の単体テストだけで使い、実験結果には保存しない。
