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
# CẤU HÌNH NGƯỜI DÙNG (BẠN CHỈ CẦN SỬA CHỖ NÀY)
# Dán link WSS bạn lấy được từ trang xiaozhi.me vào giữa dấu ngoặc kép bên dưới
# Ví dụ: MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJIUz..."
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjczNTUwNywiYWdlbnRJZCI6MTI1MDY3MCwiZW5kcG9pbnRJZCI6ImFnZW50XzEyNTA2NzAiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzY2NjgzODU3LCJleHAiOjE3OTgyNDE0NTd9.p9WaiQzusMWmLsz77rt4c80Rj95hJc9HbuH0bCn1PVM5M8xvDFkhywOLUeLHMQH1p3PS7K24OsmnVoHC87poHw"
# ==============================================================================

# --- HÀM HỖ TRỢ: LẤY LINK YOUTUBE ---
def get_youtube_audio(song_name):
    print(f"--> Đang tìm bài hát: {song_name}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
        'geo_bypass': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{song_name}", download=False)
            video = info['entries'][0] if 'entries' in info else info
            return {"title": video.get('title'), "url": video.get('url')}
    except Exception as e:
        print(f"Lỗi YouTube: {e}")
        return None

# --- HÀM HỖ TRỢ: TRA CỨU TIN TỨC ---
def search_global_news(query):
    print(f"--> Đang tìm tin tức: {query}")
    try:
        results = DDGS().text(keywords=query, region='wt-wt', max_results=1)
        if results:
            return results[0]['body']
    except Exception:
        pass
    return None

# --- PHẦN XỬ LÝ KẾT NỐI WEBSOCKET (TRÁI TIM CỦA CÁCH 2) ---
def on_message(ws, message):
    try:
        # Giải mã tin nhắn từ Robot gửi đến
        data = json.loads(message)
        
        # Lấy nội dung câu nói của bạn
        # Cấu trúc JSON có thể khác nhau tùy phiên bản, ta kiểm tra cả 2 trường hợp
        user_text = ""
        if 'payload' in data and 'text' in data['payload']:
            user_text = data['payload']['text']
        elif 'text' in data:
            user_text = data['text']
        
        if not user_text:
            return # Không có chữ thì bỏ qua

        user_text = user_text.lower()
        print(f"Robot nghe thấy: {user_text}")

        response_payload = None

        # 1. Xử lý nghe nhạc (Gửi link Audio - Không bị kiểm duyệt)
        if any(k in user_text for k in ["mở bài", "nghe bài", "phát bài", "hát bài"]):
            song_name = user_text.replace("mở bài", "").replace("nghe bài", "").replace("phát bài", "").replace("hát bài", "").strip()
            song_data = get_youtube_audio(song_name)
            
            if song_data:
                response_payload = {
                    "type": "audio",
                    "url": song_data['url'],
                    "text": f"Đang phát {song_data['title']}"
                }

        # 2. Xử lý tin tức (Gửi Text - Có thể bị kiểm duyệt nếu nhạy cảm)
        elif any(k in user_text for k in ["tin tức", "là gì", "ở đâu", "biết gì về"]):
            news_text = search_global_news(user_text)
            if news_text:
                response_payload = {
                    "type": "tts",
                    "text": news_text
                }

        # Gửi phản hồi lại cho Robot (nếu có)
        if response_payload:
            reply = {
                "message_id": data.get("message_id"), # Quan trọng: Phải trả về đúng ID
                "type": "response",
                "data": response_payload
            }
            # Gửi đi!
            ws.send(json.dumps(reply))
            print("--> Đã gửi phản hồi về Robot")

    except Exception as e:
        print(f"Lỗi xử lý: {e}")

def on_error(ws, error):
    print(f"Lỗi kết nối: {error}")

def on_close(ws, close_status_code, close_msg):
    print("Mất kết nối với Robot. Thử lại sau 5 giây...")
    time.sleep(5)
    start_websocket_thread()

def on_open(ws):
    print(">>> KẾT NỐI THÀNH CÔNG! BỘ NÃO ĐÃ SẴN SÀNG <<<")

def run_websocket():
    # Kết nối và giữ kết nối mãi mãi
    ws = websocket.WebSocketApp(MCP_ENDPOINT,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    
    # --- DÒNG QUAN TRỌNG NHẤT Ở DƯỚI ĐÂY ---
    # ping_interval=30: Cứ 30 giây gửi tín hiệu "Tôi còn sống" một lần
    # ping_timeout=10: Nếu server không trả lời trong 10 giây thì tự kết nối lại
    ws.run_forever(ping_interval=30, ping_timeout=10)

def start_websocket_thread():
    t = threading.Thread(target=run_websocket)
    t.daemon = True
    t.start()

# --- PHẦN SERVER HTTP (ĐỂ RENDER KHÔNG TẮT) ---
@app.get("/")
def keep_alive():
    return {"status": "Hybrid Server Online"}

# Khi server khởi động, tự động chạy luồng WebSocket
@app.on_event("startup")
async def startup_event():
    if "wss://" in MCP_ENDPOINT:
        start_websocket_thread()
    else:
        print("CẢNH BÁO: Bạn chưa điền link WSS vào file main.py!")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)