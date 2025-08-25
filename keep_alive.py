from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "SweeperLeader bot is running!"

def run():
    # Render requires port >= 10000
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()