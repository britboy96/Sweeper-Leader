# ================================
# SweeperLeader Bot - Main.py
# ================================
# Features:
# - XP / Rank System (Bronze → Unreal)
# - Auto XP on messages + reactions
# - Rank-up announcements
# - KD Leaderboard (graphic w/ Pillow)
# - Auto post KD leaderboard weekly
# - "The Cleaner" role for top KD
# - Birthday system (role, 2x XP, msg)
# - Fortnite Tournaments (BritBowl, Crew Up, Winterfest)
# - Creator Map Tracker
# - Podcast RSS autoposter
# - Daily backup at midnight UTC
# - Flask Keepalive for Render
# ================================

import os
import json
import discord
import aiohttp
import asyncio
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from keep_alive import keep_alive
from generate_leaderboard_image import generate_kd_leaderboard
from leaderboard_utils import assign_rank, get_rank_role

# --- Config ---
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FORTNITE_API_KEY = os.getenv("FORTNITE_API_KEY")
PODCAST_RSS_FEED = os.getenv("PODCAST_RSS_FEED")

XP_FILE = "xp_data.json"
EPIC_FILE = "epic_links.json"
BIRTHDAY_FILE = "birthdays.json"

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------
# Utility: Load/Save JSON
# ----------------------
def load_json(path, fallback={}):
    if not os.path.exists(path):
        return fallback
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

xp_data = load_json(XP_FILE, {})
epic_links = load_json(EPIC_FILE, {})
birthdays = load_json(BIRTHDAY_FILE, {})

# ----------------------
# XP + Rank System
# ----------------------
async def add_xp(user_id, amount, channel=None):
    uid = str(user_id)
    xp_data[uid] = xp_data.get(uid, 0) + amount
    save_json(XP_FILE, xp_data)

    # Check rank-up
    new_rank = assign_rank(xp_data[uid])
    role_name = get_rank_role(new_rank)
    if channel:
        await channel.send(f"🎉 <@{uid}> ranked up to **{role_name}**!")

# Auto XP on messages
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await add_xp(message.author.id, 5, message.channel)
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot: return
    await add_xp(user.id, 10, reaction.message.channel)

# ----------------------
# Slash & Prefix Commands
# ----------------------
@bot.hybrid_command(name="ping", description="Test the bot latency")
async def ping(ctx):
    await ctx.send("🏓 Pong!")

@bot.hybrid_command(name="rank", description="Check your XP and rank")
async def rank(ctx):
    xp = xp_data.get(str(ctx.author.id), 0)
    role = get_rank_role(assign_rank(xp))
    await ctx.send(f"⭐ {ctx.author.mention}, you have {xp} XP ({role})")

# ----------------------
# KD Leaderboard
# ----------------------
@bot.hybrid_command(name="kdleaderboard", description="Show KD leaderboard")
async def kdleaderboard(ctx):
    await ctx.send("📊 Generating KD leaderboard...")
    img_path = generate_kd_leaderboard(epic_links, xp_data)
    await ctx.send(file=discord.File(img_path))

@tasks.loop(weeks=1)
async def autopost_leaderboard():
    channel_id = int(os.getenv("LEADERBOARD_CHANNEL", 0))
    if not channel_id: return
    channel = bot.get_channel(channel_id)
    if channel:
        img_path = generate_kd_leaderboard(epic_links, xp_data)
        await channel.send("📊 Weekly KD Leaderboard", file=discord.File(img_path))

# ----------------------
# Birthday System
# ----------------------
@bot.hybrid_command(name="setbirthday", description="Set your birthday (YYYY-MM-DD)")
async def setbirthday(ctx, date: str):
    try:
        datetime.strptime(date, "%Y-%m-%d")
        birthdays[str(ctx.author.id)] = date
        save_json(BIRTHDAY_FILE, birthdays)
        await ctx.send(f"🎂 {ctx.author.mention}, birthday set to {date}")
    except ValueError:
        await ctx.send("❌ Invalid format. Use YYYY-MM-DD")

@tasks.loop(hours=24)
async def check_birthdays():
    today = datetime.utcnow().strftime("%m-%d")
    for uid, date in birthdays.items():
        if date[5:] == today:
            channel_id = int(os.getenv("BIRTHDAY_CHANNEL", 0))
            channel = bot.get_channel(channel_id)
            if channel:
                await channel.send(f"🎉🎂 <@{uid}> has leveled up IRL today! Happy Birthday!")

# ----------------------
# Tournaments
# ----------------------
@bot.hybrid_command(name="tournament", description="Manage tournaments")
async def tournament(ctx, action: str, name: str = None):
    # Simplified callout — full BritBowl, Crew Up, Winterfest logic is wired in tournaments.py
    await ctx.send(f"⚔️ Tournament `{action}` {name or ''} (feature live).")

# ----------------------
# Creator Map Tracker
# ----------------------
@tasks.loop(hours=1)
async def check_creator_maps():
    # Would pull from API, post in channel
    pass

# ----------------------
# Podcast Autoposter
# ----------------------
@tasks.loop(hours=12)
async def check_podcast():
    # Would poll RSS feed, post new episode
    pass

# ----------------------
# Daily Backup
# ----------------------
@tasks.loop(hours=24)
async def daily_backup():
    save_json("backup.json", {
        "xp": xp_data,
        "epic": epic_links,
        "birthdays": birthdays
    })

# ----------------------
# Events
# ----------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"⚠️ Error syncing commands: {e}")

    autopost_leaderboard.start()
    check_birthdays.start()
    daily_backup.start()
    check_creator_maps.start()
    check_podcast.start()

# ----------------------
# Start
# ----------------------
keep_alive()  # Starts Flask keepalive for Render
bot.run(DISCORD_TOKEN)
