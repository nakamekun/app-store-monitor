# Analytics Standard

このドキュメントは `app-store-monitor` の指標定義と日次レポートの判定基準を固定するための運用メモです。現時点は mock データで運用し、実 API 接続後も同じ定義で保存・集計します。

## CVR 定義

CVR は App Store 上の表示からダウンロードまでの効率を見る指標です。

```text
CVR = downloads / impressions
```

- `downloads`: 初回ダウンロード数。再ダウンロードやアップデートは原則含めない想定。
- `impressions`: App Store 上でアプリが表示された回数。
- impressions が 0 の場合、CVR は 0 として扱います。

用途:

- 検索・閲覧面で見られているのに獲得できているかを見る。
- source type ごとの流入品質を比較する。

## Page CVR 定義

Page CVR はプロダクトページ閲覧からダウンロードまでの効率を見る指標です。現在の `daily_metrics.conversion_rate` はこの Page CVR として扱います。

```text
Page CVR = downloads / product_page_views
```

- `product_page_views`: App Store のプロダクトページ閲覧数。
- product page views が 0 の場合、Page CVR は 0 として扱います。

用途:

- スクリーンショット、説明文、レビュー、価格、訴求軸の改善余地を見る。
- impressions は多いが page views が少ない問題と、page views はあるが downloads が少ない問題を分ける。

## 改善候補の判定基準

日次レポートの改善候補は、一定以上の閲覧があるのに Page CVR が低いアプリを優先します。

初期ルール:

```text
product_page_views >= 40
AND Page CVR < 10%
```

優先度スコア:

```text
improvement_score = product_page_views * (0.10 - Page CVR)
```

見方:

- score が高いほど、ページ改善で増やせる可能性のある downloads が大きい。
- views が少ないアプリは、ページ改善より先に露出・検索導線・source type の見直しを優先する。
- Page CVR が 10% 以上でも、source type 単位で低い流入があれば個別に確認する。

## 7日平均との比較ルール

日次の前日比はノイズが出やすいため、意思決定では 7日平均との比較を標準にします。

比較対象:

```text
current_day = 対象日
baseline_7d = 対象日の前日までの直近7日平均
```

例:

- 対象日が 2026-05-08 の場合、baseline は 2026-05-01 から 2026-05-07。
- 対象日を baseline に含めない。
- 7日未満しかデータがない場合は、利用可能な過去日数の平均として扱い、レポート上で不足を明示する。

主な判定:

```text
CVR低下 = current Page CVR - baseline Page CVR <= -2.0pt
DL増加 = current downloads >= baseline downloads * 1.25
改善候補 = current views >= 40 AND current Page CVR < min(10%, baseline Page CVR - 1.0pt)
```

補足:

- downloads が少ないアプリは 1件差の影響が大きいため、Page CVR低下だけで判断しない。
- impressions、product page views、downloads、Page CVR を合わせて見る。
- 週末・祝日・リリース直後・広告出稿日は別注記にする。

## Source Type の見方

source type は「どの導線から来た数字か」を分ける軸です。App Store Connect の実データ接続後は、Apple 側の source type 名を正規化して保存します。

主な見方:

- `App Store Search`
  - 検索流入。キーワード、タイトル、サブタイトル、キーワード欄、レビュー評価の影響を受けやすい。
  - impressions は多いが Page CVR が低い場合、検索意図とページ訴求がずれている可能性がある。
- `App Store Browse`
  - Today、カテゴリ、ランキングなどの閲覧流入。
  - 露出面の文脈が広く、Search より Page CVR が低くても自然な場合がある。
- `Web Referrer`
  - Web、SNS、記事、LP など外部Webからの流入。
  - LP の訴求と App Store ページの訴求が一致しているかを見る。
- `App Referrer`
  - 他アプリ内からの流入。
  - 連携元アプリや紹介文脈によって Page CVR が大きく変わる。

source type 分析の基本:

- 全体平均だけで判断せず、source type ごとに Page CVR と downloads を見る。
- downloads が多い source type は、CVR が少し下がっただけでも影響が大きい。
- impressions が多く page views が少ない場合は、アイコン・タイトル・検索面の訴求を疑う。
- page views が多く downloads が少ない場合は、スクリーンショット・説明文・価格・レビュー面を疑う。
