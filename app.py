from flask import Flask, render_template, request, jsonify, send_from_directory
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
import asyncio
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# Environment variables
API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Bot token use

# Flask app
app = Flask(__name__)
PHOTO_FOLDER = "static/photos"
os.makedirs(PHOTO_FOLDER, exist_ok=True)

# ThreadPoolExecutor for async calls
executor = ThreadPoolExecutor(max_workers=5)

# Telethon client, bot_token দিয়ে start
client = TelegramClient("anon", API_ID, API_HASH).start(bot_token=BOT_TOKEN)
loop = asyncio.get_event_loop()  # Event loop

# Routes
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/static/photos/<filename>")
def photos(filename):
    return send_from_directory(PHOTO_FOLDER, filename)

@app.route("/api/getinfo", methods=["POST"])
def get_info():
    data = request.json
    username = data.get("username")
    if not username:
        return jsonify({"status": "error", "message": "No username provided"}), 400

    # Async function call safely in Flask
    future = executor.submit(lambda: asyncio.run(fetch_entity_info(username)))
    try:
        result = future.result()
        return jsonify({"status": "success", "info": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Async function to fetch entity info
async def fetch_entity_info(username):
    entity = await client.get_entity(username)

    # Determine entity type
    entity_type = "User"
    if getattr(entity, "bot", False):
        entity_type = "Bot"
    elif getattr(entity, "megagroup", False):
        entity_type = "Group"
    elif getattr(entity, "broadcast", False) or (getattr(entity, "username", False) and getattr(entity, "id", None) < 0):
        entity_type = "Channel"

    # Approximate account creation date
    base_id = 100000000
    base_date = datetime(2015, 1, 1)
    days_offset = (entity.id - base_id) // 100000
    created_date = base_date + timedelta(days=days_offset)
    now = datetime.utcnow()
    delta = now - created_date
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = (delta.days % 365) % 30
    age_str = f"{years} years, {months} months, {days} days"

    # Profile photo
    profile_pic_file = None
    if getattr(entity, "photo", None):
        filename = f"{entity.id}.jpg"
        profile_pic_path = os.path.join(PHOTO_FOLDER, filename)
        await client.download_profile_photo(entity, file=profile_pic_path)
        profile_pic_file = f"/static/photos/{filename}"

    # Info dictionary
    info = {
        "entity_type": entity_type,
        "name": getattr(entity, "title", None) or f"{getattr(entity, 'first_name', '')} {getattr(entity, 'last_name', '')}".strip(),
        "username": f"@{getattr(entity, 'username', None)}" if getattr(entity, "username", None) else None,
        "id": entity.id,
        "premium": getattr(entity, "premium", False),
        "verified": getattr(entity, "verified", False),
        "scam": getattr(entity, "scam", False),
        "fake": getattr(entity, "fake", False),
        "data_center": "Unknown",
        "status": str(getattr(entity, "status", "Unknown")).replace("UserStatus", "").strip(),
        "account_created": created_date.strftime("%b %d, %Y"),
        "age": age_str,
        "profile_pic_url": profile_pic_file
    }

    # Channel / Group info
    if entity_type in ["Channel", "Group"]:
        full = await client(GetFullChannelRequest(entity))
        info["members_count"] = getattr(full.full_chat, "participants_count", "Unknown") if hasattr(full, "full_chat") else getattr(full.chats[0], "participants_count", "Unknown")
        admins = []
        for participant in getattr(full.full_chat, "participants", []):
            if participant.admin_rights or participant.rank:
                try:
                    user_entity = await client.get_entity(participant.user_id)
                    admins.append({
                        "name": f"{user_entity.first_name or ''} {user_entity.last_name or ''}".strip(),
                        "username": f"@{user_entity.username}" if user_entity.username else None
                    })
                except:
                    continue
        info["admins"] = admins

    return info

# Run Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
