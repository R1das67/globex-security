import discord
from discord.ext import commands
import datetime
import database as db
import re
import os
from dotenv import load_dotenv
from menu import MainMenuView

load_dotenv()

# Tracker für Verstöße: {guild_id: {user_id: {modul: [zeitstempel, ...]}}}
violation_tracker = {}

class GlobexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=None, intents=intents, help_command=None)

    async def setup_hook(self):
        # Das Menü bleibt auch nach einem Neustart funktionsfähig
        self.add_view(MainMenuView())
        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ {self.user} is online and secured!")
        
        # Start-Benachrichtigung an Server-Owner
        for guild in self.guilds:
            try:
                owner = guild.owner
                # Falls Owner nicht im Cache, versuchen zu fetchen
                if not owner:
                    owner = await guild.fetch_member(guild.owner_id)
                
                msg_content = (
                    f"**__Global Ping by Globex__**\n"
                    f"Hallo {owner.mention}, Globex Security ist stolz darauf, Ihnen mitteilen zu können, "
                    f"dass unser erweitertes Konfigurations-Menü nun vollständig einsatzbereit ist! "
                    f"Sie haben ab sofort die volle Kontrolle, um jede Sicherheitsfunktion individuell nach Ihren Wünschen anzupassen.\n"
                    f"-# Hinweis: Ihre Einstellungen werden sicher in unserer Datenbank gespeichert und bleiben auch nach Bot-Neustarts erhalten.\n\n"
                    f"**English:**\n"
                    f"Hello {owner.mention}, Globex Security is proud to announce that our extensive configuration menu is now fully operational! "
                    f"You now have the power to customize every single security module exactly the way you want.\n"
                    f"-# Note: Your settings are securely stored in our database and will persist even after bot restarts."
                )

                # Versuche DM, sonst in den 3. Textkanal
                try:
                    await owner.send(msg_content)
                except:
                    # Filtert nur echte Textkanäle und nimmt den Dritten (Index 2)
                    text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
                    if len(text_channels) >= 3:
                        await text_channels[2].send(msg_content)
                    elif text_channels:
                        await text_channels[0].send(msg_content)
            except Exception as e:
                print(f"Could not notify owner of {guild.name}: {e}")

bot = GlobexBot()

# --- HILFSFUNKTION FÜR LIMITS & ZEITRAUM ---
def is_limit_exceeded(guild_id, user_id, module, limit, timeframe):
    if not limit: return True
    if guild_id not in violation_tracker: violation_tracker[guild_id] = {}
    if user_id not in violation_tracker[guild_id]: violation_tracker[guild_id][user_id] = {}
    if module not in violation_tracker[guild_id][user_id]: violation_tracker[guild_id][user_id][module] = []
    
    now = datetime.datetime.now().timestamp()
    violation_tracker[guild_id][user_id][module] = [t for t in violation_tracker[guild_id][user_id][module] if now - t < (timeframe or 10)]
    violation_tracker[guild_id][user_id][module].append(now)
    return len(violation_tracker[guild_id][user_id][module]) >= limit

# --- ZENTRALE BESTRAFUNG MIT LOGGING ---
async def apply_punishment(member, module_prefix, guild_id):
    settings = db.get_data("settings", guild_id)
    punishment = settings.get(f"{module_prefix}_punish") or "kick"
    reason_clean = module_prefix.replace('_', ' ').title()
    reason = f"Globex Security: {reason_clean} Protection"

    try:
        # Bestrafung ausführen
        if punishment == "kick": await member.kick(reason=reason)
        elif punishment == "ban": await member.ban(reason=reason)
        elif punishment == "timeout":
            until = discord.utils.utcnow() + datetime.timedelta(hours=1)
            await member.timeout(until, reason=reason)
        
        # LOGGING (Falls aktiviert)
        if settings.get("log_status") == 1:
            log_cid = settings.get("log_channel")
            if log_cid and str(log_cid).isdigit():
                log_chan = bot.get_channel(int(log_cid))
                if log_chan:
                    now = datetime.datetime.now()
                    time_str = now.strftime("%d.%m.2026 at %H:%M") 
                    
                    embed = discord.Embed(title="**__🗃Globex Security Log__**", color=discord.Color.blue())
                    embed.add_field(name="Who was punished:", value=member.display_name, inline=False)
                    embed.add_field(name="Punishment Type:", value=punishment.capitalize(), inline=False)
                    embed.add_field(name="Reason:", value=reason_clean, inline=False)
                    embed.set_footer(text=f"{time_str}")
                    await log_chan.send(embed=embed)
    except Exception as e:
        print(f"DEBUG Error during punishment/logging: {e}")

# --- EVENT: ON_MESSAGE (Anti-Invite, Anti-Ping, Anti-Webhook) ---
@bot.event
async def on_message(message):
    if message.author.id == bot.user.id: return
    if message.webhook_id:
        if db.get_data("settings", message.guild.id).get("anti_webhook_status") == 1:
            try: await message.delete()
            except: pass
            return
    if message.author.bot or not message.guild: return
    if message.author.id == message.guild.owner_id or db.is_on_list(message.guild.id, message.author.id, "whitelist"): return

    settings = db.get_data("settings", message.guild.id)
    limits = db.get_data("limits", message.guild.id)

    # ANTI-INVITE
    if settings.get("anti_invite_status") == 1:
        invites = re.findall(r"(discord\.gg/|discord\.com/invite/)\S+", message.content)
        if invites:
            l, t = limits.get("invite_limit") or 1, limits.get("invite_time") or 10
            if len(invites) >= l or is_limit_exceeded(message.guild.id, message.author.id, "invite", l, t):
                try: 
                    await message.delete()
                    await apply_punishment(message.author, "anti_invite", message.guild.id)
                except: pass
            else:
                try: await message.delete()
                except: pass

    # ANTI-PING
    if settings.get("anti_ping_status") == 1:
        if message.mention_everyone:
            l, t = limits.get("ping_limit") or 1, limits.get("ping_time") or 10
            if 1 >= l or is_limit_exceeded(message.guild.id, message.author.id, "ping", l, t):
                try: 
                    await message.delete()
                    await apply_punishment(message.author, "anti_ping", message.guild.id)
                except: pass
            else:
                try: await message.delete()
                except: pass

# --- ANTI-NUKE EVENTS (Channel & Role) ---
@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        if entry.user.id in [bot.user.id, channel.guild.owner_id]: return
        if db.is_on_list(channel.guild.id, entry.user.id, "whitelist"): return
        if db.get_data("settings", channel.guild.id).get("channel_create_status") == 1:
            await channel.delete()
            member = await channel.guild.fetch_member(entry.user.id)
            await apply_punishment(member, "anti_channel_create", channel.guild.id)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id in [bot.user.id, channel.guild.owner_id]: return
        if db.is_on_list(channel.guild.id, entry.user.id, "whitelist"): return
        if db.get_data("settings", channel.guild.id).get("channel_delete_status") == 1:
            member = await channel.guild.fetch_member(entry.user.id)
            await apply_punishment(member, "anti_channel_delete", channel.guild.id)

@bot.event
async def on_guild_role_create(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        if entry.user.id in [bot.user.id, role.guild.owner_id]: return
        if db.is_on_list(role.guild.id, entry.user.id, "whitelist"): return
        if db.get_data("settings", role.guild.id).get("role_create_status") == 1:
            await role.delete()
            member = await role.guild.fetch_member(entry.user.id)
            await apply_punishment(member, "anti_role_create", role.guild.id)

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id in [bot.user.id, role.guild.owner_id]: return
        if db.is_on_list(role.guild.id, entry.user.id, "whitelist"): return
        if db.get_data("settings", role.guild.id).get("role_delete_status") == 1:
            member = await role.guild.fetch_member(entry.user.id)
            await apply_punishment(member, "anti_role_delete", role.guild.id)

# --- ANTI-WEBHOOK & ANTI-BOT JOIN ---
@bot.event
async def on_webhooks_update(channel):
    if db.get_data("settings", channel.guild.id).get("anti_webhook_status") == 1:
        async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.webhook_create, limit=1):
            if entry.user.id in [bot.user.id, channel.guild.owner_id]: return
            if db.is_on_list(channel.guild.id, entry.user.id, "whitelist"): return
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.id == entry.target.id: await wh.delete()
            member = await channel.guild.fetch_member(entry.user.id)
            await apply_punishment(member, "anti_webhook", channel.guild.id)

@bot.event
async def on_member_join(member):
    if not member.bot: return
    gid = member.guild.id
    if db.get_data("settings", gid).get("anti_bot_status") == 1:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.user.id in [gid, member.guild.owner_id]: return
            if db.is_on_list(gid, entry.user.id, "whitelist"): return
            try: await member.kick(reason="Anti-Bot Join Protection")
            except: pass
            l = db.get_data("limits", gid).get("bot_limit") or 1
            if is_limit_exceeded(gid, entry.user.id, "bot_join", l, 315360000):
                inviter = await member.guild.fetch_member(entry.user.id)
                if inviter: await apply_punishment(inviter, "anti_bot_join", gid)

# --- SETUP COMMAND ---
@bot.tree.command(name="config-setup-globex", description="Öffnet das Globex Security Hauptquartier")
async def setup(interaction: discord.Interaction):
    view = MainMenuView()
    await interaction.response.send_message(embed=view.base_embed(), view=view)

# --- START (RAILWAY/ORACLE SECRETS) ---
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:

    print("❌ERROR: No DISCORD_TOKEN found in environment variables or .env file!")
