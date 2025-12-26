import threading
import websocket
import json
import time
from fastapi import FastAPI
import uvicorn
from duckduckgo_search import DDGS
import yt_dlp

app = FastAPI()

# ==============================================================================
# CẤU HÌNH: DÁN TOKEN MỚI CỦA BẠN VÀO GIỮA HAI DẤU NGOẶC KÉP DƯỚI ĐÂY
# ==============================================================================
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjczNTUwNywiYWdlbnRJZCI6MTI1MDY3MCwiZW5kcG9pbnRJZCI6ImFnZW50XzEyNTA2NzAiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzY2NzMyNzY4LCJleHAiOjE3OTgyOTAzNjh9.GrQ7EstI2e2WJGJ5Vh1lmJfgCZrlrnKY4JQY9-1E4v2rc78-4PUElH8tz7yU7hcGn-9B9iumWwHgdicvEoyTlw"

# --- HÀM 1: TÌM NHẠC THÔNG MINH (DUCKDUCKGO + YT-DLP) ---
def get_youtube_audio(song_name):
    print(f"--> [Search] Đang tìm: {song_name}...")
    try:
        # Tìm link qua DuckDuckGo để tránh YouTube chặn IP
        search_query = f"{song_name} lyrics youtube"
        results = DDGS().videos(
            keywords=search_query,
            region="vn-vn",
            safesearch="off",
            max_results=1
        )
        
        if not results:
            return None

        video_url = results[0]['content']
        video_title = results[0]['title']
        print(f"--> [Found] Tìm thấy: {video_title}")

        # Lấy link audio trực tiếp
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {"title": info.get('title'), "url": info.get('url')}

    except Exception as e:
        print(f"--> [Error] Lỗi lấy nhạc: {e}")
        return None

# --- HÀM 2: XỬ LÝ LỆNH TRONG LUỒNG RIÊNG ---
def process_command(ws, message_id, user_text):
    try:
        response_payload = None
        # Kiểm tra từ khóa mở nhạc
        keywords = ["mở bài", "nghe bài", "phát bài", "hát bài", "bật bài"]
        if any(k in user_text for k in keywords):
            song_name = user_text
            for k in keywords:
                song_name = song_name.replace(k, "")
            
            song_data = get_youtube_audio(song_name.strip())
            
            if song_data:
                response_payload = {
                    "type": "audio",
                    "url": song_data['url'],
                    "text": f"Đang phát: {song_data['title']}"
                }
            else:
                 response_payload = {"type": "tts", "text": "Không tìm thấy bài hát này."}

        # Gửi phản hồi
        if response_payload:
            reply = {
                "message_id": message_id,
                "type": "response",
                "data": response_payload
            }
            ws.send(json.dumps(reply))
            print("--> [Sent] Đã gửi phản hồi.")

    except Exception as e:
        print(f"--> [Error] Lỗi xử lý: {e}")

# --- PHẦN KẾT NỐI WEBSOCKET ---
def on_message(ws, message):
    try:
        data = json.loads(message)
        user_text = ""
        # Xử lý các định dạng tin nhắn khác nhau của Xiaozhi
        if 'payload' in data and 'text' in data['payload']:
            user_text = data['payload']['text']
        elif 'text' in data:
            user_text = data['text']
        
        if user_text:
            print(f"\n[Robot nghe]: {user_text}")
            # Tạo luồng mới để xử lý (tránh nghẽn mạng)
            t = threading.Thread(target=process_command, args=(ws, data.get("message_id"), user_text.lower()))
            t.start()
    except Exception:
        pass

def on_error(ws, error):
    print(f"[WebSocket Error]: {error}")

def on_close(ws, close_status_code, close_msg):
    print(">>> Đã ngắt kết nối.")

def on_open(ws):
    print("\n" + "="*40)
    print(">>> KẾT NỐI THÀNH CÔNG! BỘ NÃO ĐÃ SẴN SÀNG <<<")
    print("="*40 + "\n")

def run_websocket_loop():
    while True:
        try:
            ws = websocket.WebSocketApp(MCP_ENDPOINT,
                                        on_open=on_open,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            # Ping 30s để giữ kết nối
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception:
            pass
        time.sleep(5)

# --- SERVER HTTP (CẤU HÌNH CHUẨN ĐỂ KHÔNG BỊ RENDER TẮT) ---
@app.get("/")
def keep_alive():
    return {"status": "Running"}

@app.head("/") # Quan trọng: Để trả lời Health Check của Render
def keep_alive_head():
    return {"status": "OK"}

@app.on_event("startup")
async def startup_event():
    if "wss://" in MCP_ENDPOINT:
        t = threading.Thread(target=run_websocket_loop)
        t.daemon = True
        t.start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)