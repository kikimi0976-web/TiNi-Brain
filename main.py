import os
import requests
import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

# ==============================================================================
# CẤU HÌNH THÔNG SỐ (API, THƯ MỤC & RENDER)
# ==============================================================================
# Thông tin Google Drive của bạn
API_KEY = "8b1b47c1aa1ab072ba58157a2e3888f15cb6e656"
FOLDER_ID = "1fkU37PX7J7q8hMhsjs67ohEBafdWtxNw"

# Tự động lấy URL từ hệ thống của Render (không cần cấu hình bằng tay)
RENDER_APP_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:10000")

# ==============================================================================
# HÀM LẤY DANH SÁCH NHẠC TỪ GOOGLE DRIVE
# ==============================================================================
def get_drive_music_list():
    """Gọi Google API bằng requests để lấy danh sách bài hát trong thư mục"""
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
            print("!! [DRIVE API Lỗi]:", data["error"]["message"])
            return []
        return data.get("files", [])
    except Exception as e:
        print("!! [Lỗi kết nối Drive]:", e)
        return []

# ==============================================================================
# FASTAPI ENDPOINTS (API CHO ỨNG DỤNG LILY GỌI TỚI)
# ==============================================================================

@app.get("/")
def health(): 
    return {"status": "Online", "app_url": RENDER_APP_URL}

@app.head("/")
def head(): 
    return {"status": "OK"}

# 1. API: XỬ LÝ LỆNH TÌM KIẾM HOẶC LẤY DANH SÁCH NHẠC
@app.get("/api/music")
def handle_music_request(song_name: str = ""):
    """
    Endpoint này ứng dụng Lily sẽ gọi tới.
    - Nếu song_name rỗng: Trả về danh sách nhạc.
    - Nếu song_name có nội dung: Trả về URL phát nhạc.
    """
    song_name = song_name.strip()
    files = get_drive_music_list()
    
    if not files:
        return {
            "status": "error", 
            "message": "Kho nhạc hiện đang trống hoặc chưa được chia sẻ quyền truy cập công khai."
        }
    
    if not song_name:
        # Trả về danh sách bài hát
        song_names_only = [f['name'].replace(".mp3", "") for f in files]
        song_list_text = "\n".join([f"- {name}" for name in song_names_only])
        return {
            "status": "success",
            "action": "list",
            "message": f"Dưới đây là danh sách nhạc của bạn:\n{song_list_text}\nBạn muốn tôi phát bài nào?",
            "data": song_names_only
        }
    
    else:
        # Tìm kiếm bài hát
        matched_file = None
        search_query = song_name.lower()
        
        for f in files:
            if search_query in f['name'].lower():
                matched_file = f
                break
        
        if matched_file:
            stream_url = f"{RENDER_APP_URL}/stream/{matched_file['id']}"
            clean_name = matched_file['name'].replace(".mp3", "")
            return {
                "status": "success",
                "action": "play",
                "message": f"Đang phát bài hát {clean_name} từ thư viện của bạn.",
                "stream_url": stream_url
            }
        else:
            return {
                "status": "error",
                "message": f"Không tìm thấy bài hát nào có tên '{song_name}' trong kho nhạc của bạn."
            }

# 2. API: TRUYỀN DỮ LIỆU ÂM THANH (STREAMING) CHO ESP32-S3
@app.get("/stream/{file_id}")
def stream_audio(file_id: str):
    """Lấy file nhạc từ Google Drive và stream trực tiếp về robot ESP32"""
    url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key={API_KEY}"
    req = requests.get(url, stream=True)
    
    if req.status_code != 200:
        return {"error": "Không thể lấy file từ Google Drive"}

    # Hàm generator để pipe dữ liệu âm thanh MP3
    def iterfile():
        for chunk in req.iter_content(chunk_size=8192):
            if chunk:
                yield chunk

    return StreamingResponse(iterfile(), media_type="audio/mpeg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)