# Claude の引き継ぎ（新しいセッション「修論2」へ、2026-11-20）

前のセッション（claude.ai/code、2026-11 前半〜11-20）が長くなったので、新しいセッションに引き継ぐ。**運用は変えない**（利用者の指示：精度を落とさない）。
新しいセッションは、まずこの文書、`CLAUDE.md`、`AGENTS.md`、`conference/ROADMAP_ja.md`、進捗ボード（`conference/progress/tasks.csv`）を読むこと。

## 運用（変えないこと）
- 窓口は利用者（Mac の Claude デスクトップアプリ）。Claude は方針・指示書・依頼文・**レビュー**・取り込み・進捗ボード。Codex は実装と研究 PC の実行。受け渡しは利用者が手で行う。
- **Codex のチャットは 3 つを使い回す**：研究PC実行（Mac のローカル、`ssh hayashi`）、研究実装1・研究実装2（クラウド）。依頼文には送り先のチャットを必ず書く。
- **レビューは Claude が行い、手順は `CLAUDE.md` の 1〜6 をすべて行う**（利用者の判断：Claude の方が精度が高い。軽くしない）。結果は `results/<タスク>/REVIEW_ja.md`。
  - 既定の出力のバイト一致は、**直す前のコード（git worktree）と同じ環境でその場で比べる**。別の PC で記録したハッシュとは小数の最後の桁が合わないことがある（`test_map_speed` が研究 PC で落ちた件）。
  - 地図のコードが変わったときは、`conference/results/map_speed/review/fuzz.py`（本物の砂浜で 160 回の更新、14 種類の配列）を直す前と後で走らせて比べる。
  - 全テストは `conference/tests/test_*.py` を 1 本ずつ（`PYTHONPATH=. python3 -m tests.<名前>`）。クラウドの環境では `pip install -r conference/requirements-venv.txt` が先に要る。
- 取り込みは `claude/laughing-tesla-igaehc` にマージ → PR を `realtime-map` へ → マージ。push は `claude/laughing-tesla-igaehc` だけ。
- **進捗ボード**（https://claude.ai/artifact/T627sMmE9VFZQFwaamScrV）：指示書を作ったとき（未着手）・依頼文を出したとき（実行中）・取り込んだとき（完了）に、指示書の「状態」の行と `conference/progress/tasks.csv` をそろえ、ボードに上げて `python3 conference/progress/check_board.py --mark-synced`。
  ボードへの上げ方：`tasks.csv` を Artifact の asset として上げ、`datasets/tasks` の `source.url` を差し替える（古い asset は消す）。走行結果は `outcomes.csv`・`datasets/outcomes`。
- 返事は日本語。研究室のリポジトリ（`hayashilab/*`）には push しない。認証情報は記録しない。

## 今の状態（2026-11-20）
| 番号 | 内容 | 状態 | どこで |
|---|---|---|---|
| 039 | 実時間 1 倍と 0.3 倍の比較 | 段階 A 完了。**段階 B は研究 PC の事前テストで `test_map_speed` が落ちて未開始** | 研究PC実行 |
| 041 | 障害物の膨らませをマス全体で判定（`--obstacle-clearance overlap`） | 実装済み。Claude のレビュー済み（`results/obstacle_clearance/REVIEW_ja.md`）。**全テストの結果を待って取り込む** | 研究実装1（終了） |
| — | `test_map_speed`・`test_obstacle_clearance` を、記録したハッシュではなく直す前の実装とその場で比べる形に直した | 作業ブランチにコミット済み。041 と一緒に取り込む | — |

研究実装2 は空き。

## 次にやること
1. 041 を取り込む（全テスト 36 本の合格を確かめてから）。`REVIEW_ja.md` の「テストの結果」に追記。ボードの 041 を「完了」に。
2. 研究PC実行に、039 段階 B の**やり直し**を送る（`realtime-map` を最新にして、事前テストからやり直す。依頼文は前のものに「最新を pull してテストからやり直す」を足す）。
3. 039 段階 B のあと、研究 PC で **041 の評価**（037 と同じ条件で `--obstacle-clearance centre` と `overlap` を各 3 回）。指示書を書く（042）。
   - 041 のレビューで見つけた穴：既定の `centre` では、膨らませで通れないになったマスでも、点が当たっていない（見ていない）マスは計画で通れるとみなされる。`overlap` はこれも直す。評価の考察に入れる。
4. そのあと：経路を追う側の許容（`off_path` 0.75m）の見直し、本当の高さの箱でのカメラの比較（037 では箱が 0.5m 高く差が出なかった）、`0167`・`0347` がいつも「経路なし」になる件。
5. ICAROB の本文（12/7 締め切り）：利用者の判断で後回し。Claude の提案は「遅くとも 11/28 に書き始める」（`ROADMAP_ja.md`）。

## 主な経緯（詳しくは各 REVIEW_ja.md）
- 034（`--online-fixes v1`）→ 035 で評価（転倒 0、止まったまま解消）→ 040 で `v2`（傾きのくり返しで終える、残りの経路でずれを測る）。
- 036（`local` 高速化）、038（地図の更新の高速化、出力はバイト単位で同じ）、039 段階 A（`--real-time-factor 1.0`）。
- 037：実機の位置のセンサーで L と LC は完走 11/15 で差なし。漂着物のマスへの進入は、地図は正しいのに経路がすぐそばを通ったため → 041。
- Claude の前のレビューの誤り（034 の所見 3、036 の lethal の一致、035 S1 の原因）は、それぞれの REVIEW_ja.md に訂正を書いた。
