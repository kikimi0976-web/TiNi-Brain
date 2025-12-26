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

# URL kết nối từ phía Robot (Hãy đảm bảo Token còn hạn)
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=YOUR_TOKEN_HERE"

# --- [TOOLS] 1. CÔNG CỤ TÌM KIẾM TIN TỨC ---
def tool_web_search(query):
    print(f">>> [Executing] Đang tra cứu DuckDuckGo: {query}", flush=True)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="wt-wt", max_results=3))
            if not results: return "Không tìm thấy thông tin mới nhất."
            return " . ".join([f"{r['title']}: {r['body'][:150]}" for r in results])
    except Exception as e:
        return f"Lỗi tìm kiếm: {str(e)}"

# --- [TOOLS] 2. CÔNG CỤ PHÁT NHẠC TOÀN CẦU ---
def tool_play_music(song_name):
    print(f">>> [Executing] Đang tìm link nhạc YouTube: {song_name}", flush=True)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.videos(f"{song_name} audio", max_results=1))
            if not results: return "Không tìm thấy bài hát yêu cầu."
            video_url = results[0]['content']
        
        ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return {"url": info['url'], "title": info['title']}
    except Exception as e:
        return f"Lỗi phát nhạc: {str(e)}"

# --- [CORE] BỘ ĐIỀU PHỐI LỆNH (MCP DISPATCHER) ---
def on_message(ws, message):
    try:
        print(f"\n[DỮ LIỆU NHẬN ĐƯỢC]: {message}", flush=True)
        data = json.loads(message)
        method = data.get("method")
        msg_id = data.get("id") or data.get("message_id")

        # A. Xử lý yêu cầu khởi tạo (Initialize) - CỰC KỲ QUAN TRỌNG
        if method == "initialize":
            reply = {
                "id": msg_id,
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "Truman-Brain", "version": "1.0"}
                }
            }
            ws.send(json.dumps(reply))
            print(">>> [XÁC NHẬN] Đã phản hồi gói tin khởi tạo!", flush=True)

        # B. Xử lý yêu cầu gọi công cụ (call_tool hoặc method: tools/call)
        elif data.get("type") == "call_tool" or method == "tools/call":
            tool_name = data.get("name") or data.get("params", {}).get("name")
            args = data.get("arguments") or data.get("params", {}).get("arguments") or {}

            print(f">>> [DISPATCHER] Robot gọi tool: {tool_name}", flush=True)

            if tool_name == "web_search":
                res = tool_web_search(args.get("query"))
                reply = {"type": "tool_result", "message_id": msg_id, "data": {"text": res}}
                ws.send(json.dumps(reply))

            elif tool_name == "play_music":
                res = tool_play_music(args.get("query"))
                if isinstance(res, dict):
                    reply = {"type": "tool_result", "message_id": msg_id, 
                             "data": {"type": "audio", "url": res['url'], "text": f"Đang mở: {res['title']}"}}
                else:
                    reply = {"type": "tool_result", "message_id": msg_id, "data": {"text": res}}
                ws.send(json.dumps(reply))

    except Exception as e:
        print(f"!! Lỗi logic: {str(e)}", flush=True)

def on_open(ws):
    print(">>> KẾT NỐI THÀNH CÔNG! KHAI BÁO TÍNH NĂNG...", flush=True)
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
            ws.run_forever(ping_interval=30)
        except: time.sleep(5)

@app.get("/")
def health(): return {"status": "Truman Brain Live"}

@app.head("/") # Fix lỗi 405 cho UptimeRobot
def head(): return {"status": "OK"}

@app.on_event("startup")
async def startup(): threading.Thread(target=run_ws, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)