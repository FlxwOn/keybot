import discord
from discord import app_commands
import os
import sqlite3
from datetime import datetime, timedelta
from discord.ext import tasks
import random
import string
from flask import Flask, jsonify
from threading import Thread

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")
OWNER_ID = 1306613335713779755   # Your Discord ID
ROLE_ID = 1511762417225302099       # ← CHANGE THIS
GUILD_ID = 1511181685881045002

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Database
conn = sqlite3.connect("keys.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS used_keys (key TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS active_access (user_id INTEGER PRIMARY KEY, expires TEXT)''')
conn.commit()

def random_str(n=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

# ====================== FLASK API (for Website) ======================
app = Flask(__name__)

@app.route('/generate-key')
def generate_key():
    key = f"KM-{random_str()}-{random_str()}-{random_str()}-{random_str()}"
    cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
    conn.commit()
    return jsonify({"success": True, "key": key})

def run_flask():
    app.run(host="0.0.0.0", port=5000, debug=False)

# ====================== REDEEM MODAL ======================
class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key = discord.ui.TextInput(label="Enter your key", placeholder="KM-XXXX-XXXX-XXXX-XXXX", max_length=30)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value.strip().upper()

        if not key.startswith("KM-"):
            return await interaction.response.send_message("❌ Key must start with KM-", ephemeral=True)

        cursor.execute("SELECT * FROM used_keys WHERE key = ?", (key,))
        if not cursor.fetchone():
            return await interaction.response.send_message("❌ Invalid key. Only keys from the website work.", ephemeral=True)

        cursor.execute("SELECT * FROM used_keys WHERE key = ?", (key,))  # Double check
        if cursor.fetchone():  # Already used? Wait, we check used_keys
            pass  # We'll mark as used below

        role = interaction.guild.get_role(ROLE_ID)
        if not role:
            return await interaction.response.send_message("❌ Role not found.", ephemeral=True)

        await interaction.user.add_roles(role)

        expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        cursor.execute("INSERT OR REPLACE INTO active_access (user_id, expires) VALUES (?, ?)", (interaction.user.id, expires))
        cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))  # Mark as used
        conn.commit()

        embed = discord.Embed(title="✅ Key Redeemed", description=f"{interaction.user.mention} redeemed a key.", color=0x00ff00)
        log_channel = discord.utils.get(interaction.guild.text_channels, name="key-logs")
        if log_channel:
            await log_channel.send(embed=embed)

        await interaction.response.send_message("✅ Success! You have **1 hour** access.", ephemeral=True)

# ====================== COMMANDS ======================
@tree.command(name="gen", description="Generate keys (Owner only)")
@app_commands.describe(amount="How many keys (1-10)")
async def gen(interaction: discord.Interaction, amount: int = 1):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Owner only.", ephemeral=True)

    amount = max(1, min(10, amount))
    keys = []
    for _ in range(amount):
        key = f"KM-{random_str()}-{random_str()}-{random_str()}-{random_str()}"
        cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
        keys.append(key)
    conn.commit()

    key_list = "\n".join([f"`{k}`" for k in keys])
    await interaction.response.send_message(f"**Generated {amount} key(s):**\n{key_list}", ephemeral=True)

@tree.command(name="redeem", description="Redeem your key")
async def redeem(interaction: discord.Interaction):
    await interaction.response.send_modal(RedeemModal())

# ====================== AUTO EXPIRATION ======================
@tasks.loop(minutes=5)
async def check_expirations():
    now = datetime.utcnow().isoformat()
    cursor.execute("SELECT user_id FROM active_access WHERE expires < ?", (now,))
    for (user_id,) in cursor.fetchall():
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                role = guild.get_role(ROLE_ID)
                if role and role in member.roles:
                    await member.remove_roles(role)
                    log_channel = discord.utils.get(guild.text_channels, name="key-logs")
                    if log_channel:
                        await log_channel.send(embed=discord.Embed(title="⏰ Access Expired", description=f"{member.mention}'s access ended.", color=0x6B7280))
    cursor.execute("DELETE FROM active_access WHERE expires < ?", (now,))
    conn.commit()

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    check_expirations.start()
    Thread(target=run_flask, daemon=True).start()
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("✅ Commands synced + API started.")

bot.run(TOKEN)
