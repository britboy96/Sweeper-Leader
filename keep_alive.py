# keep_alive.py
from flask import Flask
from threading import Thread
import requests
import os

app = Flask('')

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")  # set this in Render env vars
GUILD_ID = os.getenv("GUILD_ID")              # set this too

@app.route('/')
def home():
    return "I'm alive"

@app.route('/health')
def health():
    # Trigger your /health slash command silently
    url = f"https://discord.com/api/v10/interactions"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    payload = {
        "type": 2,  # application command
        "application_id": APPLICATION_ID,
        "guild_id": GUILD_ID,
        "channel_id": os.getenv("LOG_CHANNEL_ID", ""),  # optional
        "data": {"name": "health", "type": 1}
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception as e:
        print("Health trigger failed:", e)
    return "Triggered /health"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
