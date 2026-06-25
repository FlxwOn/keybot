import discord
from discord import app_commands
import os
import sqlite3
from datetime import datetime, timedelta
from discord.ext import tasks
import random
import string

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")

OWNER_ID = 1511181685881045002   # Your ID
ROLE_ID = 1511762417225302099      # Change this
GUILD_ID = 1511181685881045002   # Your server ID

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ====================== DATABASE ======================
conn = sqlite3.connect("keys.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS used_keys (key TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS active_access (user_id INTEGER PRIMARY KEY, expires TEXT)''')
conn.commit()

def random_str(length=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ====================== REDEEM MODAL ======================
class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key = discord.ui.TextInput(label="Enter your key", placeholder="KM-XXXX-XXXX-XXXX-XXXX", required=True, max_length=30)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value.strip().upper()

        if not key.startswith("KM-"):
            await interaction.response.send_message("❌ Key must start with KM-", ephemeral=True)
            return

        cursor.execute("SELECT * FROM used_keys WHERE key = ?", (key,))
        if cursor.fetchone():
            await interaction.response.send_message("❌ This key has already been used.", ephemeral=True)
            return

        role = interaction.guild.get_role(ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Role not found.", ephemeral=True)
            return

        await interaction.user.add_roles(role)

        expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        cursor.execute("INSERT OR REPLACE INTO active_access (user_id, expires) VALUES (?, ?)", (interaction.user.id, expires))
        cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
        conn.commit()

        # Log
        embed = discord.Embed(title="✅ Key Redeemed", description=f"{interaction.user.mention} redeemed a key.", color=0x00ff00)
        embed.set_footer(text="GemArchive")
        embed.timestamp = datetime.utcnow()

        log_channel = discord.utils.get(interaction.guild.text_channels, name="key-logs")
        if log_channel:
            await log_channel.send(embed=embed)

        await interaction.response.send_message("✅ Success! You have **1 hour** access.", ephemeral=True)

# ====================== COMMANDS ======================
@tree.command(name="redeem", description="Redeem your key")
async def redeem(interaction: discord.Interaction):
    await interaction.response.send_modal(RedeemModal())

@tree.command(name="setup", description="Setup bot (Owner only)")
async def setup(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ Only owner can use this.", ephemeral=True)
        return
    await interaction.response.send_message("✅ Bot setup complete.", ephemeral=True)

@tree.command(name="gen", description="Generate key (Owner only)")
async def gen(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ Only owner can use this.", ephemeral=True)
        return
    key = f"KM-{random_str(4)}-{random_str(4)}-{random_str(4)}-{random_str(4)}"
    cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))  # Optional: pre-add to valid
    conn.commit()
    await interaction.response.send_message(f"**Generated Key:**\n`{key}`", ephemeral=True)

# ====================== EXPIRATION ======================
@tasks.loop(minutes=5)
async def check_expirations():
    now = datetime.utcnow().isoformat()
    cursor.execute("SELECT user_id FROM active_access WHERE expires < ?", (now,))
    for (user_id,) in cursor.fetchall():
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                role = guild.get_role(ROLE_ID)
                if role:
                    await member.remove_roles(role)
                    log_channel = discord.utils.get(guild.text_channels, name="key-logs")
                    if log_channel:
                        embed = discord.Embed(title="⏰ Access Expired", description=f"{member.mention}'s access ended.", color=0x6B7280)
                        await log_channel.send(embed=embed)
    cursor.execute("DELETE FROM active_access WHERE expires < ?", (now,))
    conn.commit()

@bot.event
async def on_ready():
    print(f"✅ Bot online as {bot.user}")
    check_expirations.start()
    
    # Global sync + guild sync
    await tree.sync()
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("✅ Commands synced globally.")

bot.run(TOKEN)
