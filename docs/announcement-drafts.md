# Announcement Drafts

## X

小規模iOS開発者向けのOSS CLI `app-store-monitor` を公開しました。

App Store Connect analytics をローカルで集めて、日次KPIレポートをMarkdownで生成し、必要ならDiscordにも通知できます。mock mode付きなので認証情報なしで試せます。

https://github.com/nakamekun/app-store-monitor

## note

# 小規模iOS開発者向けOSS `app-store-monitor` を公開しました

個人開発や小規模チームでiOSアプリを運営していると、App Store Connectの数字を毎日見るだけでも少し手間がかかります。

`app-store-monitor` は、その作業をローカルで自動化するためのCLIです。

- App Store Connect analytics の日次データを取得
- SQLiteに保存
- MarkdownのKPIレポートを生成
- 必要に応じてDiscordへ通知
- mock modeで認証情報なしに動作確認

対象は、たくさんのダッシュボード機能がほしい人というより、「昨日の表示回数、ページビュー、ダウンロード、CVRを毎朝さっと見たい」個人・小規模iOS開発者です。

秘密情報や実データをリポジトリに含めない前提で作っており、mock dataとテストだけで動作を確認できます。

GitHub:
https://github.com/nakamekun/app-store-monitor
