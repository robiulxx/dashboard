# app.py - FINAL FIXED VERSION
from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import threading
import asyncio
from datetime import datetime, timedelta
import sys

# Try to import Telethon with fallback
try:
    from telethon import TelegramClient
    from telethon.tl.functions.channels import GetFullChannelRequest
    from telethon.sessions import StringSession
    TELETHON_AVAILABLE = True
except ImportError as e:
    print(f"Telethon import error: {e}")
    TELETHON_AVAILABLE = False

app = Flask(__name__)
PHOTO_FOLDER = "static/photos"
os.makedirs(PHOTO_FOLDER, exist_ok=True)

# Global client instance
client = None
client_lock = threading.Lock()

def initialize_client():
    """Initialize Telegram client properly"""
    global client
    
    if not TELETHON_AVAILABLE:
        print("Telethon not available")
        return
    
    try:
        API_ID = os.getenv("API_ID")
        API_HASH = os.getenv("API_HASH")
        BOT_TOKEN = os.getenv("BOT_TOKEN")
        SESSION_STRING = os.getenv("SESSION_STRING", "")
        
        # Check if required environment variables are set
        if not API_ID or not API_HASH or not BOT_TOKEN:
            print("Missing Telegram API credentials")
            return
        
        API_ID = int(API_ID)
        
        with client_lock:
            if client is None:
                # Create new session if SESSION_STRING is not provided
                if not SESSION_STRING or SESSION_STRING.strip() == "":
                    print("Creating new session...")
                    client = TelegramClient(StringSession(), API_ID, API_HASH)
                else:
                    print("Using existing session...")
                    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
                
                # Start the client
                client.start(bot_token=BOT_TOKEN)
                
                # Save the new session string if it was created
                if not SESSION_STRING or SESSION_STRING.strip() == "":
                    new_session_string = client.session.save()
                    print(f"NEW_SESSION_STRING: {new_session_string}")
                    print("Please set this SESSION_STRING in your environment variables")
                
                print("Telegram client initialized successfully")
                
    except Exception as e:
        print(f"Error initializing Telegram client: {e}")
        client = None

# Initialize client when app starts
initialize_client()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/static/photos/<filename>")
def photos(filename):
    return send_from_directory(PHOTO_FOLDER, filename)

@app.route("/api/getinfo", methods=["POST"])
def get_info():
    data = request.json
    username = data.get("username", "").lstrip('@').strip()
    
    if not username:
        return jsonify({"status": "error", "message": "No username provided"}), 400
    
    # If telethon not available or client not initialized, return error
    if not TELETHON_AVAILABLE or client is None:
        return jsonify({
            "status": "error", 
            "message": "Telegram API not configured. Please check environment variables."
        }), 500
    
    try:
        result = fetch_entity_info_sync(username)
        return jsonify({"status": "success", "info": result})
    except Exception as e:
        error_msg = str(e)
        return jsonify({"status": "error", "message": error_msg}), 500

def fetch_entity_info_sync(username):
    """Synchronous wrapper for the async function"""
    global client
    
    if client is None:
        raise Exception("Telegram client not initialized")
    
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(fetch_entity_info(username))
        return result
    except Exception as e:
        raise Exception(f"Failed to fetch info: {str(e)}")
    finally:
        loop.close()

async def fetch_entity_info(username):
    """Async function to fetch entity info using Telethon"""
    global client
    
    try:
        # Get entity
        entity = await client.get_entity(username)
        
        # CORRECT ENTITY TYPE DETECTION
        entity_type = "User"
        if hasattr(entity, 'bot') and entity.bot:
            entity_type = "Bot"
        elif hasattr(entity, 'megagroup') and entity.megagroup:
            entity_type = "Group"
        elif hasattr(entity, 'broadcast') and entity.broadcast:
            entity_type = "Channel"

        # CORRECT ACCOUNT CREATION DATE
        created_date = "Not available via API"
        age_str = "Unknown"

        # Download profile photo
        profile_pic_file = None
        if getattr(entity, "photo", None):
            try:
                filename = f"{entity.id}_{int(datetime.now().timestamp())}.jpg"
                profile_pic_path = os.path.join(PHOTO_FOLDER, filename)
                await client.download_profile_photo(entity, file=profile_pic_path)
                if os.path.exists(profile_pic_path):
                    profile_pic_file = f"/static/photos/{filename}"
            except Exception as e:
                print(f"Error downloading profile photo: {e}")

        # Basic info
        name = getattr(entity, "title", None) 
        if not name:
            first_name = getattr(entity, "first_name", "")
            last_name = getattr(entity, "last_name", "")
            name = f"{first_name} {last_name}".strip()
        
        username_value = getattr(entity, "username", None)
        if username_value:
            username_display = f"@{username_value}"
        else:
            username_display = None

        # Info dictionary - CORRECTED
        info = {
            "entity_type": entity_type,
            "name": name or "Unknown",
            "username": username_display,
            "id": getattr(entity, "id", "Unknown"),
            "premium": getattr(entity, "premium", False),
            "verified": getattr(entity, "verified", False),
            "scam": getattr(entity, "scam", False),
            "fake": getattr(entity, "fake", False),
            "data_center": "Unknown",
            "status": str(getattr(entity, "status", "Unknown")).replace("UserStatus", "").strip(),
            "account_created": created_date,
            "age": age_str,
            "profile_pic_url": profile_pic_file
        }

        # Channel/Group specific info
        if entity_type in ["Channel", "Group"]:
            try:
                full = await client(GetFullChannelRequest(entity))
                info["members_count"] = getattr(full.full_chat, "participants_count", "Unknown")
                
                # Get admins
                admins = []
                participants = getattr(full.full_chat, "participants", [])
                for participant in participants:
                    if getattr(participant, "admin_rights", None) or getattr(participant, "rank", None):
                        try:
                            user_entity = await client.get_entity(participant.user_id)
                            admin_name = f"{getattr(user_entity, 'first_name', '')} {getattr(user_entity, 'last_name', '')}".strip()
                            admin_username = getattr(user_entity, "username", None)
                            admins.append({
                                "name": admin_name or "Unknown",
                                "username": f"@{admin_username}" if admin_username else None
                            })
                        except Exception as e:
                            continue
                info["admins"] = admins
            except Exception as e:
                info["members_count"] = "Unknown"
                info["admins"] = []

        return info
        
    except Exception as e:
        raise Exception(f"Telegram API error: {str(e)}")

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "service": "Telegram Info Dashboard",
        "telethon_available": TELETHON_AVAILABLE,
        "client_initialized": client is not None,
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/test')
def test_route():
    """Test route to verify the app is working"""
    return jsonify({
        "message": "Telegram Info Dashboard is running!",
        "mode": "live" if TELETHON_AVAILABLE and client is not None else "not configured",
        "timestamp": datetime.utcnow().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Telegram Info Dashboard on port {port}")
    print(f"Telethon available: {TELETHON_AVAILABLE}")
    print(f"Client initialized: {client is not None}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
