import discord
from discord import app_commands
import os
import sqlite3
from datetime import datetime, timedelta
from discord.ext import tasks
import random
import string
from flask import Flask, jsonify   # Added for API
from threading import Thread

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")
OWNER_ID = 1511181685881045002
ROLE_ID = YOUR_ROLE_ID_HERE
GUILD_ID = 1511181685881045002

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

conn = sqlite3.connect("keys.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS used_keys (key TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS active_access (user_id INTEGER PRIMARY KEY, expires TEXT)''')
conn.commit()

def random_str(n=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

# ====================== FLASK API FOR WEBSITE ======================
app = Flask(__name__)

@app.route('/generate-key')
def generate_key():
    key = f"KM-{random_str()}-{random_str()}-{random_str()}-{random_str()}"
    cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
    conn.commit()
    return jsonify({"success": True, "key": key})

def run_flask():
    app.run(host="0.0.0.0", port=5000)

# ====================== DISCORD BOT ======================
class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key = discord.ui.TextInput(label="Enter your key", placeholder="KM-XXXX-XXXX-XXXX-XXXX", max_length=30)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value.strip().upper()
        if not key.startswith("KM-"):
            return await interaction.response.send_message("❌ Invalid key format.", ephemeral=True)

        cursor.execute("SELECT * FROM used_keys WHERE key = ?", (key,))
        if not cursor.fetchone():
            return await interaction.response.send_message("❌ Invalid or expired key.", ephemeral=True)

        cursor.execute("SELECT * FROM used_keys WHERE key = ?", (key,))  # Wait, already checked
        # ... rest of redeem logic (add role, expiration, log) same as before

        # (I can send full code if you want)

# Add your commands (/gen, /redeem, etc.)

@bot.event
async def on_ready():
    print(f"✅ Bot online")
    Thread(target=run_flask, daemon=True).start()   # Start API
    await tree.sync(guild=discord.Object(id=GUILD_ID))

bot.run(TOKEN)
