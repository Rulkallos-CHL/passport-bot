import os
import json
import threading
from datetime import datetime
from flask import Flask
import discord
from discord.ext import commands

# ==========================================
# 1. RENDER KEEP-ALIVE WEB SERVER
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Passport Bot is actively running!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==========================================
# 2. LOCAL STORAGE SYSTEM (JSON)
# ==========================================
DATA_FILE = "passports.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def initialize_user(user_id, joined_at):
    """Creates a fresh default passport profile for a user if they don't have one."""
    data = load_data()
    if str(user_id) not in data:
        data[str(user_id)] = {
            "authenticated": False,
            "auth_date": "N/A",
            "auth_by": "N/A",
            "joined_at": joined_at,
            "warnings": 0
        }
        save_data(data)

# ==========================================
# 3. DISCORD BOT SETUP
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Setup a helper function to check for Admin permissions
def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f"Logged in safely as {bot.user.name}")
    print("------")

# ==========================================
# 4. AUTO-INITIALIZATION ON JOIN / TRIGGER
# ==========================================
@bot.event
async def on_guild_join(guild):
    """Automatically logs all existing members when bot joins a new server."""
    print(f"Joined new guild: {guild.name}. Initializing user profiles...")
    for member in guild.members:
        if not member.bot:
            joined_str = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"
            initialize_user(member.id, joined_str)
    print("All profiles initialized successfully.")

@bot.command()
@is_admin()
async def sync_all(ctx):
    """Manual trigger to initialize or update data profiles for everyone in the server."""
    await ctx.send("🔄 Scanning server and compiling passport database records...")
    count = 0
    for member in ctx.guild.members:
        if not member.bot:
            joined_str = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"
            initialize_user(member.id, joined_str)
            count += 1
    await ctx.send(f"✅ Successfully checked/updated records for {count} members.")

# ==========================================
# 5. CORE COMMANDS
# ==========================================

# 📋 COMMAND 1: CHECK
@bot.command()
async def check(ctx, member: discord.Member = None):
    """Prints a beautifully formatted profile overview of a user's passport data."""
    member = member or ctx.author  # If no user tagged, check yourself
    
    joined_str = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"
    initialize_user(member.id, joined_str)
    
    data = load_data()
    user_info = data[str(member.id)]
    
    # Format roles info
    roles = [role.name for role in member.roles if role.name != "@everyone"]
    roles_str = ", ".join(roles) if roles else "None"
    top_role = member.top_role.name if member.top_role else "None"
    
    status_emoji = "✅ Valid" if user_info["authenticated"] else "❌ Expired/Invalid"
    
    embed = discord.Embed(
        title=f"Passport Registry: {member.display_name}", 
        color=discord.Color.blue() if user_info["authenticated"] else discord.Color.red()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Passport Status", value=status_emoji, inline=False)
    embed.add_field(name="Date of Entry", value=user_info["joined_at"], inline=True)
    embed.add_field(name="Warnings Logged", value=f"⚠️ {user_info['warnings']}", inline=True)
    embed.add_field(name="Authentication Date", value=user_info["auth_date"], inline=True)
    embed.add_field(name="Authenticated By", value=user_info["auth_by"], inline=True)
    embed.add_field(name="Top Server Role", value=top_role, inline=True)
    embed.add_field(name="All Assigned Roles", value=roles_str, inline=False)
    embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
    
    await ctx.send(embed=embed)


# 🛑 COMMAND 2: DIS (Disable Passport)
@bot.command()
@is_admin()
async def dis(ctx, member: discord.Member, *, reason="No reason specified"):
    """Expires a passport and restricts text/read permissions across the server."""
    joined_str = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"
    initialize_user(member.id, joined_str)
    
    data = load_data()
    data[str(member.id)]["authenticated"] = False
    data[str(member.id)]["warnings"] += 1  # Automatically flags a warning when passport is revoked
    save_data(data)
    
    # Overwrite channel overrides dynamically to lock them down
    await ctx.send(f"⚠️ Revoking permissions and locking passport for {member.mention}...")
    
    # Loop through channels to remove view/speak abilities
    for channel in ctx.guild.channels:
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            # Deny view and send message access
            await channel.set_permissions(member, read_messages=False, send_messages=False)
            
    await ctx.send(f"🛑 **Passport Expired**: {member.mention}'s passport has been voided by {ctx.author.mention}. Reason: *{reason}*.")


# 🟢 COMMAND 3: EN (Enable Passport)
@bot.command()
@is_admin()
async def en(ctx, member: discord.Member):
    """Enables a passport, adding authentication details and reversing the lockdown overrides."""
    joined_str = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"
    initialize_user(member.id, joined_str)
    
    data = load_data()
    data[str(member.id)]["authenticated"] = True
    data[str(member.id)]["auth_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data[str(member.id)]["auth_by"] = str(ctx.author.name)
    save_data(data)
    
    await ctx.send(f"⚙️ Restoring server visibility and initializing passport access structures for {member.mention}...")
    
    # Remove user-specific channel overrides to restore standard role-based access
    for channel in ctx.guild.channels:
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            await channel.set_permissions(member, overwrite=None)
            
    await ctx.send(f"🟢 **Passport Authorized**: {member.mention} has been fully cleared and verified by {ctx.author.mention}!")


# Error management for Admin commands
@dis.error
@en.error
@sync_all.error
async def admin_command_error(ctx, error):
    if isinstance(error, commands.MissingCheckFailure):
        await ctx.send("❌ Error: You must be a Server Administrator to execute authorization commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Error: Missing arguments. Usage: `!dis @username [reason]` or `!en @username`")

# ==========================================
# 6. RUN EXECUTION
# ==========================================
if __name__ == "__main__":
    # Start the Flask web app background keep-alive loop
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()

    TOKEN = os.environ.get('DISCORD_TOKEN')
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("CRITICAL: DISCORD_TOKEN is missing from your Environment Variables!")