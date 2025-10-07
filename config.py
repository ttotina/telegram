import os

# === Telegram API (replace with your values) ===
API_ID = 27370476
API_HASH = "1b9a1be4f8027ee3bb3b1805cf30881d"




# Media directory (project folder's media/)
BASE_DIR = os.path.dirname(__file__)
MEDIA_DIR = os.path.join(BASE_DIR, "media")

# Auto-load media lists at runtime
def _list_media(exts):
    try:
        return [os.path.join(MEDIA_DIR, f) for f in os.listdir(MEDIA_DIR)
                if f.lower().endswith(tuple(exts))]
    except Exception:
        return []

PHOTOS = _list_media((".jpg", ".jpeg", ".png"))
VIDEOS = _list_media((".mp4", ".mov", ".mkv"))