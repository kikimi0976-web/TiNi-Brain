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
MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjczNTUwNywiYWdlbnRJZCI6MTI1MDY3MCwiZW5kcG9pbnRJZCI6ImFnZW50XzEyNTA2NzAiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzY2NzczNDUyLCJleHAiOjE3OTgzMzEwNTJ9.yVZ6Pi7ojLVQQ5UYwDyLkC-YUhIfb2_GuJf1uw4a6_ZD3FUQfkZpBriYT1BGykACxLeZ8NOMq4Sx3Ann2oLWiw"

# --- [TOOLS] CÁC GIÁC QUAN ---
def tool_web_search(query):
    print(f">>> [TRUMAN SEARCHING]: {query}", flush=True)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, region="wt-wt", max_results=3))
            if not results: return "Không tìm thấy thông tin mới nhất."
            return " . ".join([f"{r['title']}: {r['body'][:200]}" for r in results])
    except Exception as e:
        return f"Lỗi internet: {str(e)}"

def tool_play_music(song_name):
    print(f">>> [TRUMAN MUSIC]: {song_name}", flush=True)
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
        return f"Lỗi âm nhạc: {str(e)}"

# --- [CORE] ĐIỀU PHỐI VÀ ĐĂNG KÝ CÔNG CỤ (MCP) ---
def on_message(ws, message):
    try:
        # In dữ liệu thô để theo dõi log thực tế
        print(f"\n[DỮ LIỆU NHẬN ĐƯỢC]: {message}", flush=True)
        
        data = json.loads(message)
        method = data.get("method")
        # Lấy đúng ID để phản hồi chính xác cho từng gói tin
        msg_id = data.get("id") if data.get("id") is not None else data.get("message_id")

        # 1. PHẢN HỒI PING (GIỮ KẾT NỐI - CÓ PRINT ĐỂ BẠN THẤY)
        if method == "ping":
            ws.send(json.dumps({"id": msg_id, "jsonrpc": "2.0", "result": {}}))
            print(f">>> [PONG] Đã phản hồi nhịp đập cho gói ID: {msg_id}", flush=True)
            return

        # 2. PHẢN HỒI KHỞI TẠO (CHỈ KHAI BÁO KHẢ NĂNG)
        if method == "initialize":
            reply = {
                "id": msg_id,
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {} # Chỉ khai báo có hỗ trợ, Robot sẽ hỏi danh sách sau
                    },
                    "serverInfo": {"name": "Truman-Brain", "version": "1.0"}
                }
            }
            ws.send(json.dumps(reply))
            print(f">>> [INIT OK] Đã xác nhận khởi tạo gói ID: {msg_id}", flush=True)
            return

        # 3. PHẢN HỒI DANH SÁCH TOOLS (BƯỚC QUYẾT ĐỊNH ĐỘ ỔN ĐỊNH)
        if method == "tools/list":
            reply = {
                "id": msg_id,
                "jsonrpc": "2.0",
                "result": {
                    "tools": [
                        {"name": "web_search", "description": "Tìm kiếm tin tức trực tuyến"},
                        {"name": "play_music", "description": "Tìm và phát nhạc YouTube"}
                    ]
                }
            }
            ws.send(json.dumps(reply))
            print(f">>> [LIST OK] Đã gửi danh sách công cụ cho gói ID: {msg_id}", flush=True)
            return

        # 4. XỬ LÝ GỌI CÔNG CỤ (CALL_TOOL)
        if data.get("type") == "call_tool" or method == "tools/call":
            params = data.get("params", {})
            tool_name = data.get("name") or params.get("name")
            args = data.get("arguments") or params.get("arguments") or {}
            
            print(f">>> [EXECUTING] Robot gọi tool: {tool_name}", flush=True)

            if tool_name == "web_search":
                res = tool_web_search(args.get("query"))
                ws.send(json.dumps({"type": "tool_result", "message_id": msg_id, "data": {"text": res}}))
            elif tool_name == "play_music":
                res = tool_play_music(args.get("query"))
                # Trả về link audio để Robot phát ngay
                if isinstance(res, dict):
                    ws.send(json.dumps({"type": "tool_result", "message_id": msg_id, 
                                        "data": {"type": "audio", "url": res['url'], "text": f"Đang mở: {res['title']}"}}))
                else:
                    ws.send(json.dumps({"type": "tool_result", "message_id": msg_id, "data": {"text": res}}))

    except Exception as e:
        print(f"!! Lỗi xử lý lệnh: {str(e)}", flush=True)
        
def on_open(ws):
    # Chỉ in log để biết đã thông mạng, KHÔNG gửi gì thêm tại đây
    print(">>> ĐÃ MỞ KẾT NỐI. ĐỢI ROBOT GỬI LỆNH KHỞI TẠO...", flush=True)

def run_ws():
    while True:
        try:
            ws = websocket.WebSocketApp(MCP_ENDPOINT, on_open=on_open, on_message=on_message)
            ws.run_forever()
        except: time.sleep(5)

@app.get("/")
def health(): return {"status": "Online"}

@app.head("/") # Sửa lỗi 405 cho UptimeRobot
def head(): return {"status": "OK"}

@app.on_event("startup")
async def startup(): threading.Thread(target=run_ws, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)