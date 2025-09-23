from flask import Flask
from threading import Thread
import asyncio

app = Flask(__name__)

@app.route('/')
def home():
    return "I am alive!", 200

@app.route('/healthz')
def healthz():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(main.run_self_maintenance(), loop)
        else:
            loop.run_until_complete(main.run_self_maintenance())
    except Exception as e:
        return f"ERROR: {e}", 500
    return "✅ Self-maintenance complete", 200

def run():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()
