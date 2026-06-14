import discord
from discord import app_commands
from discord.ext import tasks
import os
import sqlite3
from datetime import datetime, timedelta, timezone

# ====================== CONFIG ======================

TOKEN = os.getenv("TOKEN")

ROLE_ID = 1511762417225302099
GUILD_ID = 1511181685881045002

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ====================== DATABASE ======================

conn = sqlite3.connect("keys.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS active_access (
    user_id INTEGER PRIMARY KEY,
    expires TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS used_keys (
    key TEXT PRIMARY KEY
)
""")

conn.commit()

# ====================== HELPERS ======================

def utc_now():
    return datetime.now(timezone.utc)

# ====================== REDEEM MODAL ======================

class RedeemModal(discord.ui.Modal, title="Redeem Key"):

    key = discord.ui.TextInput(
        label="Enter your key",
        placeholder="KM-XXXX-XXXX-XXXX-XXXX",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key.value.strip().upper()

        cursor.execute(
            "SELECT key FROM used_keys WHERE key = ?",
            (key,)
        )

        if cursor.fetchone():
            await interaction.response.send_message(
                "❌ This key has already been used.",
                ephemeral=True
            )
            return

        role = interaction.guild.get_role(ROLE_ID)

        if role is None:
            await interaction.response.send_message(
                "❌ Role not found.",
                ephemeral=True
            )
            return

        try:
            await interaction.user.add_roles(role)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to give that role.",
                ephemeral=True
            )
            return

        expires = (utc_now() + timedelta(hours=1)).isoformat()

        cursor.execute(
            """
            INSERT OR REPLACE INTO active_access
            (user_id, expires)
            VALUES (?, ?)
            """,
            (interaction.user.id, expires)
        )

        cursor.execute(
            "INSERT INTO used_keys (key) VALUES (?)",
            (key,)
        )

        conn.commit()

        embed = discord.Embed(
            title="🔑 Key Redeemed Successfully",
            description=f"{interaction.user.mention} just unlocked access!",
            color=0xC026D3
        )

        embed.add_field(
            name="User",
            value=interaction.user.mention,
            inline=True
        )

        embed.add_field(
            name="Key",
            value=f"`{key}`",
            inline=True
        )

        embed.add_field(
            name="Duration",
            value="1 Hour",
            inline=True
        )

        embed.timestamp = utc_now()
        embed.set_footer(text="GemArchive • Premium Collection")

        log_channel = discord.utils.get(
            interaction.guild.text_channels,
            name="key-logs"
        )

        if log_channel:
            await log_channel.send(embed=embed)

        print(
            f"[{utc_now().strftime('%H:%M:%S')}] "
            f"KEY REDEEMED -> {interaction.user}"
        )

        await interaction.response.send_message(
            "✅ Success! You now have 1 hour of access.",
            ephemeral=True
        )

# ====================== COMMANDS ======================

guild_obj = discord.Object(id=GUILD_ID)

@tree.command(
    name="setup",
    description="Setup the bot",
    guild=guild_obj
)
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.send_message(
        "✅ Bot setup complete!",
        ephemeral=True
    )

@tree.command(
    name="gen",
    description="Generate a key",
    guild=guild_obj
)
@app_commands.checks.has_permissions(administrator=True)
async def gen(interaction: discord.Interaction):

    key = "KM-" + "-".join(
        os.urandom(2).hex().upper()
        for _ in range(4)
    )

    await interaction.response.send_message(
        f"**Generated Key:** `{key}`",
        ephemeral=True
    )

@tree.command(
    name="redeem",
    description="Redeem your key",
    guild=guild_obj
)
async def redeem(interaction: discord.Interaction):
    await interaction.response.send_modal(RedeemModal())

# ====================== EXPIRATION TASK ======================

@tasks.loop(minutes=5)
async def check_expirations():

    now = utc_now()

    cursor.execute(
        "SELECT user_id, expires FROM active_access"
    )

    rows = cursor.fetchall()

    for user_id, expires_str in rows:

        try:
            expires = datetime.fromisoformat(expires_str)
        except Exception:
            continue

        if expires > now:
            continue

        for guild in bot.guilds:

            member = guild.get_member(user_id)

            if member is None:
                continue

            role = guild.get_role(ROLE_ID)

            if role and role in member.roles:
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    continue

                embed = discord.Embed(
                    title="⏰ Access Expired",
                    description=f"{member.mention}'s access has ended.",
                    color=0x6B7280
                )

                embed.timestamp = utc_now()
                embed.set_footer(text="GemArchive")

                log_channel = discord.utils.get(
                    guild.text_channels,
                    name="key-logs"
                )

                if log_channel:
                    await log_channel.send(embed=embed)

        cursor.execute(
            "DELETE FROM active_access WHERE user_id = ?",
            (user_id,)
        )

    conn.commit()

@check_expirations.before_loop
async def before_check_expirations():
    await bot.wait_until_ready()

# ====================== EVENTS ======================

@bot.event
async def on_ready():

    print(f"✅ Logged in as {bot.user}")

    if not check_expirations.is_running():
        check_expirations.start()

    synced = await tree.sync(guild=guild_obj)

    print(f"✅ Synced {len(synced)} commands")
    print("✅ Bot ready")

# ====================== RUN ======================

bot.run(TOKEN)
