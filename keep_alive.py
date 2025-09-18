from flask import Flask
from threading import Thread
import requests
import os

app = Flask('')

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
APPLICATION_ID = os.getenv("APPLICATION_ID")  # add in Render env vars
GUILD_ID = os.getenv("GUILD_ID")              # add in Render env vars

@app.route('/')
def home():
    return "I am alive!"

@app.route('/ping')
def ping():
    # Call Discord API to trigger /health command
    url = f"https://discord.com/api/v10/applications/{APPLICATION_ID}/guilds/{GUILD_ID}/commands"
    headers = {"Authorization": f"Bot {DISCORD_TOKEN}"}

    # Look for the /health command
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        cmds = r.json()
        health_cmd = next((c for c in cmds if c["name"] == "health"), None)
        if health_cmd:
            # Trigger the command directly
            invoke_url = f"https://discord.com/api/v10/interactions"
            payload = {
                "type": 2,
                "application_id": APPLICATION_ID,
                "guild_id": GUILD_ID,
                "data": {"id": health_cmd["id"], "name": "health", "type": 1}
            }
            requests.post(invoke_url, headers=headers, json=payload)

    return "Pinged /health"

def run():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()