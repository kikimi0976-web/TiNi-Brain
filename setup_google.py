# File: setup_google.py
from google_auth_oauthlib.flow import InstalledAppFlow
import os

# Quyền hạn robot cần (Chỉ đọc)
SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    
]

def main():
    if not os.path.exists('credentials.json'):
        print("Lỗi: Bạn chưa copy file credentials.json vào thư mục này!")
        return

    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)

    # Lưu token
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    
    print("\n>>> THÀNH CÔNG! File 'token.json' đã được tạo.")
    print(">>> Bạn hãy copy nội dung file này để dùng cho Render (Secret Files).")

if __name__ == '__main__':
    main()