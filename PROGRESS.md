# Notion Webhook Server 開発進捗

## プロジェクト概要
- NotionのデータベースにChatGPTの会話を保存するWebhookサーバー
- FastAPIベースで開発
- 一方通行の通信（ChatGPT → Notion）
- Renderでの動作確認済み、Vercelへの移行を試行中

## 環境構成
- Python 3.13.3
- 主要パッケージ：
  - fastapi==0.110.0
  - uvicorn==0.27.1
  - python-dotenv==1.0.1
  - notion-client==2.2.1
  - mangum>=0.17.0

## トークン試行履歴と問題点

### 1回目の試行
- トークン: `secret_313455018064j1ty10MDp5814cx0owv2gKIeTGBnDoNgVI`
- 結果: 失敗
- 問題点: secretプレフィックスは Notion → Webhook プッシュ用であり、本プロジェクトの用途と異なる

### 2回目の試行
- トークン: `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`
- 結果: 401 Unauthorized
- エラー: "API token is invalid"

### 3回目の試行
- データベースID: `1ff74c56666e80fea8d8e73c2cde1df8`（Notionのビューリンクから取得）
- トークン: `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`
- 結果: モジュールのインポートエラー
- 対応: 
  1. 新しいPowerShellウィンドウを開く
  2. 必要なパッケージを再インストール
  3. 環境変数を設定してサーバーを起動

### 4回目の試行（Notion仕様変更対応）
- Notionの仕様変更：インテグレーション機能が「Connect」に統合
- 正しいトークン取得手順：
  1. データベースビューで「Connect」をクリック
  2. インテグレーションを選択
  3. 内部インテグレーションシークレットを使用

- データベースID: `1ff74c56666e80fea8d8e73c2cde1df8`（変更なし）
- トークン: 内部インテグレーションシークレット（Connect機能から取得）

## 理解した重要ポイント（更新）
1. トークンの種類と用途：
   - `secret_` プレフィックス：Notion → Webhook へのプッシュ用（本プロジェクトでは不要）
   - `ntn_` プレフィックス：古い形式のトークン（非推奨）
   - 内部インテグレーションシークレット：新しい接続方式で使用するトークン（推奨）

2. 環境変数の設定方法：
   ```powershell
   $env:NOTION_TOKEN = "ntn_..."
   $env:NOTION_DATABASE_ID = "1ff74c56666e80fea8d8e73c2cde1df8"
   ```

3. データベースIDの取得方法：
   - Notionのデータベースビューを開く
   - ビューのオプションから「ビューのリンクをコピー」を選択
   - URLから抽出: `https://www.notion.so/[DATABASE_ID]?v=...`
   - 例: `https://www.notion.so/1ff74c56666e80fea8d8e73c2cde1df8?v=1ff74c56666e8025b993000cbdfe83ac&source=copy_link`

## 現在の課題
1. Notion APIの認証エラー（401 Unauthorized）
2. 環境変数の永続化
3. Python 3.13.3との互換性確認

## 次のステップ
1. 正しいNotion Integration トークンの確認
2. ローカル環境での動作確認
3. Vercelデプロイ設定の調整

## 注意点
- `.env`ファイルは作成できない（globalIgnoreによりブロック）
- 環境変数は一時的な設定となっている
- トークンの形式と用途の違いに注意が必要 