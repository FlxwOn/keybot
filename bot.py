import discord
from discord import app_commands
import os
import sqlite3
from datetime import datetime, timedelta
from discord.ext import tasks
import random
import string

TOKEN = os.getenv("TOKEN")
OWNER_ID = 1511181685881045002
ROLE_ID = 1511762417225302099        # ← CHANGE
GUILD_ID = 1511181685881045002

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

conn = sqlite3.connect("keys.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS used_keys (key TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS active_access (user_id INTEGER PRIMARY KEY, expires TEXT)''')
conn.commit()

def random_str(n=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=n))

class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key = discord.ui.TextInput(label="Enter Key", placeholder="KM-XXXX-XXXX-XXXX-XXXX", max_length=30)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value.strip().upper()
        if not key.startswith("KM-"):
            return await interaction.response.send_message("❌ Must start with KM-", ephemeral=True)

        cursor.execute("SELECT * FROM used_keys WHERE key = ?", (key,))
        if cursor.fetchone():
            return await interaction.response.send_message("❌ Key already used.", ephemeral=True)

        role = interaction.guild.get_role(ROLE_ID)
        if role:
            await interaction.user.add_roles(role)

        expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        cursor.execute("INSERT OR REPLACE INTO active_access (user_id, expires) VALUES (?, ?)", (interaction.user.id, expires))
        cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
        conn.commit()

        await interaction.response.send_message("✅ 1 hour access granted!", ephemeral=True)

@tree.command(name="gen", description="Generate key (Owner only)")
async def gen(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("❌ Owner only", ephemeral=True)
    key = f"KM-{random_str()}-{random_str()}-{random_str()}-{random_str()}"
    cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
    conn.commit()
    await interaction.response.send_message(f"**New Key:**\n`{key}`", ephemeral=True)

@tree.command(name="redeem", description="Redeem your key")
async def redeem(interaction: discord.Interaction):
    await interaction.response.send_modal(RedeemModal())

@bot.event
async def on_ready():
    print(f"✅ Bot is online: {bot.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("✅ Commands synced to server.")

bot.run(TOKEN)
