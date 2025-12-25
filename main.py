from fastapi import FastAPI, Request
from duckduckgo_search import DDGS
import yt_dlp
import requests

app = FastAPI()

# --- CẤU HÌNH ---
# Hàm tìm kiếm nhạc từ YouTube (Mạnh mẽ nhất)
def get_youtube_audio(song_name):
    print(f"--> Đang tìm bài hát: {song_name}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
        'geo_bypass': True, # Vượt tường lửa quốc gia
        'socket_timeout': 10,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{song_name}", download=False)
            if 'entries' in info:
                video = info['entries'][0]
            else:
                video = info
            return {
                "title": video.get('title'),
                "url": video.get('url') # Link trực tiếp robot đọc được
            }
    except Exception as e:
        print(f"Lỗi YouTube: {e}")
        return None

# Hàm tra cứu tin tức quốc tế (DuckDuckGo)
def search_global_news(query):
    print(f"--> Đang tra cứu tin tức: {query}")
    try:
        # region='wt-wt' là toàn cầu, không bị giới hạn địa lý
        results = DDGS().text(keywords=query, region='wt-wt', max_results=1)
        if results:
            return results[0]['body']
    except Exception as e:
        print(f"Lỗi Search: {e}")
    return None

# --- API XỬ LÝ CHÍNH ---
@app.get("/")
def keep_alive():
    return {"status": "Ti Ni Brain is Online"}

@app.post("/mcp")
async def handle_request(request: Request):
    data = await request.json()
    user_text = data.get("text", "").lower()
    print(f"Lệnh nhận được: {user_text}")

    # 1. XỬ LÝ PHÁT NHẠC (Ưu tiên cao nhất)
    # Cú pháp: "Mở bài [tên bài]", "Nghe bài [tên bài]", "Phát bài [tên bài]"
    music_keywords = ["mở bài", "nghe bài", "phát bài", "hát bài"]
    if any(k in user_text for k in music_keywords):
        song_name = user_text
        for k in music_keywords:
            song_name = song_name.replace(k, "")
        song_name = song_name.strip()

        if song_name:
            song_data = get_youtube_audio(song_name)
            if song_data:
                return {
                    "text": f"Đã tìm thấy {song_data['title']}. Đang phát...",
                    "type": "audio",
                    "url": song_data['url']
                }
            else:
                return {"text": "Xin lỗi, tôi không tải được bài hát này lúc này.", "type": "tts"}

    # 2. XỬ LÝ TRA CỨU / TIN TỨC / KIẾN THỨC
    # Cú pháp: "Tin tức...", "Là gì...", "Ở đâu...", "Như thế nào..."
    search_keywords = ["tin tức", "là gì", "ở đâu", "như thế nào", "tìm kiếm", "biết gì về"]
    if any(k in user_text for k in search_keywords):
        result = search_global_news(user_text)
        if result:
            return {
                "text": f"Theo thông tin tìm được: {result}",
                "type": "tts"
            }
        else:
            return {"text": "Tôi không tìm thấy thông tin liên quan.", "type": "tts"}

    # 3. MẶC ĐỊNH (Nếu không hiểu lệnh)
    return {
        "text": "Tôi chưa hiểu. Hãy nói 'Mở bài' cộng tên bài hát, hoặc hỏi tin tức.",
        "type": "tts"
    }