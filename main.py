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
# CẤU HÌNH: DÁN TOKEN MỚI CỦA BẠN VÀO DƯỚI ĐÂY
# Lưu ý: Token thường hết hạn sau 24h hoặc khi bị spam kết nối. 
# Nếu lỗi đỏ, hãy vào xiaozhi.me lấy token mới.
# ==============================================================================
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjczNTUwNywiYWdlbnRJZCI6MTI1MDY3MCwiZW5kcG9pbnRJZCI6ImFnZW50XzEyNTA2NzAiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzY2Njg5MzE1LCJleHAiOjE3OTgyNDY5MTV9.DFcMDjJcIysAJE_OZ8tVbZ1V4LTvYvkzmWsTjtJoxQ7yc1kVuRh1YnZ0vJ4yHeiQ8UzaDGx_RFqUN7qPbF2e9A"


# --- HÀM 1: TÌM NHẠC THÔNG MINH (CHỐNG CHẶN IP) ---
def get_youtube_audio(song_name):
    print(f"--> [Search] Đang tìm: {song_name}...")
    try:
        # BƯỚC 1: Dùng DuckDuckGo tìm link Video (Né chặn tìm kiếm của YouTube)
        # Thêm từ khóa "lyrics" hoặc "official audio" để tìm bài chuẩn
        search_query = f"{song_name} lyrics youtube"
        results = DDGS().videos(
            keywords=search_query,
            region="vn-vn",
            safesearch="off",
            max_results=1
        )
        
        if not results:
            print("--> Không tìm thấy video nào qua DuckDuckGo.")
            return None

        video_url = results[0]['content']
        video_title = results[0]['title']
        print(f"--> [Found] Tìm thấy: {video_title}")

        # BƯỚC 2: Dùng yt_dlp để lấy link âm thanh trực tiếp
        ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            # Giả lập trình duyệt để tránh lỗi 403
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {"title": info.get('title'), "url": info.get('url')}

    except Exception as e:
        print(f"--> [Error] Lỗi lấy nhạc: {e}")
        return None

# --- HÀM 2: XỬ LÝ LỆNH TRONG LUỒNG RIÊNG (ĐỂ KHÔNG BỊ DISCONNECT) ---
def process_command(ws, message_id, user_text):
    try:
        response_payload = None

        # --- LOGIC XỬ LÝ NHẠC ---
        if any(k in user_text for k in ["mở bài", "nghe bài", "phát bài", "hát bài", "bật bài"]):
            # Lọc bỏ từ khóa để lấy tên bài hát
            song_name = user_text
            for k in ["mở bài", "nghe bài", "phát bài", "hát bài", "bật bài"]:
                song_name = song_name.replace(k, "")
            
            song_name = song_name.strip()
            song_data = get_youtube_audio(song_name)
            
            if song_data:
                response_payload = {
                    "type": "audio",
                    "url": song_data['url'],
                    "text": f"Đang phát: {song_data['title']}"
                }
            else:
                 response_payload = {
                    "type": "tts",
                    "text": "Xin lỗi, mình không tìm thấy bài hát này."
                }

        # --- LOGIC XỬ LÝ TIN TỨC (VÍ DỤ) ---
        elif "tin tức" in user_text:
            response_payload = {
                "type": "tts",
                "text": "Chức năng tin tức đang được bảo trì để tối ưu hóa tìm kiếm."
            }

        # --- GỬI PHẢN HỒI ---
        if response_payload:
            reply = {
                "message_id": message_id,
                "type": "response",
                "data": response_payload
            }
            # Gửi tin nhắn qua WebSocket (Thread safe)
            ws.send(json.dumps(reply))
            print("--> [Sent] Đã gửi phản hồi về Robot.")

    except Exception as e:
        print(f"--> [Error] Lỗi xử lý lệnh: {e}")

# --- PHẦN KẾT NỐI WEBSOCKET ---
def on_message(ws, message):
    try:
        data = json.loads(message)
        
        # Lấy nội dung text
        user_text = ""
        if 'payload' in data and 'text' in data['payload']:
            user_text = data['payload']['text']
        elif 'text' in data:
            user_text = data['text']
        
        if not user_text: return

        user_text = user_text.lower()
        print(f"\n[Robot nghe]: {user_text}")

        # QUAN TRỌNG: Tạo luồng mới để xử lý, không làm chặn kết nối chính
        # Nếu không có cái này, khi đang tìm nhạc 5s, server sẽ tưởng bạn chết và ngắt kết nối
        t = threading.Thread(target=process_command, args=(ws, data.get("message_id"), user_text))
        t.start()

    except Exception as e:
        print(f"Lỗi đọc tin nhắn: {e}")

def on_error(ws, error):
    print(f"[WebSocket Error]: {error}")

def on_close(ws, close_status_code, close_msg):
    print(">>> Đã ngắt kết nối. Đang chờ tái kết nối...")

def on_open(ws):
    print("\n" + "="*50)
    print(">>> KẾT NỐI THÀNH CÔNG! BỘ NÃO ĐÃ SẴN SÀNG <<<")
    print("="*50 + "\n")

# --- VÒNG LẶP KẾT NỐI VĨNH CỬU ---
def run_websocket_loop():
    while True:
        try:
            print(f"Đang kết nối đến Server...")
            ws = websocket.WebSocketApp(MCP_ENDPOINT,
                                        on_open=on_open,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            
            # Ping mỗi 30s, Timeout 10s -> Giữ kết nối cực chắc
            ws.run_forever(ping_interval=30, ping_timeout=10)
        except Exception as e:
            print(f"Lỗi khởi tạo: {e}")
        
        print("Đang thử lại sau 5 giây...")
        time.sleep(5)

def start_background_service():
    t = threading.Thread(target=run_websocket_loop)
    t.daemon = True # Tự tắt khi chương trình chính tắt
    t.start()

# --- SERVER HTTP (ĐỂ RENDER KHÔNG TẮT) ---
@app.get("/")
def keep_alive():
    return {"status": "Robot Brain is Running"}
# --- Thêm đoạn này vào dưới hàm keep_alive ---
@app.head("/")
def keep_alive_head():
    return {"status": "OK"}
# Tự động chạy khi khởi động
@app.on_event("startup")
async def startup_event():
    if "wss://" in MCP_ENDPOINT:
        start_background_service()
    else:
        print("!!! CẢNH BÁO: CHƯA CÓ TOKEN !!!")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)