import os
import logging
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, status, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator, ValidationError
from notion_client import AsyncClient
from dotenv import load_dotenv
from mangum import Mangum
import json
from datetime import datetime, timedelta, timezone
import sys
import traceback
from tenacity import retry, stop_after_attempt, wait_exponential
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List, Annotated
import asyncio
from cachetools import TTLCache
from functools import wraps
import statistics
import re

# タイムゾーンの設定
JST = timezone(timedelta(hours=+9), 'JST')

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()

# 環境変数の取得
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))  # キャッシュの有効期限（秒）
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))  # バッチ処理のサイズ

# 必須環境変数のチェック
if not NOTION_TOKEN or not NOTION_DATABASE_ID:
    error_msg = "Missing required environment variables"
    logger.error(error_msg)
    raise ValueError(error_msg)

# メトリクス用の構造体
class Metrics:
    def __init__(self):
        self.request_times: List[float] = []
        self.queue_times: List[float] = []
        self.notion_api_times: List[float] = []
        self.total_requests: int = 0
        self.failed_requests: int = 0
        self.queue_size: int = 0
        self.last_reset: datetime = datetime.now(JST)

    def add_request_time(self, time: float):
        self.request_times.append(time)
        if len(self.request_times) > 100:  # 直近100件のみ保持
            self.request_times.pop(0)

    def add_queue_time(self, time: float):
        self.queue_times.append(time)
        if len(self.queue_times) > 100:
            self.queue_times.pop(0)

    def add_notion_time(self, time: float):
        self.notion_api_times.append(time)
        if len(self.notion_api_times) > 100:
            self.notion_api_times.pop(0)

    def get_stats(self) -> Dict[str, Any]:
        now = datetime.now(JST)
        uptime = (now - self.last_reset).total_seconds()
        
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "current_queue_size": self.queue_size,
            "uptime_seconds": uptime,
            "average_request_time": statistics.mean(self.request_times) if self.request_times else 0,
            "average_queue_time": statistics.mean(self.queue_times) if self.queue_times else 0,
            "average_notion_time": statistics.mean(self.notion_api_times) if self.notion_api_times else 0,
            "success_rate": ((self.total_requests - self.failed_requests) / self.total_requests * 100) if self.total_requests > 0 else 100
        }

# グローバル変数
notion_client = None
db_cache = TTLCache(maxsize=100, ttl=CACHE_TTL)
request_queue = asyncio.Queue()
processing = False
metrics = Metrics()

def cache_result(cache_key: str, ttl: int = CACHE_TTL):
    """関数の結果をキャッシュするデコレータ"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_value = db_cache.get(cache_key)
            if cache_value is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cache_value
            
            result = await func(*args, **kwargs)
            db_cache[cache_key] = result
            return result
        return wrapper
    return decorator

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフスパン管理"""
    global notion_client, processing
    # 起動時の処理
    logger.info("Initializing application...")
    notion_client = AsyncClient(auth=NOTION_TOKEN)
    try:
        # データベース情報を取得してキャッシュ
        database = await get_database_info()
        logger.info("Successfully connected to Notion database")
        
        # バッチ処理タスクの開始
        asyncio.create_task(process_request_queue())
        
        yield
    except Exception as e:
        logger.error(f"Failed to connect to Notion database: {str(e)}")
        raise
    finally:
        # 終了時の処理
        processing = False  # バッチ処理を停止
        if notion_client:
            await notion_client.aclose()
            notion_client = None
        logger.info("Closed Notion client")

# FastAPIアプリケーションの初期化
app = FastAPI(
    title="ChatGPT Summary Server",
    lifespan=lifespan
)

# リクエストボディのモデル
class ChatMessage(BaseModel):
    name: Annotated[str, Field(min_length=1, description="Chat message name")]
    content: Annotated[str, Field(min_length=1, description="Chat message content")]
    url: Annotated[str, Field(pattern="^https?://.*", description="Valid URL starting with http:// or https://")]
    timestamp: Optional[str] = Field(None, description="Optional timestamp in ISO format")

    @field_validator("name", "content")
    @classmethod
    def validate_non_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return v.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(v):
            raise ValueError("Invalid URL format")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError("Invalid timestamp format. Must be ISO format")
        return v

    model_config = {
        "validate_assignment": True,
        "extra": "forbid"
    }

class FileUploadRequest(BaseModel):
    mode: str = Field("external_url", description="Upload mode, must be 'external_url'")
    external_url: str = Field(..., description="The URL of the file to import")
    filename: str = Field(..., description="Name of the file")

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v != "external_url":
            raise ValueError("Only 'external_url' mode is supported")
        return v

    @field_validator("external_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(v):
            raise ValueError("Invalid URL format")
        return v

@cache_result("database_info")
async def get_database_info() -> Dict[str, Any]:
    """データベース情報を取得（キャッシュ付き）"""
    return await notion_client.databases.retrieve(database_id=NOTION_DATABASE_ID)

async def process_request_queue():
    """バッチ処理用のキュー処理"""
    global processing
    processing = True
    
    while processing:
        batch = []
        try:
            # バッチサイズまでリクエストを収集
            while len(batch) < BATCH_SIZE:
                try:
                    item = await asyncio.wait_for(request_queue.get(), timeout=1.0)
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
            
            if batch:
                # バッチ処理の実行
                await process_batch(batch)
                
        except Exception as e:
            logger.error(f"Error processing batch: {str(e)}")
            # エラーが発生しても処理は継続
            continue

async def process_batch(batch):
    """バッチをまとめて処理"""
    for item in batch:
        message, timestamp, start_time = item
        try:
            queue_time = (datetime.now(JST) - start_time).total_seconds()
            metrics.add_queue_time(queue_time)
            
            notion_start = datetime.now(JST)
            page_id = await create_notion_page(message)
            notion_time = (datetime.now(JST) - notion_start).total_seconds()
            metrics.add_notion_time(notion_time)
            
            logger.info(f"Processed item: queue_time={queue_time:.2f}s, notion_time={notion_time:.2f}s")
        except Exception as e:
            metrics.failed_requests += 1
            logger.error(f"Error processing item in batch: {str(e)}")
            continue  # エラーが発生しても次のアイテムの処理を継続

# カスタムエラークラス
class NotionError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        self.status_code = status.HTTP_400_BAD_REQUEST
        super().__init__(self.message)

class DatabaseError(Exception):
    def __init__(self, message: str):
        self.message = message
        self.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        super().__init__(self.message)

# エラーハンドラー
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """バリデーションエラーのハンドラー"""
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": error["loc"][-1],
            "message": error["msg"]
        })

    error_response = {
        "error": "Validation Error",
        "message": "Request validation failed",
        "details": error_details,
        "timestamp": get_jst_timestamp()
    }
    
    logger.error(f"Validation error: {error_details}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTPエラーのハンドラー"""
    error_response = {
        "error": "HTTP Error",
        "message": exc.detail,
        "status_code": exc.status_code,
        "timestamp": get_jst_timestamp()
    }
    
    logger.error(f"HTTP error: {error_response}")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response
    )

@app.exception_handler(NotionError)
async def notion_error_handler(request: Request, exc: NotionError):
    logger.error(f"Notion API error: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Notion API Error",
            "message": exc.message,
            "path": request.url.path,
            "timestamp": get_jst_timestamp()
        }
    )

@app.exception_handler(DatabaseError)
async def database_error_handler(request: Request, exc: DatabaseError):
    logger.error(f"Database error: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Database Error",
            "message": exc.message,
            "path": request.url.path,
            "timestamp": get_jst_timestamp()
        }
    )

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
async def create_notion_page(message: ChatMessage) -> str:
    """Notionページを作成する"""
    try:
        # プロパティの変換
        properties = {
            "名前": {"title": [{"text": {"content": message.name}}]},
            "テキスト": {"rich_text": [{"text": {"content": message.content}}]},
            "URL": {"url": str(message.url)},  # URLを文字列として確実に変換
            "日付": {"date": {"start": message.timestamp or get_jst_timestamp()}}
        }
        
        # ページの作成
        response = await notion_client.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties=properties
        )
        
        page_id = response["id"]
        logger.info(f"Successfully created Notion page with ID: {page_id}")
        return page_id
    except Exception as e:
        error_msg = f"Failed to create Notion page: {str(e)}"
        logger.error(error_msg)
        logger.error(f"Request details: {message.model_dump()}")
        if "Unauthorized" in str(e):
            raise NotionError(error_msg, status_code=status.HTTP_401_UNAUTHORIZED)
        elif "Not Found" in str(e):
            raise NotionError(error_msg, status_code=status.HTTP_404_NOT_FOUND)
        elif "Validation" in str(e):
            raise NotionError(error_msg, status_code=status.HTTP_400_BAD_REQUEST)
        raise NotionError(error_msg)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Server is running",
        "queue_size": request_queue.qsize()
    }

def get_jst_timestamp() -> str:
    """現在のJST時刻をISO形式で取得"""
    return datetime.now(JST).isoformat()

@app.get("/metrics")
async def get_metrics():
    """メトリクス情報を取得するエンドポイント"""
    return metrics.get_stats()

@app.post("/webhook")
async def webhook(message: ChatMessage, background_tasks: BackgroundTasks):
    try:
        metrics.total_requests += 1
        metrics.queue_size = request_queue.qsize()
        
        logger.info(f"Received webhook request for chat: {message.name}")
        start_time = datetime.now(JST)
        
        await request_queue.put((message, None, start_time))
        
        end_time = datetime.now(JST)
        processing_time = (end_time - start_time).total_seconds()
        metrics.add_request_time(processing_time)
        logger.info(f"Request queued in {processing_time:.2f} seconds")
        
        content = {
            "status": "accepted",
            "message": "Request queued for processing",
            "queue_position": request_queue.qsize(),
            "timestamp": get_jst_timestamp()
        }
        
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=content,
            headers={"Content-Type": "application/json"}
        )
    except ValidationError as e:
        metrics.failed_requests += 1
        logger.error(f"Validation error in webhook endpoint: {str(e)}")
        logger.error(f"Request details: {message.model_dump()}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "Validation Error",
                "message": str(e),
                "timestamp": get_jst_timestamp(),
                "details": [{"field": err["loc"][-1], "message": err["msg"]} for err in e.errors()]
            }
        )
    except Exception as e:
        metrics.failed_requests += 1
        logger.error(f"Error in webhook endpoint: {str(e)}")
        logger.error(f"Request details: {message.model_dump()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Error handler for uncaught exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_details = {
        "message": "An unexpected error occurred",
        "error": str(exc),
        "path": request.url.path,
        "method": request.method,
    }
    logger.error(f"Uncaught exception: {error_details}")
    return JSONResponse(
        status_code=500,
        content=error_details
    )

@app.post("/files/upload")
async def upload_file(file_request: FileUploadRequest):
    try:
        # Step 1: Create file upload
        response = await notion_client.files.create(
            mode=file_request.mode,
            external_url=file_request.external_url,
            filename=file_request.filename
        )
        
        logger.info(f"File upload initiated: {response['id']}")
        
        # Step 2: Wait for the upload to complete
        file_upload_id = response["id"]
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            file_status = await notion_client.files.retrieve(file_upload_id)
            
            if file_status["status"] == "uploaded":
                logger.info(f"File upload completed: {file_upload_id}")
                return {
                    "status": "success",
                    "file_upload_id": file_upload_id,
                    "message": "File upload completed"
                }
            elif file_status["status"] == "failed":
                error_msg = file_status.get("file_import_result", {}).get("error", {}).get("message", "Unknown error")
                logger.error(f"File upload failed: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File upload failed: {error_msg}"
                )
            
            retry_count += 1
            await asyncio.sleep(5)  # Wait 5 seconds before checking again
        
        # If we reach here, the upload is still pending
        return {
            "status": "pending",
            "file_upload_id": file_upload_id,
            "message": "File upload is still processing"
        }
        
    except ValidationError as e:
        logger.error(f"Validation error in file upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Vercel handler
handler = Mangum(app)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port) 