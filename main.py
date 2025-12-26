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

# URL kết nối từ phía Robot
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjczNTUwNywiYWdlbnRJZCI6MTI1MDY3MCwiZW5kcG9pbnRJZCI6ImFnZW50XzEyNTA2NzAiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzY2NzY4MjU3LCJleHAiOjE3OTgzMjU4NTd9.p92b9mHiYlETDrPBXY8yhuqHVvZ6EG8Y9b4-83BOMZ_mtrkXdv9d7MEe_3Szr02wKLqnwxWfFEJF2_WOzvcQjA"

# --- [TOOLS] CÔNG CỤ TÌM KIẾM TIN TỨC ---
def tool_web_search(query):
    print(f">>> [Executing] Đang tìm tin tức cho: {query}", flush=True)
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, region="wt-wt", max_results=3)]
            return " . ".join([f"{r['title']}: {r['body'][:150]}" for r in results])
    except Exception as e:
        return f"Lỗi tìm kiếm: {str(e)}"

# --- [TOOLS] CÔNG CỤ PHÁT NHẠC TOÀN CẦU ---
def tool_play_music(song_name):
    print(f">>> [Executing] Đang tìm nhạc: {song_name}", flush=True)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.videos(f"{song_name} audio", max_results=1))
            if not results: return "Không tìm thấy bài hát."
            video_url = results[0]['content']
        
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {"url": info['url'], "title": info['title']}
    except Exception as e:
        return f"Lỗi phát nhạc: {str(e)}"

# --- [CORE] BỘ ĐIỀU PHỐI LỆNH (DISPATCHER) ---
def on_message(ws, message):
    try:
        # 1. Ép in log thô để theo dõi trên Render
        print(f"\n[DỮ LIỆU NHẬN ĐƯỢC]: {message}", flush=True)
        
        data = json.loads(message)
        
        # 2. Kiểm tra xem Robot có yêu cầu gọi công cụ (call_tool) không
        if data.get("type") == "call_tool":
            tool_name = data.get("name")
            arguments = data.get("arguments", {})
            message_id = data.get("message_id") # Cần ID để Robot biết phản hồi này cho lệnh nào

            print(f">>> [DISPATCHER] Robot yêu cầu dùng: {tool_name}", flush=True)

            # 3. Điều phối đến công cụ Tìm kiếm (Bước 3)
            if tool_name == "web_search":
                query = arguments.get("query")
                search_result = tool_web_search(query) # Gọi hàm từ Bước 3
                
                # Gửi kết quả về cho AI tóm tắt
                reply = {
                    "type": "tool_result",
                    "message_id": message_id,
                    "data": {"text": search_result}
                }
                ws.send(json.dumps(reply))

            # 4. Điều phối đến công cụ Phát nhạc (Bước 4)
            elif tool_name == "play_music":
                song_query = arguments.get("query")
                music_res = tool_play_music(song_query) # Gọi hàm từ Bước 4
                
                if isinstance(music_res, dict):
                    # Trả về link audio để Robot phát ngay lập tức
                    reply = {
                        "type": "tool_result",
                        "message_id": message_id,
                        "data": {
                            "type": "audio",
                            "url": music_res['url'],
                            "text": f"Đang mở bài: {music_res['title']}"
                        }
                    }
                else:
                    reply = {"type": "tool_result", "message_id": message_id, "data": {"text": music_res}}
                
                ws.send(json.dumps(reply))

    except Exception as e:
        print(f"!! Lỗi điều phối lệnh: {str(e)}", flush=True)

def on_open(ws):
    print(">>> KẾT NỐI THÀNH CÔNG! KHAI BÁO TÍNH NĂNG...", flush=True)
    # Gửi gói tin Init để Robot biết bạn có những "quyền năng" gì
    init_msg = {
        "type": "init",
        "capabilities": {
            "tools": [
                {"name": "web_search", "description": "Tìm kiếm tin tức và thông tin trực tuyến"},
                {"name": "play_music", "description": "Tìm và phát nhạc từ YouTube toàn cầu"}
            ]
        }
    }
    ws.send(json.dumps(init_msg))

def run_ws():
    while True:
        try:
            ws = websocket.WebSocketApp(MCP_ENDPOINT, on_open=on_open, on_message=on_message)
            ws.run_forever(ping_interval=30) # Giữ kết nối luôn sống
        except: time.sleep(5)

@app.get("/")
def health(): return {"status": "Truman Brain is Live"}

@app.on_event("startup")
async def startup(): threading.Thread(target=run_ws, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
from duckduckgo_search import DDGS

def tool_web_search(query):
    """
    Hàm thực hiện tra cứu thông tin trực tuyến.
    """
    print(f">>> [TRUMAN SEARCHING]: {query}", flush=True)
    try:
        with DDGS() as ddgs:
            # Tra cứu văn bản với vùng tìm kiếm toàn cầu (wt-wt)
            results = list(ddgs.text(query, region="wt-wt", max_results=3))
            
            if not results:
                return "Không tìm thấy thông tin liên quan."
            
            # Gộp các tiêu đề và nội dung tóm tắt để gửi lại cho AI
            summary = []
            for r in results:
                summary.append(f"Tiêu đề: {r['title']}\nNội dung: {r['body'][:200]}")
            
            return "\n---\n".join(summary)
            
    except Exception as e:
        print(f"!! Lỗi khi tra cứu: {e}", flush=True)
        return f"Xin lỗi, mình gặp trục trặc khi truy cập internet: {str(e)}"

import yt_dlp
from duckduckgo_search import DDGS

def tool_play_music(song_name):
    """
    Hàm trích xuất link nhạc stream trực tiếp từ YouTube.
    """
    print(f">>> [TRUMAN MUSIC]: Đang tìm bài: {song_name}", flush=True)
    try:
        # Bước 1: Tìm URL video qua DuckDuckGo Video
        with DDGS() as ddgs:
            # Thêm từ khóa 'audio' để lọc kết quả chất lượng tốt nhất
            results = list(ddgs.videos(f"{song_name} audio", max_results=1))
            if not results:
                return "Xin lỗi, mình không tìm thấy bài hát này."
            video_url = results[0]['content']

        # Bước 2: Dùng yt-dlp để lấy stream URL trực tiếp
        ydl_opts = {
            'format': 'bestaudio/best', # Chỉ lấy phần âm thanh tốt nhất
            'noplaylist': True,
            'quiet': True,
            'geo_bypass': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            # Trả về URL stream để Robot có thể phát ngay
            return {
                "url": info['url'], 
                "title": info.get('title', 'Music Stream'),
                "type": "audio"
            }
            
    except Exception as e:
        print(f"!! Lỗi phát nhạc: {e}", flush=True)
        return f"Gặp sự cố khi truy cập kho nhạc: {str(e)}"