import discord
from discord import app_commands
import os
import sqlite3
from datetime import datetime, timedelta
import asyncio

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")
ROLE_ID = 1511762417225302099  # ← CHANGE THIS
GUILD_ID = 1511181685881045002  # Your server ID

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Database
conn = sqlite3.connect("keys.db")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS active_access (user_id INTEGER PRIMARY KEY, expires TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS used_keys (key TEXT PRIMARY KEY)''')
conn.commit()

# ====================== REDEEM MODAL ======================
class RedeemModal(discord.ui.Modal, title="Redeem Key"):
    key = discord.ui.TextInput(label="Enter your key", placeholder="KM-XXXX-XXXX-XXXX-XXXX", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value.strip().upper()

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
        cursor.execute("INSERT INTO active_access (user_id, expires) VALUES (?, ?)", 
                     (interaction.user.id, expires))
        
        cursor.execute("INSERT INTO used_keys (key) VALUES (?)", (key,))
        conn.commit()

        # Public Embed Log
        embed = discord.Embed(
            title="🔑 Key Redeemed Successfully",
            description=f"{interaction.user.mention} just unlocked access!",
            color=0xC026D3
        )
        embed.add_field(name="User", value=interaction.user.mention, inline=True)
        embed.add_field(name="Key", value=f"`{key}`", inline=True)
        embed.add_field(name="Duration", value="1 Hour", inline=True)
        embed.set_footer(text="GemArchive • Premium Collection")
        embed.timestamp = datetime.utcnow()

        log_channel = discord.utils.get(interaction.guild.text_channels, name="key-logs")
        if log_channel:
            await log_channel.send(embed=embed)
        else:
            getkey = discord.utils.get(interaction.guild.text_channels, name="get-key")
            if getkey:
                await getkey.send(embed=embed)

        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] KEY REDEEMED → {interaction.user}")

        await interaction.response.send_message("✅ **Success!** You now have **1 hour** of access.", ephemeral=True)

# ====================== COMMANDS ======================
@tree.command(name="setup", description="Setup the bot (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Bot setup complete! Use /redeem to redeem keys.", ephemeral=True)

@tree.command(name="gen", description="Generate a key (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def gen(interaction: discord.Interaction):
    key = "KM-" + "-".join([os.urandom(2).hex().upper() for _ in range(4)])
    await interaction.response.send_message(f"**Generated Key:** `{key}`", ephemeral=True)

@tree.command(name="redeem", description="Redeem your key")
async def redeem(interaction: discord.Interaction):
    await interaction.response.send_modal(RedeemModal())

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

                    # Public expiration log
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

# ====================== BOT EVENTS ======================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    check_expirations.start()
    
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print("Commands synced.")

# Run the bot
bot.run(TOKEN)
