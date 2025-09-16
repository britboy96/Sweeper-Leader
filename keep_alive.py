from flask import Flask
from threading import Thread
import asyncio
from main import bot, run_backscan, system_channel

app = Flask('')

@app.route('/')
def home():
    return "I'm alive", 200

@app.route('/healthping')
def healthping():
    loop = asyncio.get_event_loop()
    # Run backscan
    asyncio.run_coroutine_threadsafe(run_backscan(), loop)
    # Post bot status to logs channel
    async def announce():
        ch = bot.get_channel(1143238719541891154)
        if ch:
            await ch.send("✅ Bot is up and responding\n🏓 Pong!")
    asyncio.run_coroutine_threadsafe(announce(), loop)
    return "Health check triggered", 200

def run():
    app.run(host="0.0.0.0", port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
