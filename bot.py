import discord
from discord.ext import commands, tasks
import sqlite3
import asyncio
from datetime import datetime, timedelta
import random
import string

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Database
conn = sqlite3.connect('keys.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS active_access 
             (user_id INTEGER PRIMARY KEY, expires TEXT)''')
conn.commit()

ROLE_ID = None  # Will be set during setup

def generate_key():
    return "KM-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    check_expirations.start()

@bot.tree.command(name="setup", description="Setup the bot (Admin only)")
@commands.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction, role: discord.Role):
    global ROLE_ID
    ROLE_ID = role.id
    await interaction.response.send_message(f"✅ Setup complete!\nRole set to: **{role.name}**\n\nUse `/gen` to create keys and `/redeem` to redeem.", ephemeral=True)

@bot.tree.command(name="gen", description="Generate keys (Admin only)")
@commands.has_permissions(administrator=True)
async def gen(interaction: discord.Interaction, amount: int = 5):
    keys = [generate_key() for _ in range(amount)]
    await interaction.response.send_message(f"Generated {amount} keys:\n```" + "\n".join(keys) + "```", ephemeral=True)

@bot.tree.command(name="redeem", description="Redeem your key for 7 days access")
async def redeem(interaction: discord.Interaction, key: str):
    if ROLE_ID is None:
        await interaction.response.send_message("Bot not setup yet. Ask admin to run `/setup`", ephemeral=True)
        return

    member = interaction.user
    role = interaction.guild.get_role(ROLE_ID)

    if role in member.roles:
        await interaction.response.send_message("You already have active access!", ephemeral=True)
        return

    # Add role
    await member.add_roles(role)

    # Save expiration (7 days)
    expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
    c.execute("INSERT OR REPLACE INTO active_access VALUES (?, ?)", (member.id, expires))
    conn.commit()

    await interaction.response.send_message(f"✅ Success! You now have **7 days** of NSFW access.", ephemeral=True)

# Auto remove expired roles
@tasks.loop(minutes=20)
async def check_expirations():
    now = datetime.utcnow().isoformat()
    c.execute("SELECT user_id FROM active_access WHERE expires < ?", (now,))
    expired_users = c.fetchall()

    for (user_id,) in expired_users:
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            role = guild.get_role(ROLE_ID)
            if member and role:
                try:
                    await member.remove_roles(role)
                except:
                    pass

    # Cleanup
    c.execute("DELETE FROM active_access WHERE expires < ?", (now,))
    conn.commit()

bot.run("YOUR_BOT_TOKEN_HERE")
