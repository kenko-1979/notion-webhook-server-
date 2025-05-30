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
                    "url": "https://chat.openai.com"
                }
            }
        )
        print("Successfully created page in Notion!")
        return True, response
    except Exception as e:
        print(f"Error: {str(e)}")
        return False, str(e)

def test_database_info():
    try:
        # データベース情報の取得
        database = notion.databases.retrieve(NOTION_DATABASE_ID)
        print("\nDatabase Info:")
        print(f"Database ID: {database['id']}")
        print(f"Title: {database['title'][0]['text']['content'] if database['title'] else 'Untitled'}")
        print("\nProperties:")
        for prop_name, prop_info in database['properties'].items():
            print(f"- {prop_name} ({prop_info['type']})")
        
        return True, database
    except Exception as e:
        print(f"\nError getting database info: {str(e)}")
        return False, str(e)

if __name__ == "__main__":
    print("Testing Notion API connection...")
    try:
        # Test connection
        user = notion.users.me()
        print(f"Connected as user: {user.get('name', 'unknown')}")
        
        # Check database info
        success, database_info = test_database_info()
        if not success:
            print(f"Database info check failed: {database_info}")
            exit(1)
        
        # Create test page
        success, response = create_test_page()
        if success:
            print("Test completed successfully!")
        else:
            print(f"Test failed: {response}")
    except Exception as e:
        print(f"Connection test failed: {str(e)}") 