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

# ← CHANGE THESE
OWNER_ID = 1306613335713779755   # Your Discord User ID
ROLE_ID =  1511762417225302099     # The role given for 1 hour access
GUILD_ID = 1511181685881045002   # Your server ID

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ====================== DATABASE ======================
conn = sqlite3.connect("keys.db")
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS valid_keys (key TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS used_keys (key TEXT PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS active_access (user_id INTEGER PRIMARY KEY, expires TEXT)''')
conn.commit()

# ====================== HELPER ======================
def random_str(length=4):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# ====================== REDEEM MODAL ======================
class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key = discord.ui.TextInput(
        label="Enter your key",
        placeholder="KM-XXXX-XXXX-XXXX-XXXX",
        required=True,
        max_length=30
    )

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value.strip().upper()

        if not key.startswith("KM-"):
            await interaction.response.send_message("❌ Key must start with KM-", ephemeral=True)
            return

        # Check if already used
        cursor.execute("SELECT * FROM used_keys WHERE key = ?", (key,))
        if cursor.fetchone():
            await interaction.response.send_message("❌ This key has already been used.", ephemeral=True)
            return

        # Give role
        role = interaction.guild.get_role(ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Role not found.", ephemeral=True)
            return

        await interaction.user.add_roles(role)

        # Set expiration (1 hour)
        expires = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        cursor.execute("INSERT OR REPLACE INTO active_access (user_id, expires) VALUES (?, ?)",
                      (interaction.user.id, expires))

        # Mark as used
        cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
        conn.commit()

        # Public Log
        embed = discord.Embed(
            title="✅ Key Redeemed",
            description=f"{interaction.user.mention} redeemed a key.",
            color=0x00ff00
        )
        embed.set_footer(text="GemArchive")
        embed.timestamp = datetime.utcnow()

        log_channel = discord.utils.get(interaction.guild.text_channels, name="key-logs")
        if log_channel:
            await log_channel.send(embed=embed)

        await interaction.response.send_message("✅ Success! You now have **1 hour** of access.", ephemeral=True)

# ====================== COMMANDS ======================
@tree.command(name="setup", description="Setup the bot (Owner only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ Only the owner can use this.", ephemeral=True)
        return
    await interaction.response.send_message("✅ Bot is ready.", ephemeral=True)

@tree.command(name="gen", description="Generate a new key (Owner only)")
@app_commands.checks.has_permissions(administrator=True)
async def gen(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("❌ Only the owner can use this.", ephemeral=True)
        return

    key = f"KM-{random_str(4)}-{random_str(4)}-{random_str(4)}-{random_str(4)}"
    
    cursor.execute("INSERT INTO valid_keys (key) VALUES (?)", (key,))
    conn.commit()

    await interaction.response.send_message(f"**New Key Generated:**\n`{key}`", ephemeral=True)

# ====================== EXPIRATION TASK ======================
@tasks.loop(minutes=5)
async def check_expirations():
    now = datetime.utcnow().isoformat()
    cursor.execute("SELECT user_id FROM active_access WHERE expires < ?", (now,))
    expired = cursor.fetchall()

    for (user_id,) in expired:
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                role = guild.get_role(ROLE_ID)
                if role and role in member.roles:
                    await member.remove_roles(role)
                    embed = discord.Embed(
                        title="⏰ Access Expired",
                        description=f"{member.mention}'s access has ended.",
                        color=0x6B7280
                    )
                    embed.set_footer(text="GemArchive")
                    embed.timestamp = datetime.utcnow()
                    log_channel = discord.utils.get(guild.text_channels, name="key-logs")
                    if log_channel:
                        await log_channel.send(embed=embed)

    cursor.execute("DELETE FROM active_access WHERE expires < ?", (now,))
    conn.commit()

# ====================== ON READY ======================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    check_expirations.start()
    
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print("✅ Commands synced.")

# Run the bot
bot.run(TOKEN)
