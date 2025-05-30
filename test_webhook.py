import requests
import time
import json
import pytest
from datetime import datetime

def test_webhook_success():
    url = "http://localhost:10000/webhook"
    headers = {"Content-Type": "application/json"}
    data = {
        "name": "開発進捗要約 2024-03-30",
        "content": """本日の開発進捗：
1. エラーハンドリングの改善
- カスタムエラークラスの実装
- バリデーション処理の強化
- エラーレスポンスの構造化

2. パフォーマンス最適化
- キュー処理時間: 1.0-1.02秒
- Notion API処理時間: 0.36-4.56秒""",
        "url": "https://example.com",
        "timestamp": "2024-03-30T10:00:00+09:00"
    }
    
    start_time = time.time()
    try:
        response = requests.post(url, headers=headers, json=data)
        end_time = time.time()
        
        print(f"Response time: {(end_time - start_time):.2f} seconds")
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        assert response.status_code == 202
        response_data = response.json()
        assert "status" in response_data
        assert "message" in response_data
        assert "queue_position" in response_data
        assert "timestamp" in response_data
        assert response_data["status"] == "accepted"
    except Exception as e:
        print(f"Error in success test: {str(e)}")
        raise

def test_webhook_validation_error():
    url = "http://localhost:10000/webhook"
    headers = {"Content-Type": "application/json"}
    
    print("\nTesting empty name validation:")
    data1 = {
        "name": "",  # 空の名前
        "content": "Test content",
        "url": "https://example.com"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data1)
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        
        assert response.status_code == 400
        response_data = response.json()
        assert "error" in response_data
        assert "message" in response_data
        assert "timestamp" in response_data
        assert "name" in response_data["message"].lower()
    except Exception as e:
        print(f"Error in empty name test: {str(e)}")
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        raise
    
    print("\nTesting invalid URL validation:")
    data2 = {
        "name": "Test Message",
        "content": "Test content",
        "url": "invalid-url"  # 無効なURL
    }
    
    try:
        response = requests.post(url, headers=headers, json=data2)
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        
        assert response.status_code == 400
        response_data = response.json()
        assert "error" in response_data
        assert "message" in response_data
        assert "Invalid URL format" in response_data["message"]
    except Exception as e:
        print(f"Error in invalid URL test: {str(e)}")
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        raise

    print("\nTesting missing field validation:")
    data3 = {
        "name": "Test Message",
        # contentフィールドを省略
        "url": "https://example.com"
    }
    
    try:
        response = requests.post(url, headers=headers, json=data3)
        print(f"Status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response: {response.text}")
        
        assert response.status_code == 400
        response_data = response.json()
        assert "error" in response_data
        assert "message" in response_data
        assert "content" in response_data["message"].lower()
    except Exception as e:
        print(f"Error in missing field test: {str(e)}")
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        raise

def test_metrics():
    url = "http://localhost:10000/metrics"
    try:
        response = requests.get(url)
        
        assert response.status_code == 200
        metrics = response.json()
        
        print("\nMetrics response:")
        print(json.dumps(metrics, indent=2))
        
        # メトリクスの検証
        assert "total_requests" in metrics
        assert "failed_requests" in metrics
        assert "current_queue_size" in metrics
        assert "average_request_time" in metrics
        assert isinstance(metrics["total_requests"], int)
        assert isinstance(metrics["failed_requests"], int)
        assert isinstance(metrics["current_queue_size"], int)
        assert isinstance(metrics["average_request_time"], (int, float))
    except Exception as e:
        print(f"Error in metrics test: {str(e)}")
        print(f"Response status: {response.status_code}")
        print(f"Response text: {response.text}")
        raise

def run_all_tests():
    print("Running webhook tests...")
    print("\n1. Testing successful webhook request:")
    test_webhook_success()
    
    print("\n2. Testing validation errors:")
    test_webhook_validation_error()
    
    print("\n3. Testing metrics endpoint:")
    test_metrics()
    
    print("\nAll tests completed successfully!")

def test_webhook():
    url = "http://localhost:10000/webhook"
    headers = {"Content-Type": "application/json"}
    data = {
        "name": "開発進捗要約 2024-03-30",
        "content": """本日の開発進捗：

1. エラーハンドリングの改善
- カスタムエラークラスの実装
- バリデーション処理の強化
- エラーレスポンスの構造化

2. パフォーマンス最適化
- キュー処理時間: 1.0-1.02秒
- Notion API処理時間: 0.36-4.56秒

3. 実装された機能
- 非同期バッチ処理
- メトリクス収集
- キャッシュ機能""",
        "url": "https://github.com/kenko-1979/notion-webhook-server-",
        "timestamp": None
    }
    
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

if __name__ == "__main__":
    run_all_tests()
    test_webhook() 