from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from notion_client import Client
import os
from dotenv import load_dotenv
from mangum import Mangum
import json
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
import logging
import sys

# Configure logging to output to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="ChatGPT Summary Server")

# Initialize Notion client
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

logger.info(f"Starting application with database ID: {NOTION_DATABASE_ID}")

if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    logger.error("Missing required environment variables")
    raise ValueError("NOTION_TOKEN and NOTION_DATABASE_ID must be set")

try:
    notion = Client(auth=NOTION_TOKEN)
    # Test the connection immediately
    notion.users.me()
    logger.info("Successfully connected to Notion API")
except Exception as e:
    logger.error(f"Failed to initialize Notion client: {e}")
    raise

class ChatSummary(BaseModel):
    title: str
    summary: str
    content: str
    url: Optional[str] = "https://chat.openai.com"

def create_notion_page(title, summary, content, url=None):
    """Create a new page in Notion database"""
    try:
        logger.info(f"Creating new page with title: {title}")
        
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
                    "rich_text": [{"text": {"content": combined_text[:2000]}}]
                },
                "日付": {
                    "date": {"start": current_time}
                },
                "URL": {
                    "rich_text": [{"text": {"content": url or "https://chat.openai.com"}}]
                }
            }
        )
        logger.info("Successfully created page in Notion")
        return True, response
    except Exception as e:
        logger.error(f"Failed to create page in Notion: {e}")
        return False, str(e)

@app.get("/")
async def root():
    try:
        # Test Notion connection
        user = notion.users.me()
        logger.info(f"Health check successful, connected as user: {user.get('name', 'unknown')}")
        return {
            "message": "ChatGPT Summary Server is running",
            "status": "active",
            "notion_connection": "ok",
            "user": user.get("name")
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "message": "Service is running but Notion connection failed",
                "status": "error",
                "error": str(e)
            }
        )

@app.post("/chat-summary")
async def save_chat_summary(summary: ChatSummary):
    try:
        logger.info(f"Received request to save summary: {summary.title}")
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
            logger.error(f"Failed to save to Notion: {response}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Failed to save to Notion: {response}"
                }
            )
    except Exception as e:
        logger.error(f"Error in save_chat_summary: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e)
            }
        )

# Error handler for uncaught exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Uncaught exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "message": "An unexpected error occurred",
            "error": str(exc)
        }
    )

# Vercel handler
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port) 