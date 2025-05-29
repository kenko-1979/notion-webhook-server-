# Notion Webhook Server

ChatGPTやCursorでの会話を要約してNotionデータベースに保存するためのWebhookサーバーです。

## 機能

- チャット内容の要約をNotionデータベースに保存
- 会話の要約、タイトル、URL、日付を記録
- FastAPIベースのRESTful API

## エンドポイント

### POST /chat-summary

チャットの要約をNotionに保存します。

リクエスト例：
```json
{
    "title": "議題のタイトル",
    "summary": "会話の要約",
    "content": "詳細な内容",
    "url": "関連URL（オプション）"
}
```

## 環境変数

- `NOTION_TOKEN`: Notionインテグレーションのトークン
- `NOTION_DATABASE_ID`: 保存先のNotionデータベースID

## デプロイ

このプロジェクトはVercelにデプロイされています。

## 技術スタック

- Python 3.9+
- FastAPI
- Notion API
- Vercel 