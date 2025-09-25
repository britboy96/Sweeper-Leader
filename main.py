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
from datetime import datetime, date
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
LOGS_CHANNEL_ID = int(os.getenv("LOGS_CHANNEL", 0))
BIRTHDAY_CHANNEL_ID = int(os.getenv("BIRTHDAY_CHANNEL", 0))
PODCAST_CHANNEL_ID = int(os.getenv("PODCAST_CHANNEL", 0))
QOTD_CHANNEL_ID = int(os.getenv("QOTD_CHANNEL_ID", 1140430213440876716))

XP_FILE = "xp_data.json"
EPIC_FILE = "epic_links.json"
BIRTHDAY_FILE = "birthdays.json"
TOURNAMENT_FILE = "data/tournaments.json"
BACKUP_FILE = "backup.json"
CREATOR_FILE = "creator_maps.json"
QOTD_FILE = "qotd.json"

CREW_ROLE_ID = 1372346291023249511  # Crew Member role for tagging

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
last_qotd_date = None

def system_channel():
    return bot.get_channel(SYSTEM_CHANNEL_ID)

def leaderboard_channel():
    return bot.get_channel(LEADERBOARD_CHANNEL_ID)

def logs_channel():
    return bot.get_channel(LOGS_CHANNEL_ID)

async def log_event(msg: str):
    ch = logs_channel()
    if ch:
        await ch.send(msg)

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
                await log_event(f"⭐ {member} ranked up to {role_name}")
                if channel:
                    await channel.send(f"🎉 {member.mention} ranked up to **{role_name}**!")

    await log_event(f"➕ {amount} XP added to <@{user_id}> (total {xp_data[uid]})")

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
# Daily Claim
# ----------------------
DAILY_FILE = "daily_claims.json"
daily_claims = load_json(DAILY_FILE, {})

@bot.hybrid_command(name="daily", description="Claim your daily XP bonus")
async def daily(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    uid = str(ctx.author.id)
    today = date.today().isoformat()

    last_claim = daily_claims.get(uid)
    if last_claim == today:
        return await ctx.followup.send("⏳ You've already claimed your daily XP today. Come back tomorrow!")

    daily_claims[uid] = today
    save_json(DAILY_FILE, daily_claims)
    await add_xp(ctx.author.id, 50, ctx.channel)  # 50 XP reward
    await ctx.followup.send(f"✅ {ctx.author.mention}, you claimed your daily reward of **50 XP**!")
    await log_event(f"🎁 Daily XP claimed by {ctx.author}")

# ----------------------
# Core Commands
# ----------------------
@bot.hybrid_command(name="linkepic", description="Link your Epic Games username")
async def linkepic(ctx, epic_username: str):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    epic_links[str(ctx.author.id)] = epic_username
    save_json(EPIC_FILE, epic_links)
    await ctx.followup.send(f"🔗 Linked your Epic username to **{epic_username}**")
    await log_event(f"🔗 {ctx.author} linked Epic → {epic_username}")

@bot.hybrid_command(name="epicslinked", description="Show all linked Epic accounts")
async def epicslinked(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    if not epic_links:
        return await ctx.followup.send("❌ No Epic accounts linked yet.")
    lines = [f"<@{uid}> → {uname}" for uid, uname in epic_links.items()]
    await ctx.followup.send("📜 **Linked Epic Accounts:**\n" + "\n".join(lines))
    await log_event("📜 Epic links list requested")

@bot.hybrid_command(name="ping", description="Test the bot")
async def ping(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)
    await ctx.followup.send("🏓 Pong!")
    await log_event("🏓 Ping command used")

@bot.hybrid_command(name="rank", description="Check your XP and rank")
async def rank(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    xp = xp_data.get(str(ctx.author.id), 0)
    role = get_rank_role(assign_rank(xp))
    await ctx.followup.send(f"⭐ {ctx.author.mention}, you have {xp} XP ({role})")
    await log_event(f"📊 Rank checked by {ctx.author} — {xp} XP, {role}")

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
            embed.add_field(
                name=rank,
                value="\n".join([f"<@{u}> — {x} XP" for u, x in members]),
                inline=False
            )

    await ctx.followup.send(embed=embed)
    await log_event("🏆 XP leaderboard requested.")

@bot.hybrid_command(name="grantxp", description="Grant XP to a user (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def grantxp(ctx, member: discord.Member, amount: int):
    if ctx.interaction:
        await ctx.interaction.response.defer(ephemeral=True)

    await add_xp(member.id, amount, ctx.channel)
    await ctx.followup.send(f"✅ Granted {amount} XP to {member.mention}", ephemeral=True)
    await log_event(f"✅ {ctx.author} granted {amount} XP to {member}")

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

                return {
                    "kd": stats.get("kd", 0),
                    "wins": stats.get("wins", 0),
                    "matches": stats.get("matches", 0),
                    "kills": stats.get("kills", 0),
                    "winRate": stats.get("winRate", 0.0)
                }
    except Exception as e:
        print(f"⚠️ Error fetching stats: {e}")
        return None

last_cleaner = None

async def generate_kd_leaderboard(epic_links):
    global last_cleaner
    players = []
    for uid, epic_username in epic_links.items():
        stats = await fetch_fortnite_stats(epic_username)
        if stats:
            players.append({
                "uid": uid,
                "username": epic_username,
                "kd": stats["kd"],
                "wins": stats["wins"]
            })

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
                        await log_event(f"🧹 Cleaner role awarded to {winner}")

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
        await log_event("📊 KD leaderboard requested.")
    else:
        await ctx.followup.send("❌ Failed to fetch.")
        await log_event("⚠️ KD leaderboard fetch failed.")

@tasks.loop(hours=168)
async def autopost_leaderboard():
    ch = leaderboard_channel()
    if ch:
        img = await generate_kd_leaderboard(epic_links)
        if img:
            await ch.send("📊 Weekly KD Leaderboard", file=discord.File(img))
            await log_event("📊 Weekly KD leaderboard autoposted.")

# ----------------------
# Fortnite Player Stats
# ----------------------
@bot.hybrid_command(name="mystats", description="Show your linked Fortnite stats")
async def mystats(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    uid = str(ctx.author.id)
    epic = epic_links.get(uid)
    if not epic:
        return await ctx.followup.send("❌ You haven't linked your Epic account. Use `/linkepic <username>` first.")

    stats = await fetch_fortnite_stats(epic)
    if not stats:
        return await ctx.followup.send(f"⚠️ Could not fetch stats for **{epic}**.")

    embed = discord.Embed(title=f"🎮 {epic} — Lifetime Stats", color=discord.Color.blue())
    embed.add_field(name="🏆 Wins", value=stats.get("wins", 0))
    embed.add_field(name="🔪 K/D", value=stats.get("kd", 0))
    embed.add_field(name="🎮 Matches", value=stats.get("matches", "N/A"))
    await ctx.followup.send(embed=embed)
    await log_event(f"📊 /mystats used by {ctx.author} → {epic}")

@bot.hybrid_command(name="compare", description="Compare Fortnite stats between 2 linked users")
async def compare(ctx, user1: discord.Member, user2: discord.Member):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    epic1 = epic_links.get(str(user1.id))
    epic2 = epic_links.get(str(user2.id))
    if not epic1 or not epic2:
        return await ctx.followup.send("❌ Both users must have linked their Epic accounts.")

    stats1 = await fetch_fortnite_stats(epic1)
    stats2 = await fetch_fortnite_stats(epic2)
    if not stats1 or not stats2:
        return await ctx.followup.send("⚠️ Could not fetch stats for one or both players.")

    embed = discord.Embed(title="⚔️ Fortnite Stat Showdown", color=discord.Color.gold())
    embed.add_field(name=f"{epic1}", value=f"🏆 Wins: {stats1['wins']}\n🔪 K/D: {stats1['kd']}", inline=True)
    embed.add_field(name=f"{epic2}", value=f"🏆 Wins: {stats2['wins']}\n🔪 K/D: {stats2['kd']}", inline=True)
    await ctx.followup.send(embed=embed)
    await log_event(f"⚔️ /compare: {user1} vs {user2}")
# ----------------------
# Birthday System
# ----------------------
@bot.hybrid_command(name="setbirthday", description="Set your birthday (YYYY-MM-DD)")
async def setbirthday(ctx, date: str):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    try:
        datetime.strptime(date, "%Y-%m-%d")
        birthdays[str(ctx.author.id)] = date
        save_json(BIRTHDAY_FILE, birthdays)
        await ctx.followup.send(f"🎂 {ctx.author.mention}, birthday set to {date}")
        await log_event(f"🎂 Birthday set for {ctx.author} → {date}")
    except ValueError:
        await ctx.followup.send("❌ Invalid format. Use YYYY-MM-DD")
        await log_event(f"⚠️ Invalid birthday format by {ctx.author}")

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
                await log_event(f"🎉 Birthday detected for <@{uid}> — Level {age}")

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
            await ctx.followup.send(f"⚔️ {ctx.author.mention} joined **{name}**!")
            await log_event(f"⚔️ {ctx.author} joined tournament {name}")
        else:
            await ctx.followup.send(f"ℹ️ {ctx.author.mention}, you are already in **{name}**.")
    elif action == "status" and name:
        players = tournaments.get(name, [])
        await ctx.followup.send(f"📋 Tournament **{name}**: {len(players)} players")
        await log_event(f"📋 Tournament status checked: {name} — {len(players)} players")
    else:
        await ctx.followup.send("❌ Usage: /tournament join <name> | /tournament status <name>")
        await log_event(f"⚠️ Invalid tournament command usage by {ctx.author}")

# ----------------------
# Winterfest Tournament (December only)
# ----------------------
@tasks.loop(hours=24)
async def winterfest_challenge():
    today = datetime.utcnow()
    if today.month != 12:
        return  # December only

    modes = ["Battle Royale", "Reload", "OG", "Blitz", "Zero Build"]
    squads = ["Solo", "Duos", "Trios", "Squads"]
    mode = random.choice(modes)
    squad = random.choice(squads)

    ch = system_channel()
    if ch:
        await ch.send(
            f"❄️ **Winterfest Daily Challenge** ❄️\n"
            f"🎮 Mode: **{mode}**\n"
            f"👥 Squad Size: **{squad}**\n"
            f"🏆 Get 1 win today in this setup to stay in!"
        )
        await log_event(f"❄️ Winterfest challenge posted: {mode} {squad}")

# ----------------------
# Deep Scan: Messages + XP + Links + Birthdays
# ----------------------
async def scan_message_history(limit_per_channel=None):
    """Scans messages across all text channels for XP, linkepic, setbirthday, reactions."""
    if not bot.guilds:
        return

    guild = bot.guilds[0]
    for channel in guild.text_channels:
        try:
            async for msg in channel.history(limit=limit_per_channel, oldest_first=True):
                if msg.author.bot:
                    continue
                uid = str(msg.author.id)

                # XP for messages
                await add_xp(msg.author.id, 5, channel)

                # XP for reactions
                for reaction in msg.reactions:
                    async for user in reaction.users():
                        if not user.bot:
                            await add_xp(user.id, 10, channel)

                # Catch legacy !linkepic
                if msg.content.startswith("!linkepic") or msg.content.startswith("/linkepic"):
                    parts = msg.content.split(maxsplit=1)
                    if len(parts) > 1:
                        epic_links[uid] = parts[1].strip()
                        save_json(EPIC_FILE, epic_links)
                        await log_event(f"🔗 Backscan linked Epic for {msg.author} → {parts[1].strip()}")

                # Catch legacy !setbirthday
                if msg.content.startswith("!setbirthday") or msg.content.startswith("/setbirthday"):
                    parts = msg.content.split(maxsplit=1)
                    if len(parts) > 1:
                        try:
                            datetime.strptime(parts[1].strip(), "%Y-%m-%d")
                            birthdays[uid] = parts[1].strip()
                            save_json(BIRTHDAY_FILE, birthdays)
                            await log_event(f"🎂 Backscan set birthday for {msg.author} → {parts[1].strip()}")
                        except ValueError:
                            pass

        except Exception as e:
            await log_event(f"⚠️ Could not scan {channel.name}: {e}")

# ----------------------
# Backscan + Health Check
# ----------------------
async def run_backscan():
    """Deep backscan across all channels: XP, links, birthdays, leaderboards"""
    try:
        await scan_message_history(limit_per_channel=None)

        # Birthdays
        await check_birthdays()

        # KD leaderboard
        img = await generate_kd_leaderboard(epic_links)
        if img and leaderboard_channel():
            await leaderboard_channel().send("📊 Catch-up KD Leaderboard", file=discord.File(img))
            await log_event("📊 Backscan KD leaderboard refreshed.")

        # XP leaderboard
        if xp_data and leaderboard_channel():
            order = ["UNREAL","CHAMPION","ELITE","DIAMOND III","DIAMOND II","DIAMOND I",
                     "PLATINUM III","PLATINUM II","PLATINUM I","GOLD III","GOLD II","GOLD I",
                     "SILVER III","SILVER II","SILVER I","BRONZE III","BRONZE II","BRONZE I"]

            embed = discord.Embed(title="🏆 Catch-up XP Leaderboard", color=discord.Color.purple())
            grouped = {rank: [] for rank in order}
            for uid, xp in xp_data.items():
                rank = get_rank_role(assign_rank(xp))
                if rank in grouped:
                    grouped[rank].append((uid, xp))
            for rank in order:
                if grouped[rank]:
                    members = sorted(grouped[rank], key=lambda x: x[1], reverse=True)
                    embed.add_field(
                        name=rank,
                        value="\n".join([f"<@{u}> — {x} XP" for u, x in members]),
                        inline=False
                    )
            await leaderboard_channel().send(embed=embed)
            await log_event("🏆 Backscan XP leaderboard refreshed.")

        await log_event("✅ Deep backscan completed successfully.")

    except Exception as e:
        await log_event(f"⚠️ Backscan global error: {e}")

@bot.hybrid_command(name="backscan", description="Run deep scan manually")
async def backscan(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    await run_backscan()
    await ctx.followup.send("✅ Backscan complete — XP, links, birthdays synced.")
    await log_event(f"✅ Backscan run by {ctx.author}")

# ----------------------
# Self-Maintenance (Healthz pings)
# ----------------------
async def run_self_maintenance():
    try:
        await scan_message_history(limit_per_channel=500)  # catch-up sample

        await check_birthdays()

        # KD leaderboard
        img = await generate_kd_leaderboard(epic_links)
        if img and leaderboard_channel():
            await leaderboard_channel().send("📊 Self-maintenance KD Leaderboard", file=discord.File(img))
            await log_event("📊 Self-maintenance KD leaderboard refreshed.")

        # Ensure QOTD
        if qotd_data["questions"]:
            available = [q for q in qotd_data["questions"] if q not in used_qotd]
            if not available:
                used_qotd.clear()
                available = qotd_data["questions"]
            q = random.choice(available)
            used_qotd.append(q)
            ch = bot.get_channel(QOTD_CHANNEL_ID)
            if ch:
                await ch.send(f"❓ <@&{CREW_ROLE_ID}> **QOTD (catch-up):** {q}")
                await log_event(f"❓ Catch-up QOTD posted: {q}")

        # Podcast check
        if PODCAST_RSS_FEED and PODCAST_CHANNEL_ID:
            feed = feedparser.parse(PODCAST_RSS_FEED)
            if feed.entries:
                latest = feed.entries[0]
                ch = bot.get_channel(PODCAST_CHANNEL_ID)
                if ch:
                    await ch.send(f"🎙️ Podcast check: Latest episode is {latest.title}\n{latest.link}")
                    await log_event(f"🎙️ Podcast check posted: {latest.title}")

        # Backup
        save_json(BACKUP_FILE, {
            "xp": xp_data,
            "epic": epic_links,
            "birthdays": birthdays,
            "tournaments": tournaments,
            "creator_maps": creator_maps
        })
        await log_event("💾 Self-maintenance backup saved.")

        if logs_channel():
            await logs_channel().send("🛠️ Self-maintenance completed successfully.")

    except Exception as e:
        if logs_channel():
            await logs_channel().send(f"⚠️ Self-maintenance error: {e}")

@bot.hybrid_command(name="health", description="Health check (UptimeRobot)")
async def health(ctx):
    if ctx.interaction:
        await ctx.interaction.response.defer(thinking=True)

    await run_self_maintenance()
    if ctx.interaction:
        await ctx.followup.send("✅ Health maintenance complete")

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
        await log_event(f"🗺️ New creator tracked: {creator_id}")
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
                await log_event(f"🗺️ New map posted: {creator_id} — {map_id}")

# ----------------------
# Fun Engagement Features
# ----------------------
@tasks.loop(hours=24)
async def daily_qotd():
    global last_qotd_date
    today = date.today().isoformat()
    if last_qotd_date == today:
        await log_event("ℹ️ QOTD already posted today, skipping.")
        return
    if not qotd_data["questions"]:
        return

    available = [q for q in qotd_data["questions"] if q not in used_qotd]
    if not available:
        used_qotd.clear()
        available = qotd_data["questions"]

    q = random.choice(available)
    used_qotd.append(q)
    ch = bot.get_channel(QOTD_CHANNEL_ID)
    if ch:
        await ch.send(f"❓ <@&{CREW_ROLE_ID}> **QOTD:** {q}")
        await log_event(f"❓ QOTD posted: {q}")
        last_qotd_date = today

@tasks.loop(hours=24)
async def hidden_multiplier():
    global xp_multiplier
    if random.random() < 0.2:
        xp_multiplier = 2
        ch = system_channel()
        if ch:
            await ch.send("⚡ A mysterious energy is in the air… XP gains are doubled today!")
            await log_event("⚡ XP multiplier set to 2x")
    else:
        xp_multiplier = 1
        await log_event("ℹ️ XP multiplier reset to 1x")

@tasks.loop(hours=6)
async def loot_drop():
    if random.random() < 0.3:
        ch = system_channel()
        if ch:
            await ch.send(
                f"🎁 <@&{CREW_ROLE_ID}> A loot chest appeared! "
                f"Type `!claim` in 5 hours to open it! Winner gets **10,000 XP**!"
            )
            await log_event("🎁 Loot chest spawned.")

            def check(m): return m.content.lower() == "!claim" and m.channel == ch
            try:
                m = await bot.wait_for("message", timeout=18000, check=check)  # 5h
                await add_xp(m.author.id, 10000, ch)
                await ch.send(f"🎉 {m.author.mention} claimed the chest and earned **10,000 XP!**")
                await log_event(f"🏆 Loot chest claimed by {m.author}")
            except asyncio.TimeoutError:
                await ch.send("⌛ The loot chest vanished...")
                await log_event("⌛ Loot chest expired.")

@tasks.loop(hours=720)  # ~monthly
async def secret_challenge():
    if not bot.guilds:
        return
    guild = bot.guilds[0]
    member = random.choice([m for m in guild.members if not m.bot])
    try:
        await member.send("🤫 **Secret Mission:** Post a Fortnite clip today and you’ll earn 100 bonus XP!")
        await log_event(f"🤫 Secret mission DM sent to {member}")
    except:
        await log_event("⚠️ Secret mission DM failed to deliver")
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
        await log_event(f"🎙️ Podcast autopost: {latest.title}")

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
    await log_event("💾 Daily backup completed")

# ----------------------
# Events
# ----------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

    # Try to sync commands
    try:
        synced = await bot.tree.sync()
        names = [c.name for c in synced]
        print(f"✅ Synced {len(synced)} commands: {names}")
        if logs_channel():
            await logs_channel().send(f"✅ Synced {len(synced)} commands: {', '.join(names)}")
    except Exception as e:
        print(f"⚠️ Sync error: {e}")
        if logs_channel():
            await logs_channel().send(f"⚠️ Sync error: {e}")

    # Start background tasks
    autopost_leaderboard.start()
    check_birthdays.start()
    daily_backup.start()
    check_creator_maps.start()
    check_podcast.start()
    daily_qotd.start()
    hidden_multiplier.start()
    loot_drop.start()
    secret_challenge.start()
    winterfest_challenge.start()

    # Generate KD and XP leaderboard on startup (redeploy test)
    kd_img = await generate_kd_leaderboard(epic_links)
    if kd_img and leaderboard_channel():
        await leaderboard_channel().send("📊 Startup KD Leaderboard", file=discord.File(kd_img))
        await log_event("📊 KD leaderboard generated on startup")

    if xp_data and leaderboard_channel():
        order = ["UNREAL","CHAMPION","ELITE","DIAMOND III","DIAMOND II","DIAMOND I",
                 "PLATINUM III","PLATINUM II","PLATINUM I","GOLD III","GOLD II","GOLD I",
                 "SILVER III","SILVER II","SILVER I","BRONZE III","BRONZE II","BRONZE I"]

        embed = discord.Embed(title="🏆 Startup XP Leaderboard", color=discord.Color.purple())
        grouped = {rank: [] for rank in order}
        for uid, xp in xp_data.items():
            rank = get_rank_role(assign_rank(xp))
            if rank in grouped:
                grouped[rank].append((uid, xp))
        for rank in order:
            if grouped[rank]:
                members = sorted(grouped[rank], key=lambda x: x[1], reverse=True)
                embed.add_field(
                    name=rank,
                    value="\n".join([f"<@{u}> — {x} XP" for u, x in members]),
                    inline=False
                )
        await leaderboard_channel().send(embed=embed)
        await log_event("🏆 XP leaderboard generated on startup")
# ----------------------
# Start
# ----------------------
keep_alive()
bot.run(DISCORD_TOKEN)
