from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ SweeperLeader bot is alive and running!"

def run():
    port = int(os.environ.get("PORT", 10000))  # Render gives us this env var
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    run()
