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
# - Epic Linking (/linkepic & !linkepic)
# - Promote XP command (with 2x XP boost react)
# - Birthday system (role, 2x XP, themed post)
# - Fortnite Tournaments (BritBowl, Crew Up, Winterfest)
# - Creator Map Tracker (BritBoy96 default + up to 25)
# - Podcast RSS autoposter
# - Daily backup
# - Flask Keepalive for Render
# - UptimeRobot health check triggers catch-up sweep
# - Daily QOTD (kid-friendly pool from qotd.json)
# - Loot Drops (10,000 XP claimable)
# - Hidden XP Multipliers (random days)
# - Secret Challenges (monthly DM missions)
# ================================

import os
import json
import random
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
SYSTEM_CHANNEL_ID = 1140430213440876716
LOGS_CHANNEL_ID = 1143238719541891154   # For /health pings
BIRTHDAY_CHANNEL_ID = int(os.getenv("BIRTHDAY_CHANNEL", 0))
PODCAST_CHANNEL_ID = int(os.getenv("PODCAST_CHANNEL", 0))

XP_FILE = "xp_data.json"
EPIC_FILE = "epic_links.json"
BIRTHDAY_FILE = "birthdays.json"
TOURNAMENT_FILE = "data/tournaments.json"
BACKUP_FILE = "backup.json"
CREATOR_FILE = "creator_maps.json"
QOTD_FILE = "qotd.json"

# ----------------------
# Bot Setup
# ----------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------
# Utility
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
creator_maps = load_json(CREATOR_FILE, {"tracked": ["BritBoy96"], "posted": {}})
qotd_data = load_json(QOTD_FILE, {"questions": []})
used_qotd = []

def system_channel():
    return bot.get_channel(SYSTEM_CHANNEL_ID)

def leaderboard_channel():
    return bot.get_channel(LEADERBOARD_CHANNEL_ID)

def logs_channel():
    return bot.get_channel(LOGS_CHANNEL_ID)

async def send_reply(ctx, content=None, embed=None, file=None, ephemeral=False):
    try:
        if ctx.interaction and not ctx.interaction.response.is_done():
            await ctx.interaction.response.send_message(content or "", embed=embed, file=file, ephemeral=ephemeral)
        else:
            await ctx.reply(content or "", embed=embed, file=file)
    except Exception:
        if content or embed or file:
            await ctx.channel.send(content or "", embed=embed, file=file)

# ----------------------
# XP + Rank System
# ----------------------
xp_multiplier = 1

async def add_xp(user_id, amount, channel=None):
    uid = str(user_id)
    xp_data[uid] = xp_data.get(uid, 0) + (amount * xp_multiplier)
    save_json(XP_FILE, xp_data)

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
# Core Commands
# ----------------------
@bot.hybrid_command(name="ping", description="Test the bot")
async def ping(ctx):
    await send_reply(ctx, "🏓 Pong!")

@bot.hybrid_command(name="rank", description="Check your XP and rank")
async def rank(ctx):
    xp = xp_data.get(str(ctx.author.id), 0)
    role = get_rank_role(assign_rank(xp))
    await send_reply(ctx, f"⭐ {ctx.author.mention}, you have {xp} XP ({role})")

@bot.hybrid_command(name="linkepic", description="Link your Epic Games account")
async def linkepic(ctx, epic_username: str):
    epic_links[str(ctx.author.id)] = epic_username
    save_json(EPIC_FILE, epic_links)
    await send_reply(ctx, f"✅ Linked your Epic account as **{epic_username}**")

@bot.hybrid_command(name="epicslinked", description="List Epic accounts")
async def epicslinked(ctx):
    if not epic_links:
        return await send_reply(ctx, "❌ No Epic accounts linked yet.")
    linked = "\n".join([f"<@{uid}> → **{epic}**" for uid, epic in epic_links.items()])
    await send_reply(ctx, f"🔗 Epic accounts linked:\n{linked}")

# ----------------------
# XP Leaderboard
# ----------------------
@bot.hybrid_command(name="xpleaderboard", description="Show XP leaderboard")
async def xpleaderboard(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    if not xp_data:
        return await ctx.followup.send("❌ No XP data yet.")

    order = ["UNREAL","CHAMPION","ELITE","DIAMOND III","DIAMOND II","DIAMOND I",
             "PLATINUM III","PLATINUM II","PLATINUM I","GOLD III","GOLD II","GOLD I",
             "SILVER III","SILVER II","SILVER I","BRONZE III","BRONZE II","BRONZE I"]

    embed = discord.Embed(title="🏆 XP Leaderboard", color=discord.Color.blue())
    grouped = {rank: [] for rank in order}
    for uid, xp in xp_data.items():
        rank = get_rank_role(assign_rank(xp))
        if rank in grouped:
            grouped[rank].append((uid, xp))

    for rank in order:
        if grouped[rank]:
            members = sorted(grouped[rank], key=lambda x: x[1], reverse=True)
            embed.add_field(name=rank, value="\n".join([f"<@{u}> — {x} XP" for u, x in members]), inline=False)

    await ctx.followup.send(embed=embed)

@bot.hybrid_command(name="grantxp", description="Grant XP to a user (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def grantxp(ctx, member: discord.Member, amount: int):
    await add_xp(member.id, amount, ctx.channel)
    await send_reply(ctx, f"✅ Granted {amount} XP to {member.mention}", ephemeral=True)
# ----------------------
# KD Leaderboard + Cleaner Role
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

last_cleaner = None

async def generate_kd_leaderboard(epic_links):
    global last_cleaner
    players = []
    for uid, epic_username in epic_links.items():
        stats = await fetch_fortnite_stats(epic_username)
        if stats:
            players.append({"uid": uid, "username": epic_username, "kd": stats["kd"], "wins": stats["wins"]})

    players.sort(key=lambda p: (-p["kd"], -p["wins"]))
    top10 = players[:10]

    if top10:
        guild = bot.guilds[0] if bot.guilds else None
        if guild:
            cleaner_role = discord.utils.get(guild.roles, name="The Cleaner")
            if cleaner_role:
                for m in guild.members:
                    if cleaner_role in m.roles:
                        await m.remove_roles(cleaner_role)
                winner = guild.get_member(int(top10[0]["uid"]))
                if winner:
                    await winner.add_roles(cleaner_role)
                    if last_cleaner != winner.id:
                        last_cleaner = winner.id
                        embed = discord.Embed(
                            title="🧹 New Cleaner Crowned!",
                            description=f"{winner.mention} cleaned up the lobbies!",
                            color=discord.Color.green()
                        )
                        embed.set_thumbnail(url=winner.display_avatar.url)
                        if system_channel():
                            await system_channel().send(embed=embed)

    img = "kd_leaderboard.png"
    generate_leaderboard_image(top10)
    return img

@bot.hybrid_command(name="kdleaderboard", description="Show KD leaderboard")
async def kdleaderboard(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    img = await generate_kd_leaderboard(epic_links)
    if img:
        await ctx.followup.send(file=discord.File(img))
    else:
        await ctx.followup.send("❌ Failed to fetch.")

@tasks.loop(hours=168)
async def autopost_leaderboard():
    ch = leaderboard_channel()
    if ch:
        img = await generate_kd_leaderboard(epic_links)
        if img:
            await ch.send("📊 Weekly KD Leaderboard", file=discord.File(img))

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
                age = datetime.utcnow().year - int(date[:4])
                await channel.send(f"🎮 <@{uid}> has reached **Level {age}** today! 🎉")
                await add_xp(int(uid), 500, channel)

# ----------------------
# Tournament Commands
# ----------------------
@bot.hybrid_command(name="tournament", description="Manage tournaments")
async def tournament(ctx, action: str, name: str = None):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    uid = str(ctx.author.id)
    if action == "join" and name:
        if name not in tournaments:
            tournaments[name] = []
        if uid not in tournaments[name]:
            tournaments[name].append(uid)
            save_json(TOURNAMENT_FILE, tournaments)
            return await ctx.followup.send(f"⚔️ {ctx.author.mention} joined **{name}**!")
    elif action == "status" and name:
        players = tournaments.get(name, [])
        return await ctx.followup.send(f"📋 Tournament **{name}**: {len(players)} players")
    else:
        return await ctx.followup.send("❌ Usage: /tournament join <name> | /tournament status <name>")

# ----------------------
# Backscan + Health Check
# ----------------------
async def run_backscan():
    await check_birthdays()
    img = await generate_kd_leaderboard(epic_links)
    if img and leaderboard_channel():
        await leaderboard_channel().send("📊 Catch-up KD Leaderboard", file=discord.File(img))

# ----------------------
# Deep Self-Maintenance
# ----------------------
async def run_self_maintenance():
    try:
        # 1. Check birthdays
        await check_birthdays()

        # 2. Rebuild KD leaderboard + update Cleaner
        img = await generate_kd_leaderboard(epic_links)
        if img and leaderboard_channel():
            await leaderboard_channel().send("📊 Self-maintenance KD Leaderboard", file=discord.File(img))

        # 3. Ensure QOTD has gone out
        if qotd_data["questions"]:
            available = [q for q in qotd_data["questions"] if q not in used_qotd]
            if not available:
                used_qotd.clear()
                available = qotd_data["questions"]
            q = random.choice(available)
            used_qotd.append(q)
            ch = bot.get_channel(int(os.getenv("QOTD_CHANNEL_ID", SYSTEM_CHANNEL_ID)))
            if ch:
                await ch.send(f"❓ **QOTD (catch-up):** {q}")

        # 4. Recheck podcast RSS
        if PODCAST_RSS_FEED and PODCAST_CHANNEL_ID:
            feed = feedparser.parse(PODCAST_RSS_FEED)
            if feed.entries:
                latest = feed.entries[0]
                ch = bot.get_channel(PODCAST_CHANNEL_ID)
                if ch:
                    await ch.send(f"🎙️ Podcast check: Latest episode is {latest.title}\n{latest.link}")

        # 5. Backup everything
        save_json(BACKUP_FILE, {
            "xp": xp_data,
            "epic": epic_links,
            "birthdays": birthdays,
            "tournaments": tournaments,
            "creator_maps": creator_maps
        })

        # 6. Log success
        if logs_channel():
            await logs_channel().send("🛠️ Self-maintenance completed successfully.")

    except Exception as e:
        if logs_channel():
            await logs_channel().send(f"⚠️ Self-maintenance error: {e}")

@bot.hybrid_command(name="backscan", description="Run daily scan manually")
async def backscan(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)
    await run_backscan()
    await ctx.followup.send("✅ Backscan complete")

@bot.hybrid_command(name="health", description="Health check (UptimeRobot)")
async def health(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    await run_backscan()
    if ctx.interaction:
        await ctx.followup.send("✅ Health scan complete")

    log_ch = logs_channel()
    if log_ch:
        await log_ch.send("✅ Bot is up and responding.")
        await log_ch.send("🏓 Pong!")

# ----------------------
# Creator Map Tracker
# ----------------------
async def fetch_creator_maps(creator_id):
    url = f"https://fortnite-api.com/v1/creative/creatorcode/{creator_id}"
    headers = {"Authorization": FORTNITE_API_KEY}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return []
                return (await resp.json()).get("data", [])
    except Exception:
        return []

@bot.hybrid_command(name="trackmaps", description="Track a Fortnite creator ID")
async def trackmaps(ctx, creator_id: str):
    if creator_id not in creator_maps["tracked"]:
        if len(creator_maps["tracked"]) >= 25:
            return await send_reply(ctx, "❌ Max 25 creators tracked.")
        creator_maps["tracked"].append(creator_id)
        save_json(CREATOR_FILE, creator_maps)
    await send_reply(ctx, f"✅ Now tracking maps for **{creator_id}**")

@tasks.loop(hours=1)
async def check_creator_maps():
    ch = system_channel()
    for creator_id in creator_maps["tracked"]:
        maps = await fetch_creator_maps(creator_id)
        for m in maps:
            map_id = m.get("code")
            if not map_id:
                continue
            if map_id not in creator_maps["posted"].get(creator_id, []):
                embed = discord.Embed(
                    title=f"🗺️ New Map by {creator_id}",
                    description=f"**{m.get('title','Untitled')}**\n{m.get('description','')}\n[Play Now](https://www.fortnite.com/@{creator_id}/{map_id})",
                    color=discord.Color.blue()
                )
                thumb = m.get("image")
                if thumb:
                    embed.set_thumbnail(url=thumb)
                if ch:
                    await ch.send(embed=embed)
                creator_maps["posted"].setdefault(creator_id, []).append(map_id)
                save_json(CREATOR_FILE, creator_maps)

# ----------------------
# Fun Engagement Features
# ----------------------
@tasks.loop(hours=24)
async def daily_qotd():
    if not qotd_data["questions"]:
        return
    available = [q for q in qotd_data["questions"] if q not in used_qotd]
    if not available:
        used_qotd.clear()
        available = qotd_data["questions"]
    q = random.choice(available)
    used_qotd.append(q)
    ch = system_channel()
    if ch:
        await ch.send(f"❓ **QOTD:** {q}")

@tasks.loop(hours=24)
async def hidden_multiplier():
    global xp_multiplier
    if random.random() < 0.2:
        xp_multiplier = 2
        ch = system_channel()
        if ch:
            await ch.send("⚡ A mysterious energy is in the air… XP gains are doubled today!")
    else:
        xp_multiplier = 1

@tasks.loop(hours=6)
async def loot_drop():
    if random.random() < 0.3:
        ch = system_channel()
        if ch:
            await ch.send("🎁 A loot chest appeared! Type `!claim` in 2 minutes to open it! Winner gets **10,000 XP**!")

            def check(m): return m.content.lower() == "!claim" and m.channel == ch
            try:
                m = await bot.wait_for("message", timeout=120, check=check)
                await add_xp(m.author.id, 10000, ch)
                await ch.send(f"🎉 {m.author.mention} claimed the chest and earned **10,000 XP!**")
            except asyncio.TimeoutError:
                await ch.send("⌛ The loot chest vanished...")

@tasks.loop(hours=720)  # ~monthly
async def secret_challenge():
    if not bot.guilds:
        return
    guild = bot.guilds[0]
    member = random.choice([m for m in guild.members if not m.bot])
    try:
        await member.send("🤫 **Secret Mission:** Post a Fortnite clip today and you’ll earn 100 bonus XP!")
    except:
        pass

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
    ch = bot.get_channel(PODCAST_CHANNEL_ID)
    if ch:
        await ch.send(f"🎙️ New episode: {latest.title}\n{latest.link}")

# ----------------------
# Daily Backup
# ----------------------
@tasks.loop(hours=24)
async def daily_backup():
    save_json(BACKUP_FILE, {
        "xp": xp_data,
        "epic": epic_links,
        "birthdays": birthdays,
        "tournaments": tournaments,
        "creator_maps": creator_maps
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
    daily_qotd.start()
    hidden_multiplier.start()
    loot_drop.start()
    secret_challenge.start()

# ----------------------
# Start
# ----------------------
keep_alive()
bot.run(DISCORD_TOKEN)
