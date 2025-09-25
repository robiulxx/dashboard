# app.py - FIXED TEMPLATE PATH
from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import threading
import asyncio
from datetime import datetime, timedelta
import traceback

# Try to import Telethon with fallback
try:
    from telethon import TelegramClient
    from telethon.tl.functions.channels import GetFullChannelRequest
    from telethon.tl.types import Channel, User, Chat
    from telethon.sessions import StringSession
    TELETHON_AVAILABLE = True
except ImportError as e:
    print(f"Telethon import error: {e}")
    TELETHON_AVAILABLE = False

app = Flask(__name__, template_folder='templates')
PHOTO_FOLDER = "static/photos"
os.makedirs(PHOTO_FOLDER, exist_ok=True)

# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)

# Global client instance
client = None

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
        
        print(f"API_ID: {API_ID}")
        print(f"API_HASH: {bool(API_HASH)}")
        print(f"BOT_TOKEN: {bool(BOT_TOKEN)}")
        
        # Check if required environment variables are set
        if not API_ID or not API_HASH or not BOT_TOKEN:
            print("Missing Telegram API credentials - running in demo mode")
            return
        
        API_ID = int(API_ID)
        
        # Create session
        if not SESSION_STRING or SESSION_STRING.strip() == "":
            print("Creating new session...")
            client = TelegramClient(StringSession(), API_ID, API_HASH)
        else:
            print("Using existing session...")
            client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
        
        # Start the client
        client.start(bot_token=BOT_TOKEN)
        
        # Save new session if created
        if not SESSION_STRING or SESSION_STRING.strip() == "":
            new_session_string = client.session.save()
            print(f"NEW_SESSION_STRING: {new_session_string}")
        
        print("Telegram client initialized successfully")
        
    except Exception as e:
        print(f"Error initializing Telegram client: {e}")
        client = None

# Initialize client
initialize_client()

@app.route("/")
def home():
    try:
        return render_template("index.html")
    except Exception as e:
        return f"""
        <html>
            <head><title>Telegram Info Dashboard</title></head>
            <body>
                <h1>Telegram Info Dashboard</h1>
                <p>Template file is being generated. Please refresh in a moment.</p>
                <p>Error: {str(e)}</p>
            </body>
        </html>
        """

@app.route("/static/photos/<filename>")
def photos(filename):
    return send_from_directory(PHOTO_FOLDER, filename)

@app.route("/api/getinfo", methods=["POST"])
def get_info():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data provided"}), 400
            
        username = data.get("username", "").lstrip('@').strip()
        
        if not username:
            return jsonify({"status": "error", "message": "No username provided"}), 400
        
        print(f"Fetching info for: {username}")
        
        # If telethon not available or client not initialized, return demo data
        if not TELETHON_AVAILABLE or client is None:
            print("Using demo mode")
            return jsonify({
                "status": "success", 
                "info": get_demo_info(username)
            })
        
        result = fetch_entity_info_sync(username)
        return jsonify({"status": "success", "info": result})
        
    except Exception as e:
        print(f"Error in get_info: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def get_demo_info(username):
    """Return demo data when Telethon is not available"""
    return {
        "entity_type": "User",
        "name": f"Demo User",
        "username": f"@{username}",
        "id": 123456789,
        "premium": False,
        "verified": False,
        "scam": False,
        "fake": False,
        "data_center": "Unknown",
        "status": "online",
        "account_created": "Not available in demo",
        "age": "Unknown",
        "profile_pic_url": None,
        "demo_mode": True,
        "message": "Configure Telegram API credentials for real information"
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
    try:
        # Get entity
        entity = await client.get_entity(username)
        print(f"Entity found: {type(entity)}")
        
        # Determine entity type
        entity_type = "User"
        if hasattr(entity, 'bot') and entity.bot:
            entity_type = "Bot"
        elif hasattr(entity, 'megagroup') and entity.megagroup:
            entity_type = "Group" 
        elif hasattr(entity, 'broadcast') and entity.broadcast:
            entity_type = "Channel"
        
        # Get name
        name = "Unknown"
        if hasattr(entity, 'title') and entity.title:
            name = entity.title
        elif hasattr(entity, 'first_name') or hasattr(entity, 'last_name'):
            first_name = getattr(entity, 'first_name', '')
            last_name = getattr(entity, 'last_name', '')
            name = f"{first_name} {last_name}".strip()
        
        # Get username
        username_value = getattr(entity, 'username', None)
        username_display = f"@{username_value}" if username_value else "No username"
        
        # Basic info
        info = {
            "entity_type": entity_type,
            "name": name,
            "username": username_display,
            "id": getattr(entity, 'id', 'Unknown'),
            "premium": getattr(entity, 'premium', False),
            "verified": getattr(entity, 'verified', False),
            "scam": getattr(entity, 'scam', False),
            "fake": getattr(entity, 'fake', False),
            "data_center": "Unknown",
            "status": "Unknown",
            "account_created": "Not available via API",
            "age": "Unknown",
            "profile_pic_url": None
        }
        
        # Try to get status
        if hasattr(entity, 'status'):
            status_str = str(entity.status)
            if 'online' in status_str.lower():
                info["status"] = "Online"
            elif 'offline' in status_str.lower():
                info["status"] = "Offline"
            else:
                info["status"] = status_str.replace("UserStatus", "").title()
        
        # For channels/groups, get additional info
        if entity_type in ["Channel", "Group"]:
            try:
                full = await client(GetFullChannelRequest(entity))
                if hasattr(full, 'full_chat') and hasattr(full.full_chat, 'participants_count'):
                    info["members_count"] = full.full_chat.participants_count
                else:
                    info["members_count"] = "Unknown"
                    
                info["admins"] = []
            except Exception as e:
                info["members_count"] = "Unknown"
                info["admins"] = []
        
        return info
        
    except Exception as e:
        print(f"Error in fetch_entity_info: {e}")
        raise Exception(f"Telegram API error: {str(e)}")

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy", 
        "telethon_available": TELETHON_AVAILABLE,
        "client_initialized": client is not None,
        "template_folder": os.path.exists('templates')
    })

@app.route('/test')
def test_route():
    return jsonify({
        "message": "Server is running!",
        "timestamp": datetime.utcnow().isoformat()
    })

# Create a simple index.html if it doesn't exist
def create_index_html():
    index_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telegram Info Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .container { background: #f5f5f5; padding: 30px; border-radius: 10px; }
        input, button { padding: 10px; margin: 5px; font-size: 16px; }
        #result { margin-top: 20px; padding: 15px; background: white; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Telegram Info Dashboard</h1>
        <input type="text" id="username" placeholder="Enter username">
        <button onclick="getInfo()">Get Info</button>
        <div id="result"></div>
    </div>

    <script>
        async function getInfo() {
            const username = document.getElementById("username").value;
            const response = await fetch("/api/getinfo", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({username})
            });
            const data = await response.json();
            document.getElementById("result").innerHTML = JSON.stringify(data, null, 2);
        }
    </script>
</body>
</html>
    """
    
    with open('templates/index.html', 'w') as f:
        f.write(index_content)
    print("Created index.html template")

# Create template on startup
if not os.path.exists('templates/index.html'):
    create_index_html()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    print(f"Telethon available: {TELETHON_AVAILABLE}")
    print(f"Client initialized: {client is not None}")
    
    app.run(host="0.0.0.0", port=port, debug=False)
