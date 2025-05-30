from notion_client import Client
import os
from datetime import datetime

# Initialize Notion client
NOTION_TOKEN = "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"
NOTION_DATABASE_ID = "1ff74c56666e80fea8d8e73c2cde1df8"

notion = Client(auth=NOTION_TOKEN)

def create_test_page():
    try:
        # Get current time in JST format
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create test content
        title = "テストタイトル"
        summary = "これはテスト用の要約です"
        content = "これはテスト用の詳細な内容です"
        combined_text = f"要約:\n{summary}\n\n内容:\n{content}"
        
        # Create page
        response = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "名前": {
                    "title": [{"text": {"content": title}}]
                },
                "テキスト": {
                    "rich_text": [{"text": {"content": combined_text}}]
                },
                "日付": {
                    "date": {"start": current_time}
                },
                "URL": {
                    "rich_text": [{"text": {"content": "https://chat.openai.com"}}]
                }
            }
        )
        print("Successfully created page in Notion!")
        return True, response
    except Exception as e:
        print(f"Error: {str(e)}")
        return False, str(e)

if __name__ == "__main__":
    print("Testing Notion API connection...")
    try:
        # Test connection
        user = notion.users.me()
        print(f"Connected as user: {user.get('name', 'unknown')}")
        
        # Create test page
        success, response = create_test_page()
        if success:
            print("Test completed successfully!")
        else:
            print(f"Test failed: {response}")
    except Exception as e:
        print(f"Connection test failed: {str(e)}") 