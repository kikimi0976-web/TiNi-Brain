import threading
import websocket
import json
import time
import os
import datetime
from fastapi import FastAPI
import uvicorn
from ddgs import DDGS
import yt_dlp

# --- THƯ VIỆN GOOGLE ---
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

app = FastAPI()

# URL kết nối (Tôi giữ nguyên Token cũ của bạn, hãy đảm bảo nó còn hạn)
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjczNTUwNywiYWdlbnRJZCI6MTI1MDY3MCwiZW5kcG9pbnRJZCI6ImFnZW50XzEyNTA2NzAiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzcwMTMwMTUzLCJleHAiOjE4MDE2ODc3NTN9.rIEhPoD4Pl45t4qgW54-yWi_qQfSFteFdmHt4wnQzzqNi19ueQOBNk4L_coeVF7yos5VnZXggWTNffCa9oM48g"

# ==============================================================================
# PHẦN 1: GOOGLE ASSISTANT (XỬ LÝ LỊCH & EMAIL)
# ==============================================================================
class GoogleAssistant:
    def __init__(self):
        # Phạm vi quyền hạn (chỉ đọc)
        self.SCOPES = [
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/gmail.readonly'
        ]
        self.creds = None
        
        # Đọc token từ file (File này được Render tạo ra từ Secret Files)
        if os.path.exists('token.json'):
            try:
                self.creds = Credentials.from_authorized_user_file('token.json', self.SCOPES)
            except Exception as e:
                print(f"!! [GOOGLE] Lỗi đọc file token: {e}")

        # Cơ chế tự động làm mới token nếu hết hạn (Refresh Token)
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                print(">>> [GOOGLE] Đã tự động gia hạn Token thành công.")
            except Exception as e:
                print(f"!! [GOOGLE] Không thể gia hạn token: {e}")

    def get_calendar(self):
        """Lấy 5 sự kiện sắp tới"""
        try:
            if not self.creds or not self.creds.valid:
                return "Lỗi: Server chưa có quyền truy cập Google (Thiếu token.json hợp lệ)."
            
            service = build('calendar', 'v3', credentials=self.creds)
            now = datetime.datetime.utcnow().isoformat() + 'Z' # Giờ UTC hiện tại
            
            events_result = service.events().list(
                calendarId='primary', timeMin=now,
                maxResults=5, singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])

            if not events:
                return "Hiện tại bạn không có sự kiện nào sắp tới trong lịch."
            
            result_text = "Lịch trình sắp tới của bạn:\n"
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                # Làm sạch chuỗi thời gian cho dễ đọc
                clean_time = start.replace('T', ' ').split('+')[0]
                result_text += f"- {event['summary']} (lúc {clean_time})\n"
            
            return result_text
        except Exception as e:
            return f"Gặp lỗi khi đọc lịch: {str(e)}"

    def get_gmail(self):
        """Đọc tiêu đề 3 email mới nhất"""
        try:
            if not self.creds or not self.creds.valid:
                return "Lỗi: Server chưa có quyền truy cập Google (Thiếu token.json hợp lệ)."
            
            service = build('gmail', 'v1', credentials=self.creds)
            
            # Lấy danh sách ID của 3 mail mới nhất trong Inbox
            results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=3).execute()
            messages = results.get('messages', [])

            if not messages:
                return "Hộp thư đến của bạn hiện đang trống."
            
            result_text = "3 Email mới nhất của bạn:\n"
            for msg in messages:
                txt = service.users().messages().get(userId='me', id=msg['id']).execute()
                payload = txt.get('payload', {})
                headers = payload.get('headers', [])
                
                subject = next((i['value'] for i in headers if i['name'] == 'Subject'), "(Không tiêu đề)")
                sender = next((i['value'] for i in headers if i['name'] == 'From'), "Ẩn danh")
                
                result_text += f"- Từ: {sender}\n  Tiêu đề: {subject}\n"
            
            return result_text
        except Exception as e:
            return f"Gặp lỗi khi đọc Gmail: {str(e)}"

# Khởi tạo đối tượng Google để dùng chung
google_bot = GoogleAssistant()


# ==============================================================================
# PHẦN 2: CÁC CÔNG CỤ CŨ (WEB SEARCH & MUSIC)
# ==============================================================================

def tool_web_search(query):
    try:
        print(f">>> [DDG] Đang tìm kiếm: {query}", flush=True)
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=5)]
            if not results:
                return "Không tìm thấy thông tin phù hợp trên Internet."
            
            search_content = []
            for r in results:
                search_content.append(f"Tiêu đề: {r['title']}\nNội dung: {r['body']}")
            
            return "\n---\n".join(search_content)
    except Exception as e:
        print(f"!! Lỗi DDG: {str(e)}", flush=True)
        return "Hệ thống tìm kiếm đang gặp sự cố."

def tool_play_music(song_name):
    try:
        print(f">>> [MUSIC] Đang tìm: {song_name}", flush=True)
        ydl_opts = {
            'format': 'bestaudio[ext=mp3]/bestaudio[ext=m4a]/best', 
            'default_search': 'scsearch',
            'noplaylist': True,
            'quiet': True,
            'match_filter': yt_dlp.utils.match_filter_func("duration > 60 & duration < 600"),
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{song_name}", download=False)
            if 'entries' in info: info = info['entries'][0]
            
            return {"url": info['url'], "title": f"{info['title']} (SoundCloud)"}
    except Exception as e:
        print(f"!! Lỗi Music: {e}", flush=True)
        return "Không tìm thấy bài hát phù hợp."


# ==============================================================================
# PHẦN 3: LOGIC WEBSOCKET MCP (TRÁI TIM CỦA ROBOT)
# ==============================================================================

def on_message(ws, message):
    try:
        data = json.loads(message)
        method = data.get("method")
        msg_id = data.get("id") if data.get("id") is not None else data.get("message_id")

        # 1. PING - PONG
        if method == "ping":
            ws.send(json.dumps({"id": msg_id, "jsonrpc": "2.0", "result": {}}))
            return

        # 2. HANDSHAKE
        if method == "notifications/initialized":
            print(">>> [READY] Robot đã kết nối thành công!", flush=True)
            ws.send(json.dumps({"jsonrpc": "2.0", "method": "notifications/ready", "params": {}}))
            return

        # 3. INITIALIZE
        if method == "initialize":
            reply = {"id": msg_id, "jsonrpc": "2.0", "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "logging": {}}, 
                "serverInfo": {"name": "Truman-Brain", "version": "2.0-GoogleIntegrated"}
            }}
            ws.send(json.dumps(reply))
            return

        # 4. KHAI BÁO DANH SÁCH CÔNG CỤ (TOOLS LIST)
        if method == "tools/list":
            reply = {"id": msg_id, "jsonrpc": "2.0", "result": {"tools": [
                {
                    "name": "web_search", 
                    "description": "Tìm kiếm tin tức trực tuyến",
                    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                },
                {
                    "name": "play_music", 
                    "description": "Tìm và phát nhạc",
                    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                },
                # --- CÔNG CỤ MỚI: GOOGLE ---
                {
                    "name": "check_schedule",
                    "description": "Kiểm tra lịch trình, thời khóa biểu trên Google Calendar",
                    "inputSchema": {"type": "object", "properties": {}, "required": []} 
                },
                {
                    "name": "check_email",
                    "description": "Đọc email mới nhất từ Gmail",
                    "inputSchema": {"type": "object", "properties": {}, "required": []}
                }
            ]}}
            ws.send(json.dumps(reply))
            print(">>> [TOOLS] Đã gửi danh sách công cụ (Search, Music, Calendar, Gmail).", flush=True)
            return

        # 5. XỬ LÝ KHI ROBOT GỌI CÔNG CỤ (TOOLS CALL)
        if method == "tools/call":
            params = data.get("params", {})
            tool_name = params.get("name")
            args = params.get("arguments", {})
            
            print(f">>> [CALL] Robot gọi công cụ: {tool_name}", flush=True)
            res_text = ""

            # --- Xử lý từng công cụ ---
            if tool_name == "web_search":
                res_text = tool_web_search(args.get("query"))
            
            elif tool_name == "play_music":
                res_music = tool_play_music(args.get("query"))
                res_text = f"Đang mở nhạc: {res_music['title']}" if isinstance(res_music, dict) else res_music
            
            elif tool_name == "check_schedule":
                # Gọi Google Assistant để lấy lịch
                res_text = google_bot.get_calendar()
            
            elif tool_name == "check_email":
                # Gọi Google Assistant để lấy mail
                res_text = google_bot.get_gmail()

            # --- Phản hồi kết quả về cho Robot ---
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": str(res_text)}]
                }
            }
            ws.send(json.dumps(response))
            print(f">>> [DONE] Đã trả lời kết quả cho ID: {msg_id}", flush=True)
            return

    except Exception as e:
        print(f"!! Lỗi WebSocket: {str(e)}", flush=True)

def on_open(ws):
    print(">>> ĐÃ MỞ KẾT NỐI. ĐANG ĐỢI ROBOT...", flush=True)

def run_ws():
    while True:
        try:
            ws = websocket.WebSocketApp(MCP_ENDPOINT, on_open=on_open, on_message=on_message)
            ws.run_forever(ping_interval=30, ping_timeout=10) 
        except Exception as e:
            print(f"!! Mất kết nối, thử lại sau 10s: {e}", flush=True)
            time.sleep(10)

@app.get("/")
def health(): return {"status": "Online"}

@app.head("/")
def head(): return {"status": "OK"}

@app.on_event("startup")
async def startup():
    threading.Thread(target=run_ws, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)