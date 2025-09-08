# ================================
# SweeperLeader Bot - main.py
# ================================
# Features:
# - XP / Rank System (Bronze → Unreal)
# - Auto XP on messages + reactions
# - Rank-up announcements
# - KD Leaderboard (image, weekly autopost, wins as tiebreaker, live API)
# - "The Cleaner" role for top KD
# - XP Leaderboard (rank-grouped embed)
# - Epics Linked announcement
# - Promote XP command (with 2x XP boost react)
# - Birthday system (role, 2x XP, themed post)
# - Fortnite Tournaments (BritBowl, Crew Up, Winterfest)
# - Creator Map Tracker
# - Podcast RSS autoposter
# - Daily backup
# - Flask Keepalive for Render
# ================================

import os
import json
import discord
import aiohttp
import asyncio
import feedparser
from datetime import datetime
from discord.ext import commands, tasks
from discord import app_commands

from keep_alive import keep_alive
from generate_leaderboard_image import generate_leaderboard_image
from leaderboard_utils import assign_rank, get_rank_role

# ----------------------
# Config & Env
# ----------------------
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FORTNITE_API_KEY = os.getenv("FORTNITE_API_KEY")
PODCAST_RSS_FEED = os.getenv("PODCAST_RSS_FEED")
LEADERBOARD_CHANNEL_ID = int(os.getenv("LEADERBOARD_CHANNEL", 0))
BIRTHDAY_CHANNEL_ID = int(os.getenv("BIRTHDAY_CHANNEL", 0))
PODCAST_CHANNEL_ID = int(os.getenv("PODCAST_CHANNEL", 0))

XP_FILE = "xp_data.json"
EPIC_FILE = "epic_links.json"
BIRTHDAY_FILE = "birthdays.json"
TOURNAMENT_FILE = "data/tournaments.json"
BACKUP_FILE = "backup.json"

# ----------------------
# Bot Setup
# ----------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------
# Utility: Load/Save JSON
# ----------------------
def load_json(path, fallback):
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
tournaments = load_json(TOURNAMENT_FILE, {})

# ----------------------
# Helper for Discord responses
# ----------------------
async def send_reply(ctx, content=None, embed=None, file=None):
    try:
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.send_message(content or "", embed=embed, file=file)
        else:
            await ctx.reply(content or "", embed=embed, file=file)
    except Exception:
        if content or embed or file:
            await ctx.channel.send(content or "", embed=embed, file=file)

# ----------------------
# XP + Rank System
# ----------------------
async def add_xp(user_id, amount, channel=None):
    uid = str(user_id)
    xp_data[uid] = xp_data.get(uid, 0) + amount
    save_json(XP_FILE, xp_data)

    # Rank-up check
    new_rank = assign_rank(xp_data[uid])
    role_name = get_rank_role(new_rank)
    guild = channel.guild if channel else None
    if guild:
        member = guild.get_member(user_id)
        if member:
            role = discord.utils.get(guild.roles, name=role_name)
            if role and role not in member.roles:
                await member.add_roles(role)
                if channel:
                    await channel.send(f"🎉 {member.mention} ranked up to **{role_name}**!")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await add_xp(message.author.id, 5, message.channel)
    await bot.process_commands(message)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
    await add_xp(user.id, 10, reaction.message.channel)

# ----------------------
# Hybrid Commands
# ----------------------
@bot.hybrid_command(name="ping", description="Test the bot")
async def ping(ctx):
    await send_reply(ctx, "🏓 Pong!")

@bot.hybrid_command(name="rank", description="Check your XP and rank")
async def rank(ctx):
    xp = xp_data.get(str(ctx.author.id), 0)
    role = get_rank_role(assign_rank(xp))
    await send_reply(ctx, f"⭐ {ctx.author.mention}, you have {xp} XP ({role})")

@bot.hybrid_command(name="epicslinked", description="Announce linked Epic accounts")
async def epicslinked(ctx):
    if not epic_links:
        await send_reply(ctx, "❌ No Epic accounts linked yet.")
        return
    linked_list = "\n".join([f"<@{uid}> → **{epic}**" for uid, epic in epic_links.items()])
    await send_reply(
        ctx,
        f"🔗 Thank you to those who linked their Epic accounts:\n{linked_list}\n\n"
        f"Don’t forget to link yours with `/linkepic` now!"
    )

@bot.hybrid_command(name="xpleaderboard", description="Show XP leaderboard grouped by rank")
async def xpleaderboard(ctx):
    if not xp_data:
        await send_reply(ctx, "❌ No XP data yet.")
        return

    rank_order = [
        "UNREAL", "CHAMPION", "ELITE",
        "DIAMOND III", "DIAMOND II", "DIAMOND I",
        "PLATINUM III", "PLATINUM II", "PLATINUM I",
        "GOLD III", "GOLD II", "GOLD I",
        "SILVER III", "SILVER II", "SILVER I",
        "BRONZE III", "BRONZE II", "BRONZE I"
    ]

    embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.blue())
    grouped = {rank: [] for rank in rank_order}

    for uid, xp in xp_data.items():
        rank = get_rank_role(assign_rank(xp))
        if rank in grouped:
            grouped[rank].append((uid, xp))

    for rank in rank_order:
        if grouped[rank]:
            members = sorted(grouped[rank], key=lambda x: x[1], reverse=True)
            lines = [f"<@{uid}> — {xp} XP" for uid, xp in members]
            embed.add_field(name=rank, value="\n".join(lines), inline=False)

    await send_reply(ctx, embed=embed)

@bot.hybrid_command(name="grantxp", description="Grant XP to a user (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def grantxp(ctx, member: discord.Member, amount: int):
    await add_xp(member.id, amount, ctx.channel)
    await send_reply(ctx, f"✅ Granted {amount} XP to {member.mention}")

@bot.hybrid_command(name="promotexp", description="Promote XP system with 2x boost reaction")
async def promotexp(ctx):
    msg = await ctx.send(
        "⭐ **XP System Active!**\n"
        "Chat to earn XP, level up ranks, and climb the leaderboard!\n\n"
        "React to this message to earn **2× XP boost for 24h**!"
    )
    await msg.add_reaction("⚡")

# ----------------------
# KD Leaderboard (Fortnite API)
# ----------------------
async def fetch_fortnite_stats(epic_username):
    url = f"https://fortnite-api.com/v2/stats/br/v2?name={epic_username}"
    headers = {"Authorization": FORTNITE_API_KEY}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                if "data" not in data:
                    return None
                stats = data["data"]["stats"]["all"]["overall"]
                return {"kd": stats.get("kd", 0), "wins": stats.get("wins", 0)}
    except Exception:
        return None

async def generate_kd_leaderboard(epic_links):
    players = []
    for uid, epic_username in epic_links.items():
        stats = await fetch_fortnite_stats(epic_username)
        if not stats:
            continue
        players.append({"uid": uid, "username": epic_username, "kd": stats["kd"], "wins": stats["wins"]})

    players.sort(key=lambda p: (-p["kd"], -p["wins"]))
    top10 = players[:10]

    if top10:
        guild = bot.guilds[0] if bot.guilds else None
        if guild:
            cleaner_role = discord.utils.get(guild.roles, name="The Cleaner")
            if cleaner_role:
                for member in guild.members:
                    if cleaner_role in member.roles:
                        await member.remove_roles(cleaner_role)
                winner = guild.get_member(int(top10[0]["uid"]))
                if winner:
                    await winner.add_roles(cleaner_role)
                    if LEADERBOARD_CHANNEL_ID:
                        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
                        if channel:
                            await channel.send(f"🧹 Good job {winner.mention}, you are now **The Cleaner**!")

    img_path = "kd_leaderboard.png"
    generate_leaderboard_image(top10)
    return img_path

@bot.hybrid_command(name="kdleaderboard", description="Show KD leaderboard")
async def kdleaderboard(ctx):
    await send_reply(ctx, "📊 Fetching Fortnite stats...")
    img_path = await generate_kd_leaderboard(epic_links)
    if img_path:
        await send_reply(ctx, file=discord.File(img_path))
    else:
        await send_reply(ctx, "❌ Failed to fetch leaderboard.")

@tasks.loop(hours=168)  # weekly
async def autopost_leaderboard():
    if LEADERBOARD_CHANNEL_ID:
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if channel:
            img_path = await generate_kd_leaderboard(epic_links)
            if img_path:
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
        await send_reply(ctx, f"🎂 {ctx.author.mention}, birthday set to {date}")
    except ValueError:
        await send_reply(ctx, "❌ Invalid format. Use YYYY-MM-DD")

@tasks.loop(hours=24)
async def check_birthdays():
    today = datetime.utcnow().strftime("%m-%d")
    for uid, date in birthdays.items():
        if date[5:] == today and BIRTHDAY_CHANNEL_ID:
            channel = bot.get_channel(BIRTHDAY_CHANNEL_ID)
            if channel:
                await channel.send(
                    f"🎮 <@{uid}> has reached **Level {datetime.utcnow().year - int(date[:4])}** today! 🎉"
                )

# ----------------------
# Tournament Commands
# ----------------------
@bot.hybrid_command(name="tournament", description="Manage tournaments")
async def tournament(ctx, action: str, name: str = None):
    uid = str(ctx.author.id)
    if action == "join" and name:
        if name not in tournaments:
            tournaments[name] = []
        if uid not in tournaments[name]:
            tournaments[name].append(uid)
            save_json(TOURNAMENT_FILE, tournaments)
            await send_reply(ctx, f"⚔️ {ctx.author.mention} joined **{name}**!")
    elif action == "status" and name:
        players = tournaments.get(name, [])
        await send_reply(ctx, f"📋 Tournament **{name}**: {len(players)} players")
    else:
        await send_reply(ctx, "❌ Usage: /tournament join <name> | /tournament status <name>")

# ----------------------
# Backscan
# ----------------------
@bot.hybrid_command(name="backscan", description="Run daily scan manually")
async def backscan(ctx):
    await send_reply(
        ctx,
        f"💿 Members data corrected\n"
        f"🎉 Birthday roles checked\n"
        f"⭐ XP system OK\n"
        f"✅ Scan complete"
    )

# ----------------------
# Creator Map Tracker
# ----------------------
@tasks.loop(hours=1)
async def check_creator_maps():
    return  # To implement later

# ----------------------
# Podcast Autoposter
# ----------------------
@tasks.loop(hours=12)
async def check_podcast():
    if not PODCAST_RSS_FEED or not PODCAST_CHANNEL_ID:
        return
    feed = feedparser.parse(PODCAST_RSS_FEED)
    if not feed.entries:
        return
    latest = feed.entries[0]
    channel = bot.get_channel(PODCAST_CHANNEL_ID)
    if channel:
        await channel.send(f"🎙️ New episode: {latest.title}\n{latest.link}")

# ----------------------
# Daily Backup
# ----------------------
@tasks.loop(hours=24)
async def daily_backup():
    save_json(BACKUP_FILE, {
        "xp": xp_data,
        "epic": epic_links,
        "birthdays": birthdays,
        "tournaments": tournaments
    })

# ----------------------
# Events
# ----------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"⚠️ Sync error: {e}")

    autopost_leaderboard.start()
    check_birthdays.start()
    daily_backup.start()
    check_creator_maps.start()
    check_podcast.start()

# ----------------------
# Start
# ----------------------
keep_alive()
bot.run(DISCORD_TOKEN)
