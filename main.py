# SweeperLeader Bot - Final Main.py
# =================================
# Commands available (slash & auto):
# /link <epic_username>      -> Link Epic account to Discord
# /stats [user]              -> Show Fortnite stats for user
# /kdleaderboard             -> Generate KD leaderboard with graphic
# /kdpreview                 -> Debug leaderboard layout with template
# /backscan                  -> Run a scan of XP/rank consistency
# /tournament join <name>    -> Join BritBowl / Crew Up / Winterfest
# /tournament status         -> Show tournament status & win gates
# Auto XP                    -> +5 per message, +10 per reaction
# Cleaner Bonus              -> Double XP if 'The Cleaner' held >7d
# Birthday System            -> Birthday role, 2× XP, level-up message
# Creator Map Tracker        -> Auto-posts maps + awards XP for clicks
# Podcast Autoposter         -> Posts new episodes from RSS feed
# Daily Backup               -> Saves DB every midnight UTC
# Keepalive                  -> Small Flask webserver for UptimeRobot
# ==========================

import os
import discord
from discord.ext import commands, tasks
from discord import app_commands

# Load secrets
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FORTNITE_API_KEY = os.getenv("FORTNITE_API_KEY")
PODCAST_RSS_FEED = os.getenv("PODCAST_RSS_FEED")

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Placeholder: Feature modules would be imported here (xp, leaderboard, etc.)
# For demo: we just boot bot.

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

# Slash command example
@bot.tree.command(name="ping", description="Test bot response")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")
from keep_alive import keep_alive

keep_alive()  # starts Flask server so Render doesn’t kill the bot
bot.run(DISCORD_TOKEN)
