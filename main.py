import threading
import websocket
import json
import time
import os
from fastapi import FastAPI
import uvicorn
from duckduckgo_search import DDGS
import yt_dlp

app = FastAPI()

# ==============================================================================
# 1. CẤU HÌNH: DÁN TOKEN MỚI NHẤT CỦA BẠN VÀO ĐÂY
# ==============================================================================
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjczNTUwNywiYWdlbnRJZCI6MTI1MDY3MCwiZW5kcG9pbnRJZCI6ImFnZW50XzEyNTA2NzAiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzY2NzM1ODM4LCJleHAiOjE3OTgyOTM0Mzh9.30k9TPSbBpae0hsZO4UVXZnCycblFbmurT1YpmXvOPLbhG9K7bSKz6aaHfdHixJzWvV82c8l1vwQAnvjM8W5kA"

# --- CÔNG CỤ 1: TÌM NHẠC QUA YOUTUBE (CHỐNG CHẶN IP) ---
def get_youtube_audio(song_name):
    print(f"--> [Music] Đang tìm bài hát: {song_name}")
    try:
        # Bước 1: Tìm link video qua DuckDuckGo (Ẩn danh, không bị Google chặn)
        with DDGS() as ddgs:
            results = list(ddgs.videos(keywords=f"{song_name} lyrics", region="vn-vn", max_results=1))
        
        if not results:
            return None

        video_url = results[0]['content']
        
        # Bước 2: Lấy link stream audio trực tiếp qua yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'geo_bypass': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {"title": info.get('title'), "url": info.get('url')}
    except Exception as e:
        print(f"Lỗi YouTube: {e}")
        return None

# --- CÔNG CỤ 2: TÌM TIN TỨC TOÀN CẦU ---
def get_global_news(query):
    print(f"--> [News] Đang tìm tin tức cho: {query}")
    try:
        with DDGS() as ddgs:
            # Tìm kiếm tin tức mới nhất (tin tức thế giới)
            results = list(ddgs.text(keywords=query, region="wt-wt", max_results=2))
        if results:
            # Gộp các tiêu đề và nội dung tóm tắt lại
            news_summary = " . ".join([f"{r['title']}: {r['body'][:150]}" for r in results])
            return news_summary
    except Exception as e:
        print(f"Lỗi tìm tin tức: {e}")
    return None

# --- HÀM XỬ LÝ LỆNH (CHẠY TRÊN LUỒNG RIÊNG) ---
def process_command(ws, message_id, user_text):
    try:
        user_text_lower = user_text.lower()
        response_data = None

        # A. Xử lý yêu cầu nhạc
        music_keywords = ["mở", "hát", "nghe", "phát", "bật", "chơi", "bài", "nhạc"]
        if any(k in user_text_lower for k in music_keywords) and len(user_text_lower) > 5:
            # Lọc bỏ từ thừa
            clean_name = user_text_lower
            for k in music_keywords + ["cho tôi", "đi", "em"]:
                clean_name = clean_name.replace(k, "")
            
            song_res = get_youtube_audio(clean_name.strip())
            if song_res:
                response_data = {
                    "type": "audio",
                    "url": song_res['url'],
                    "text": f"Đang phát bài: {song_res['title']}"
                }

        # B. Xử lý yêu cầu tin tức
        elif any(k in user_text_lower for k in ["tin tức", "thời sự", "thông tin về", "biết gì về"]):
            news_res = get_global_news(user_text_lower)
            if news_res:
                response_data = {
                    "type": "tts",
                    "text": f"Đây là tin tức mình tìm được: {news_res}"
                }

        # Gửi phản hồi lại cho Robot
        if response_data:
            reply = {
                "message_id": message_id,
                "type": "response",
                "data": response_data
            }
            ws.send(json.dumps(reply))
            print("--> [Sent] Đã phản hồi cho Robot.")

    except Exception as e:
        print(f"Lỗi logic: {e}")

# --- QUẢN LÝ KẾT NỐI WEBSOCKET ---
def on_message(ws, message):
    try:
        data = json.loads(message)
        # Debug: In tin nhắn thô để kiểm tra nếu cần
        # print(f"DEBUG RAW: {message}")

        user_text = ""
        # Kiểm tra mọi cấu trúc JSON có thể có từ Xiaozhi
        if 'payload' in data and 'text' in data['payload']:
            user_text = data['payload']['text']
        elif 'text' in data:
            user_text = data['text']
        
        if user_text:
            print(f"\n[Robot nghe]: {user_text}")
            # Chạy xử lý trong luồng riêng để giữ WebSocket không bị timeout
            t = threading.Thread(target=process_command, args=(ws, data.get("message_id"), user_text))
            t.start()
    except: pass

def on_error(ws, error): print(f"[WS Error]: {error}")
def on_close(ws, status, msg): print(">>> Mất kết nối. Đang chờ thử lại...")
def on_open(ws):
    print("\n>>> KẾT NỐI THÀNH CÔNG! ĐANG KÍCH HOẠT BỘ NÃO...")
    # Gửi gói tin mồi nhử để khai báo tính năng với Cloud
    init_msg = {
        "type": "init",
        "version": "1.0",
        "capabilities": ["audio_stream", "text_search"]
    }
    ws.send(json.dumps(init_msg))
    print(">>> ĐÃ GỬI TÍN HIỆU KHAI BÁO TÍNH NĂNG! <<<")

def run_ws_loop():
    while True:
        try:
            # Kết nối với Heartbeat 30s đúng chuẩn kỹ thuật
            ws = websocket.WebSocketApp(MCP_ENDPOINT, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except: pass
        time.sleep(5) # Chờ 5s trước khi kết nối lại để tránh bị Blacklist

# --- SERVER HTTP (CHỐNG SHUTDOWN TRÊN RENDER) ---
@app.get("/")
def home(): return {"status": "Online"}

@app.head("/") # Phản hồi lệnh HEAD để Render không báo lỗi 405
def head(): return {"status": "OK"}

@app.on_event("startup")
async def startup():
    if "wss://" in MCP_ENDPOINT:
        threading.Thread(target=run_ws_loop, daemon=True).start()

if __name__ == "__main__":
    # Render yêu cầu cổng được cấu hình qua biến môi trường hoặc mặc định 10000
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)