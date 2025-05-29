from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from notion_client import Client
import os
from dotenv import load_dotenv
from mangum import Mangum
import json
from datetime import datetime
from pydantic import BaseModel
from typing import Optional

# Load environment variables
load_dotenv()

app = FastAPI(title="ChatGPT Webhook Bot4")

# Initialize Notion client
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "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")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "1ff74c56666e80fea8d8e73c2cde1df8")

notion = Client(auth=NOTION_TOKEN)

class ChatSummary(BaseModel):
    title: str
    summary: str
    content: str
    url: Optional[str] = "https://chat.openai.com"

def create_notion_page(title, summary, content, url=None):
    """Create a new page in Notion database"""
    try:
        # Combine summary and content
        combined_text = f"要約:\n{summary}\n\n内容:\n{content}"
        
        # Get current time in JST format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create page
        response = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "名前": {
                    "title": [{"text": {"content": title}}]
                },
                "テキスト": {
                    "rich_text": [{"text": {"content": combined_text[:2000]}}]  # Notion has a 2000 character limit
                },
                "日付": {
                    "date": {"start": current_time}
                },
                "URL": {
                    "rich_text": [{"text": {"content": url or "https://chat.openai.com"}}]
                }
            }
        )
        return True, response
    except Exception as e:
        return False, str(e)

@app.get("/")
async def root():
    return {
        "message": "ChatGPT Webhook Bot4 is running",
        "status": "active"
    }

@app.post("/chat-summary")
async def save_chat_summary(summary: ChatSummary):
    try:
        success, response = create_notion_page(
            summary.title,
            summary.summary,
            summary.content,
            summary.url
        )
        
        if success:
            return JSONResponse({
                "status": "success",
                "message": "Successfully saved to Notion"
            })
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Failed to save to Notion: {response}"
                }
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        body = await request.json()
        
        # Handle Notion's URL verification challenge
        if body.get("type") == "url_verification":
            challenge = body.get("challenge")
            print(f"Received webhook verification challenge: {challenge}")
            return JSONResponse({
                "type": "url_verification",
                "challenge": challenge
            })
        
        print(f"Received webhook request: {json.dumps(body, ensure_ascii=False)}")
        return JSONResponse({"status": "success"})
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

# Vercel handler
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    print(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port) 