import os
import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

# ==============================================================================
# CẤU HÌNH (Lưu ý: Chuỗi 8b1b47... bạn cung cấp có vẻ là mã Git Commit Hash, 
# không phải Google API Key. Key chuẩn thường bắt đầu bằng chữ "AIza...". 
# Nếu code chạy báo lỗi, hãy lấy lại API Key trên Google Cloud).
# ==============================================================================
API_KEY = "AIzaSyA2U1dJq1yoNNQ2DQKEbGLxu-3Hxul31k0"
FOLDER_ID = "1fkU37PX7J7q8hMhsjs67ohEBafdWtxNw"
RENDER_APP_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://tini-brain.onrender.com")

def get_drive_music_list():
    url = "https://www.googleapis.com/drive/v3/files"
    params = {
        "q": f"'{FOLDER_ID}' in parents and trashed = false",
        "fields": "files(id, name)",
        "key": API_KEY
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "error" in data:
            print("!! [Lỗi Drive API]:", data["error"]["message"])
            return []
        return data.get("files", [])
    except Exception as e:
        print("!! [Lỗi kết nối]:", e)
        return []

@app.get("/")
def health(): 
    return {"status": "Online"}

@app.head("/")
def head(): 
    return {"status": "OK"}

# API Giao tiếp chính với ứng dụng Lily (Hỗ trợ cả GET và POST)
@app.api_route("/api/music", methods=["GET", "POST"])
async def handle_music(request: Request):
    search_term = ""
    
    # 1. Dò tìm tham số bài hát từ ứng dụng Lily gửi sang
    if request.query_params.get("song_name"):
        search_term = request.query_params.get("song_name")
    
    if request.method == "POST":
        try:
            body = await request.json()
            search_term = body.get("song_name", search_term)
        except:
            pass
            
    search_term = search_term.strip().lower()
    files = get_drive_music_list()
    
    if not files:
        return {"action": "error", "message": "Kho nhạc trống hoặc cấu hình API Key sai."}
        
    # Kịch bản 1: Không có tên bài hát cụ thể -> Đọc danh sách nhạc
    if not search_term or search_term in ["none", "null"]:
        song_names = [f['name'].replace(".mp3", "") for f in files]
        return {
            "message": f"Danh sách bài hát hiện có: {', '.join(song_names)}. Bạn muốn nghe bài nào?",
            "action": {"type": "none"}
        }
        
    # Kịch bản 2: Tìm và phát nhạc
    matched_file = next((f for f in files if search_term in f['name'].lower()), None)
    
    if matched_file:
        stream_url = f"{RENDER_APP_URL}/stream/{matched_file['id']}"
        clean_name = matched_file['name'].replace(".mp3", "")
        return {
            "message": f"Đang phát bài hát {clean_name}",
            "action": {"type": "play_audio", "url": stream_url}
        }
    else:
        return {"message": f"Không tìm thấy bài hát nào có tên {search_term}."}

# API Stream truyền dữ liệu âm thanh trực tiếp cho Loa
@app.get("/stream/{file_id}")
def stream_audio(file_id: str):
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={API_KEY}"
    req = requests.get(url, stream=True)
    if req.status_code != 200:
        return {"error": "Lỗi lấy tệp từ Google Drive"}
        
    def iterfile():
        for chunk in req.iter_content(chunk_size=8192):
            if chunk: yield chunk
            
    return StreamingResponse(iterfile(), media_type="audio/mpeg")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)