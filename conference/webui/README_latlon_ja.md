# 緯度・経度の扱い

`conference/` で次を実行すると、既存 `real_las_*.npz` を書き直さず、横に `*.geo.json` を付ける。

```bash
python3 data_prep/export_maps.py --geo-only
python3 -m webui.server --host 127.0.0.1 --port 8088
python3 -m tests.test_geo
# 任意: PlaywrightとChromiumがある環境で画面・実ファイル書出しを確認
python3 -m webui.check_latlon --base-url http://127.0.0.1:8088
```

投影はGRS80・平面直角座標第8系だけを実装する。原点は36度・138.5度、縮尺0.9999。
国土地理院の河瀬の式（第三扁平率の5次級数）をNumPyで実装し、pyprojには依存しない。
出典は `tapp/geo.py` のdocstringの2つの国土地理院URL。018指示書の独立したpyproj基準値で照合する。
JGD2011/JGD2024の水平投影は同じ定数として扱う。観測時期・測地系間の変位補正やWGS84への変換は実装していない。

地図の最初のマス中心は `(x,y)=(0,0)`。
200mパッチの `(u,v)` は `(x-99.75,y-49.75)` であり、海岸線の基準点 `origin_xy` はパッチの画像中心ではない。
`offset_uv_m` に半セルとクロップのずれを保存する。X北・Y東への符号と回転は `patch_to_plane` と同じ。
位置情報は元LASパッチの `origin_xy,tangent,normal,res` とファイルの固定生成規約から作る。
任意の外部地図に位置を推測して付ける機能ではない。

地図詳細APIには位置情報がある場合だけ `geo` が追加される。既存のメートル座標・計画・シミュレーション・ロボット送信APIを使い続ける。
`POST /api/geo/to-latlon` は `map_id, points:[[x,y],...]`、逆の `/api/geo/to-map` は `points:[{lat,lng},...]` を受け付ける。
地図ファイルのSHA-256がサイドカーと一致しない場合は変換を拒否する。位置情報のない地図の表示は従来どおり。

画面ではマウスまたはタップ位置と地点一覧に緯度・経度を表示する。
JSONは `format:'latlng', map_id, start:{lat,lng}, points:[{lat,lng},...], method` を保存する。
テキストは**巡回地点だけ**を1行に `lat,lng`、小数9桁で保存する（基地は含めない）。
読み込みは同形式のJSON、`lat`と`lng`の配列を持つJSON、1行ごとのテキスト/CSVに対応する。
UIへ戻すメートル座標は既存のクリック入力と同じ小数3桁。API・変換関数は倍精度で返す。
実機やAndroidアプリのGPSを測った値ではなく、地図上の地点を変換した値である。
