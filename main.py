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
        print(f"\n[DỮ LIỆU NHẬN ĐƯỢC]: {message}", flush=True)
        data = json.loads(message)
        method = data.get("method")
        msg_id = data.get("id") if data.get("id") is not None else data.get("message_id")

        # 1. PHẢN HỒI PING (GIỮ KẾT NỐI)
        if method == "ping":
            ws.send(json.dumps({"id": msg_id, "jsonrpc": "2.0", "result": {}}))
            print(f">>> [PONG] Đã phản hồi nhịp đập ID: {msg_id}", flush=True)
            return

        # 2. XỬ LÝ THÔNG BÁO HOÀN TẤT KHỞI TẠO (SỬA LỖI VÒNG LẶP 60S)
        if method == "notifications/initialized":
            print(">>> [READY] Handshake hoàn tất! Robot đã sẵn sàng.", flush=True)
            # Gửi một gói tin trống để "chào" Robot và reset timer của Render
            ws.send(json.dumps({"jsonrpc": "2.0", "method": "notifications/ready", "params": {}}))
            return

        # 3. PHẢN HỒI INITIALIZE (KHAI BÁO NĂNG LỰC)
        if method == "initialize":
            reply = {"id": msg_id, "jsonrpc": "2.0", "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "logging": {}}, 
                "serverInfo": {"name": "Truman-Brain", "version": "1.0"}
            }}
            ws.send(json.dumps(reply))
            print(f">>> [INIT OK] Phản hồi ID: {msg_id}", flush=True)
            return

        # 4. PHẢN HỒI TOOLS/LIST (DÙNG SCHEMA BẠN ĐÃ CẬP NHẬT)
        if method == "tools/list":
            reply = {"id": msg_id, "jsonrpc": "2.0", "result": {"tools": [
                {
                    "name": "web_search", "description": "Tìm kiếm tin tức trực tuyến",
                    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                },
                {
                    "name": "play_music", "description": "Tìm và phát nhạc YouTube",
                    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
                }
            ]}}
            ws.send(json.dumps(reply))
            print(f">>> [LIST OK] Đã gửi danh sách cho ID: {msg_id}", flush=True)
            return
        # 5. XỬ LÝ GỌI CÔNG CỤ (THÊM MỚI ĐỂ PHẢN HỒI ID)
        if method == "tools/call":
            params = data.get("params", {})
            tool_name = params.get("name")
            args = params.get("arguments", {})
            query = args.get("query")
            
            print(f">>> [DETECTED] Robot gọi tool: {tool_name} -> '{query}'", flush=True)

            res_text = ""
            if tool_name == "web_search":
                res_text = tool_web_search(query)
            elif tool_name == "play_music":
                res_music = tool_play_music(query)
                res_text = f"Đang mở nhạc: {res_music['title']}" if isinstance(res_music, dict) else res_music

            # PHẢN HỒI KẾT QUẢ THEO CHUẨN JSON-RPC
            response = {
                "jsonrpc": "2.0",
                "id": msg_id,  # Trả về đúng ID: 498 của Robot
                "result": {
                    "content": [{"type": "text", "text": res_text}]
                }
            }
            ws.send(json.dumps(response))
            print(f">>> [SUCCESS] Đã gửi kết quả cho gói ID: {msg_id}", flush=True)
            return

    except Exception as e:
        print(f"!! Lỗi: {str(e)}", flush=True)

def on_open(ws):
    # Chỉ in log để biết đã thông mạng, KHÔNG gửi gì thêm tại đây
    print(">>> ĐÃ MỞ KẾT NỐI. ĐỢI ROBOT GỬI LỆNH KHỞI TẠO...", flush=True)

def run_ws():
    while True:
        try:
            ws = websocket.WebSocketApp(
                MCP_ENDPOINT, 
                on_open=on_open, 
                on_message=on_message
            )
            # QUAN TRỌNG: Thêm ping_interval=30 để giữ kết nối trên Render
            # Điều này sẽ gửi nhịp tim mỗi 30s, trước khi Render kịp ngắt ở 60s.
            ws.run_forever(ping_interval=30, ping_timeout=10) 
        except Exception as e:
            print(f"!! Đang kết nối lại sau 10s do lỗi: {e}", flush=True)
            time.sleep(10)

@app.get("/")
def health(): return {"status": "Online"}

@app.head("/") # Sửa lỗi 405 cho UptimeRobot
def head(): return {"status": "OK"}

@app.on_event("startup")
async def startup(): threading.Thread(target=run_ws, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)