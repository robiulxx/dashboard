# app.py
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
    print("Running in demo mode without Telegram integration")
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
        print("Telethon not available - running in demo mode")
        return
    
    try:
        API_ID = os.getenv("API_ID")
        API_HASH = os.getenv("API_HASH")
        BOT_TOKEN = os.getenv("BOT_TOKEN")
        SESSION_STRING = os.getenv("SESSION_STRING", "")
        
        # Check if required environment variables are set
        if not API_ID or not API_HASH or not BOT_TOKEN:
            print("Missing Telegram API credentials - running in demo mode")
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
    
    # If telethon not available or client not initialized, return demo data
    if not TELETHON_AVAILABLE or client is None:
        return jsonify({
            "status": "success", 
            "info": get_demo_info(username)
        })
    
    try:
        result = fetch_entity_info_sync(username)
        return jsonify({"status": "success", "info": result})
    except Exception as e:
        error_msg = str(e)
        # If it's a specific Telegram error, return demo data as fallback
        if "username" in error_msg.lower() or "entity" in error_msg.lower():
            return jsonify({
                "status": "success",
                "info": get_demo_info(username)
            })
        return jsonify({"status": "error", "message": error_msg}), 500

def get_demo_info(username):
    """Return demo data when Telethon is not available"""
    # Generate some realistic-looking demo data
    demo_id = abs(hash(username)) % 1000000000
    base_date = datetime(2018, 1, 1)
    days_offset = demo_id % 2000
    created_date = base_date + timedelta(days=days_offset)
    now = datetime.utcnow()
    delta = now - created_date
    years = delta.days // 365
    months = (delta.days % 365) // 30
    days = (delta.days % 365) % 30
    
    entity_types = ["User", "Channel", "Group", "Bot"]
    entity_type = entity_types[demo_id % 4]
    
    return {
        "entity_type": entity_type,
        "name": f"Demo {entity_type} - {username.title()}",
        "username": f"@{username}",
        "id": demo_id,
        "premium": demo_id % 3 == 0,  # 33% chance of premium
        "verified": demo_id % 2 == 0,  # 50% chance of verified
        "scam": False,
        "fake": False,
        "data_center": f"DC{(demo_id % 5) + 1}",
        "status": ["online", "offline", "recently"][demo_id % 3],
        "account_created": created_date.strftime("%b %d, %Y"),
        "age": f"{years} years, {months} months, {days} days",
        "profile_pic_url": None,
        "members_count": f"{(demo_id % 10000) + 1000}" if entity_type in ["Channel", "Group"] else None,
        "admins": [
            {"name": "Admin One", "username": "@admin1"},
            {"name": "Admin Two", "username": "@admin2"}
        ] if entity_type in ["Channel", "Group"] else [],
        "demo_mode": True,
        "message": "This is demo data. Configure Telegram API for real information."
    }

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
        
        # Determine entity type
        entity_type = "User"
        if getattr(entity, "bot", False):
            entity_type = "Bot"
        elif getattr(entity, "megagroup", False):
            entity_type = "Group"
        elif getattr(entity, "broadcast", False):
            entity_type = "Channel"

        # Calculate account creation date (approximate)
        base_date = datetime(2015, 1, 1)
        if hasattr(entity, 'id'):
            days_offset = (entity.id - 100000000) // 100000
            created_date = base_date + timedelta(days=max(days_offset, 0))
            now = datetime.utcnow()
            delta = now - created_date
            years = delta.days // 365
            months = (delta.days % 365) // 30
            days = (delta.days % 365) % 30
            age_str = f"{years} years, {months} months, {days} days"
        else:
            created_date = base_date
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

        # Info dictionary
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
            "account_created": created_date.strftime("%b %d, %Y"),
            "age": age_str,
            "profile_pic_url": profile_pic_file,
            "demo_mode": False
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
        "mode": "demo" if not TELETHON_AVAILABLE or client is None else "live",
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
    print(f"Demo mode: {not TELETHON_AVAILABLE or client is None}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
