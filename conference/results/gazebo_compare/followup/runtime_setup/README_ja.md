# クラウドで実際に使用した一時実行環境の記録

通常の再実行には `ros2_jazzy/gz_checks/run_compare_checks.sh` を使う。
このフォルダは、DockerのVFS領域が容量不足だったクラウド環境で使用した補助手順の記録である。

- `image_source.json` と `image_manifest.json` は、公開 `osrf/ros:jazzy-desktop-full` の取得時の記録。
- `pull_runtime.py` は各レイヤーのSHA-256を照合して `/tmp/task019-oci/rootfs` に展開したもの。絶対シンボリックリンクは同じ展開先内への相対リンクへ変換し、デバイスは展開しない。
- `namespace_run.sh` は実行に使用したスクリプト。ホストのパッケージを変更せず、一般ユーザーのuser/mount namespace内で一時rootfsにchrootし、pandasを追加してROS2のビルドと比較スクリプトを実行した。
- ソースは読取専用で `/conference`、結果は書込可能な `/output` としてマウントした。worldとビルド・キャッシュは一時rootfs内の `/tmp` に置いた。

ここにはこのクラウド固有の `/workspace/thesis-019` と `/tmp/task019-oci` のパスをそのまま残している。
別環境向けの汎用インストーラーではない。user namespaceが許可されている環境が必要で、このクラウドではサンドボックス外での実行許可を得て使用した。
