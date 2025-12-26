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
        print(f"\n[DỮ LIỆU THÔ]: {message}", flush=True) # Hiện log ngay lập tức
        data = json.loads(message)
        
        # Chỉ xử lý nếu Robot yêu cầu gọi Tool (JSON-RPC)
        if data.get("type") == "call_tool":
            tool_name = data.get("name")
            args = data.get("arguments", {})
            msg_id = data.get("message_id")

            if tool_name == "web_search":
                result = tool_web_search(args.get("query"))
                reply = {"type": "tool_result", "message_id": msg_id, "data": {"text": result}}
                ws.send(json.dumps(reply))
            
            elif tool_name == "play_music":
                res = tool_play_music(args.get("query"))
                if isinstance(res, dict):
                    reply = {"type": "tool_result", "message_id": msg_id, 
                             "data": {"type": "audio", "url": res['url'], "text": f"Đang phát: {res['title']}"}}
                else:
                    reply = {"type": "tool_result", "message_id": msg_id, "data": {"text": res}}
                ws.send(json.dumps(reply))

    except Exception as e:
        print(f"[Error]: {str(e)}", flush=True)

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