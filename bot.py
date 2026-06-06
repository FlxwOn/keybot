import discord
from discord.ext import commands, tasks
import sqlite3
from datetime import datetime, timedelta
import random
import string
import os

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect('keys.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS active_access 
             (user_id INTEGER PRIMARY KEY, expires TEXT)''')
conn.commit()

ROLE_ID = None

def generate_key():
    return "KM-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    try:
        guild = discord.Object(id=1511181685881045002)
        await bot.tree.sync(guild=guild)
        print("✅ Commands synced!")
    except Exception as e:
        print(f"Sync error: {e}")
    check_expirations.start()

# === ADMIN ONLY COMMANDS ===
@bot.tree.command(name="setup", description="Setup the bot (Admin only)")
async def setup(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need Administrator permission to use this.", ephemeral=True)
        return
    global ROLE_ID
    ROLE_ID = role.id
    await interaction.response.send_message(f"✅ Setup complete!\nNSFW Role set to: **{role.name}**", ephemeral=True)

@bot.tree.command(name="gen", description="Generate keys (Admin only)")
async def gen(interaction: discord.Interaction, amount: int = 5):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ You need Administrator permission to use this.", ephemeral=True)
        return
    keys = [generate_key() for _ in range(amount)]
    await interaction.response.send_message(f"✅ Generated {amount} keys:\n```" + "\n".join(keys) + "```", ephemeral=True)

# Redeem Modal (Everyone can use)
class RedeemModal(discord.ui.Modal, title="Redeem Your Key"):
    key_input = discord.ui.TextInput(label="Enter your key", placeholder="KM-XXXX-XXXX-XXXX-XXXX", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key_input.value.strip()
        if ROLE_ID is None:
            await interaction.response.send_message("❌ Bot not setup yet.", ephemeral=True)
            return

        member = interaction.user
        role = interaction.guild.get_role(ROLE_ID)

        if role in member.roles:
            await interaction.response.send_message("You already have active access!", ephemeral=True)
            return

        await member.add_roles(role)

        expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
        c.execute("INSERT OR REPLACE INTO active_access VALUES (?, ?)", (member.id, expires))
        conn.commit()

        await interaction.response.send_message(f"✅ Success! You now have **7 days** NSFW access.", ephemeral=True)

@bot.tree.command(name="redeem", description="Redeem your key for 7 days access")
async def redeem(interaction: discord.Interaction):
    await interaction.response.send_modal(RedeemModal())

@tasks.loop(minutes=20)
async def check_expirations():
    now = datetime.utcnow().isoformat()
    c.execute("SELECT user_id FROM active_access WHERE expires < ?", (now,))
    for (user_id,) in c.fetchall():
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            role = guild.get_role(ROLE_ID)
            if member and role:
                try:
                    await member.remove_roles(role)
                except:
                    pass
    c.execute("DELETE FROM active_access WHERE expires < ?", (now,))
    conn.commit()

token = os.getenv("TOKEN")
bot.run(token)
