from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime

class ChatMessage(BaseModel):
    """チャットメッセージモデル"""
    name: str = Field(..., min_length=1, description="チャットの名前")
    content: str = Field(..., min_length=1, description="チャットの内容")
    url: HttpUrl = Field(..., description="チャットのURL")
    timestamp: Optional[str] = Field(None, description="チャットのタイムスタンプ（ISO 8601形式）")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "開発進捗要約",
                "content": "本日の開発進捗について...",
                "url": "https://example.com",
                "timestamp": "2024-03-30T10:00:00+09:00"
            }
        } 