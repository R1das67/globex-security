import discord
from discord.ext import commands, tasks
import datetime
import database as db
import re
import os
from dotenv import load_dotenv
from menu import MainMenuView, AdmTimerView, LogSettingsView # LogSettingsView hinzugefügt
from zoneinfo import ZoneInfo

load_dotenv()

# Tracker for violations: {guild_id: {user_id: {module: [timestamps, ...]}}}
violation_tracker = {}

class GlobexBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix=None, intents=intents, help_command=None)

    async def setup_hook(self):
        # Registrierung der Views für Persistenz (Ohne Argumente, da asynchron)
        self.add_view(MainMenuView())
        self.add_view(AdmTimerView()) 
        self.add_view(LogSettingsView())
        
        self.check_adm_times.start() 
        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ {self.user} is online and secured!")
        
        # --- AUTOMATISCHER RUNDRUF AN ALLE SERVER ---
        for guild in self.guilds:
            channels = guild.text_channels
            if not channels:
                continue
                
            # Wir nehmen einen der ersten Kanäle für die Nachricht
            target_channel = channels[0]
            owner = guild.owner
            owner_mention = owner.mention if owner else "@Server-Eigentümer"
            
            broadcast_msg = (
                f"**__Globex Security__**\n\n"
                f"{owner_mention},\n"
                f"Please edit your menu again (Cloud Migration Update).\n"
                f"*Bitte stelle dein Menü erneut ein (Umstellung auf Cloud-Datenbank).* "
            )

            if target_channel.permissions_for(guild.me).send_messages:
                try:
                    # Optional: Deaktiviert, um Spam bei jedem Neustart zu vermeiden
                    # await target_channel.send(broadcast_msg)
                    print(f"📢 Bot bereit für: {guild.name}")
                except Exception as e:
                    print(f"❌ Fehler bei {guild.name}: {e}")

    # --- AUTOMATISCHER ZEIT-CHECK (BERLINER ZEIT) ---
    @tasks.loop(minutes=1)
    async def check_adm_times(self):
        tz_berlin = ZoneInfo("Europe/Berlin")
        now = datetime.datetime.now(tz_berlin).strftime("%H:%M")
        
        for guild in self.guilds:
            data = await db.get_data("adm_timer", guild.id)
            if not data or data.get("adm_status", 0) == 0:
                continue

            for i in [1, 2]:
                r_id = data.get(f"role_id_{i}")
                g_time = data.get(f"give_time_{i}")
                rem_time = data.get(f"remove_time_{i}")
                
                if r_id and str(r_id).isdigit() and g_time and rem_time:
                    if ":" in str(g_time) and ":" in str(rem_time):
                        role = guild.get_role(int(r_id))
                        if role:
                            if g_time < rem_time:
                                should_have_adm = g_time <= now < rem_time
                            else:
                                should_have_adm = now >= g_time or now < rem_time
                            
                            if role.permissions.administrator != should_have_adm:
                                perms = role.permissions
                                perms.administrator = should_have_adm
                                try:
                                    await role.edit(permissions=perms, reason=f"ADM-Timer Auto-Update ({now})")
                                    await send_globex_log(guild.id, "ADM Auto-Update", 
                                        f"Role {role.mention} Admin flag set to **{should_have_adm}** (Time: {now})")
                                except Exception as e:
                                    print(f"Update Error in {guild.name}: {e}")

bot = GlobexBot()

# --- HELPER FOR LIMITS ---
def is_limit_exceeded(guild_id, user_id, module, limit, timeframe):
    if not limit: return False
    if guild_id not in violation_tracker: violation_tracker[guild_id] = {}
    if user_id not in violation_tracker[guild_id]: violation_tracker[guild_id][user_id] = {}
    if module not in violation_tracker[guild_id][user_id]: violation_tracker[guild_id][user_id][module] = []
    
    now = datetime.datetime.now().timestamp()
    violation_tracker[guild_id][user_id][module] = [t for t in violation_tracker[guild_id][user_id][module] if now - t < (timeframe or 10)]
    violation_tracker[guild_id][user_id][module].append(now)
    return len(violation_tracker[guild_id][user_id][module]) >= limit

# --- LOGGING SYSTEM ---
async def send_globex_log(guild_id, title, description, color=discord.Color.blue()):
    settings = await db.get_data("settings", guild_id)
    if settings.get("log_status") == 1:
        log_cid = settings.get("log_channel")
        if log_cid and str(log_cid).isdigit():
            log_chan = bot.get_channel(int(log_cid))
            if log_chan:
                tz_berlin = ZoneInfo("Europe/Berlin")
                now = datetime.datetime.now(tz_berlin)
                time_str = now.strftime("%d.%m.%Y at %H:%M:%S")
                
                embed = discord.Embed(title="**__🗃 Globex Security Log__**", description=description, color=color)
                embed.add_field(name="Event:", value=title, inline=False)
                embed.set_footer(text=f"{time_str}")
                try:
                    await log_chan.send(embed=embed)
                except: pass

# --- CENTRAL PUNISHMENT SYSTEM ---
async def apply_punishment(member, module_prefix, guild_id):
    if not member or not isinstance(member, discord.Member): return 

    settings = await db.get_data("settings", guild_id)
    punishment = settings.get(f"{module_prefix}_punish") or "kick"
    reason_clean = module_prefix.replace('_', ' ').title()
    reason = f"Globex Security: {reason_clean} Protection"

    try:
        if punishment == "kick": await member.kick(reason=reason)
        elif punishment == "ban": await member.ban(reason=reason)
        elif punishment == "timeout":
            until = discord.utils.utcnow() + datetime.timedelta(hours=1)
            await member.timeout(until, reason=reason)
        
        await send_globex_log(guild_id, "Punishment Executed", 
            f"**User:** {member.mention} ({member.id})\n**Reason:** {reason_clean}\n**Action:** {punishment.capitalize()}")
            
    except discord.Forbidden:
        await send_globex_log(guild_id, "⚠️ MISSING PERMISSIONS", 
            f"I don't have enough permissions to punish {member.mention} ({punishment}).", 
            color=discord.Color.red())

# --- ADM TIMER ENFORCEMENT ---
@bot.event
async def on_guild_role_update(before, after):
    if before.permissions.administrator == after.permissions.administrator: return
    
    data = await db.get_data("adm_timer", after.guild.id)
    if not data or data.get("adm_status", 0) == 0:
        return

    idx = None
    if str(after.id) == str(data.get("role_id_1")): idx = 1
    elif str(after.id) == str(data.get("role_id_2")): idx = 2
    
    if idx:
        tz_berlin = ZoneInfo("Europe/Berlin")
        now = datetime.datetime.now(tz_berlin).strftime("%H:%M")
        g_time = data.get(f"give_time_{idx}")
        rem_time = data.get(f"remove_time_{idx}")
        
        if ":" in str(g_time) and ":" in str(rem_time):
            if g_time < rem_time:
                is_allowed = g_time <= now < rem_time
            else:
                is_allowed = now >= g_time or now < rem_time
                
            if after.permissions.administrator != is_allowed:
                new_perms = after.permissions
                new_perms.administrator = is_allowed
                try:
                    await after.edit(permissions=new_perms, reason="ADM-Timer Enforcement")
                    await send_globex_log(after.guild.id, "ADM Role Corrected", 
                                         f"Role {after.mention} Admin flag set to {is_allowed} (Time: {now})", 
                                         color=discord.Color.orange())
                except: pass

# --- SECURITY EVENTS ---
@bot.event
async def on_message(message):
    if message.author.id == bot.user.id or message.webhook_id: return
    if not message.guild or message.author.bot: return
    
    if message.author.id == message.guild.owner_id or await db.is_on_list(message.guild.id, message.author.id, "whitelist"): return

    settings = await db.get_data("settings", message.guild.id)
    limits = await db.get_data("limits", message.guild.id)

    # ANTI-INVITE
    if settings.get("anti_invite_status") == 1:
        invites = re.findall(r"(discord\.gg/|discord\.com/invite/)\S+", message.content)
        if invites:
            try: await message.delete()
            except: pass
            l, t = limits.get("invite_limit") or 1, limits.get("invite_time") or 10
            if len(invites) >= l or is_limit_exceeded(message.guild.id, message.author.id, "invite", l, t):
                await apply_punishment(message.author, "anti_invite", message.guild.id)

    # ANTI-PING
    if settings.get("anti_ping_status") == 1:
        if message.mention_everyone:
            mode = settings.get("anti_ping_direct", "Direct")
            l, t = limits.get("ping_limit") or 1, limits.get("ping_time") or 10
            violation = is_limit_exceeded(message.guild.id, message.author.id, "ping", l, t)
            if mode == "Direct" or (mode == "Not Direct" and violation):
                try: await message.delete()
                except: pass
            if violation:
                await apply_punishment(message.author, "anti_ping", message.guild.id)

# --- ANTI-NUKE EVENTS ---
@bot.event
async def on_guild_channel_create(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_create, limit=1):
        if entry.user.id in [bot.user.id, channel.guild.owner_id] or await db.is_on_list(channel.guild.id, entry.user.id, "whitelist"): return
        settings = await db.get_data("settings", channel.guild.id)
        if settings.get("channel_create_status") == 1:
            if settings.get("channel_create_action", "delete") == "delete":
                try: await channel.delete()
                except: pass
            member = channel.guild.get_member(entry.user.id)
            if member: await apply_punishment(member, "anti_channel_create", channel.guild.id)

@bot.event
async def on_guild_channel_delete(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.channel_delete, limit=1):
        if entry.user.id in [bot.user.id, channel.guild.owner_id] or await db.is_on_list(channel.guild.id, entry.user.id, "whitelist"): return
        settings = await db.get_data("settings", channel.guild.id)
        if settings.get("channel_delete_status") == 1:
            member = channel.guild.get_member(entry.user.id)
            if member: await apply_punishment(member, "anti_channel_delete", channel.guild.id)

@bot.event
async def on_guild_role_create(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create, limit=1):
        if entry.user.id in [bot.user.id, role.guild.owner_id] or await db.is_on_list(role.guild.id, entry.user.id, "whitelist"): return
        settings = await db.get_data("settings", role.guild.id)
        if settings.get("role_create_status") == 1:
            try: await role.delete()
            except: pass
            member = role.guild.get_member(entry.user.id)
            if member: await apply_punishment(member, "anti_role_create", role.guild.id)

@bot.event
async def on_guild_role_delete(role):
    async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete, limit=1):
        if entry.user.id in [bot.user.id, role.guild.owner_id] or await db.is_on_list(role.guild.id, entry.user.id, "whitelist"): return
        settings = await db.get_data("settings", role.guild.id)
        if settings.get("role_delete_status") == 1:
            member = role.guild.get_member(entry.user.id)
            if member: await apply_punishment(member, "anti_role_delete", role.guild.id)

@bot.event
async def on_webhooks_update(channel):
    async for entry in channel.guild.audit_logs(action=discord.AuditLogAction.webhook_create, limit=1):
        if entry.user.id in [bot.user.id, channel.guild.owner_id] or await db.is_on_list(channel.guild.id, entry.user.id, "whitelist"): return
        settings = await db.get_data("settings", channel.guild.id)
        if settings.get("anti_webhook_status") == 1:
            webhooks = await channel.webhooks()
            for wh in webhooks:
                if wh.id == entry.target.id: 
                    try: await wh.delete()
                    except: pass
            member = channel.guild.get_member(entry.user.id)
            if member: await apply_punishment(member, "anti_webhook", channel.guild.id)

@bot.event
async def on_member_join(member):
    if not member.bot: return
    gid = member.guild.id
    settings = await db.get_data("settings", gid)
    if settings.get("anti_bot_status") == 1:
        async for entry in member.guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=1):
            if entry.user.id in [gid, member.guild.owner_id] or await db.is_on_list(gid, entry.user.id, "whitelist"): return
            try: await member.kick(reason="Anti-Bot Join Protection")
            except: pass
            limits = await db.get_data("limits", gid)
            l = limits.get("bot_limit") or 1
            if is_limit_exceeded(gid, entry.user.id, "bot_join", l, 315360000):
                inviter = member.guild.get_member(entry.user.id)
                if inviter: await apply_punishment(inviter, "anti_bot_join", gid)

@bot.tree.command(name="config-setup-globex", description="Opens the Globex Security Headquarters")
async def setup(interaction: discord.Interaction):
    view = MainMenuView()
    await interaction.response.send_message(embed=view.base_embed(), view=view)

# --- STARTUP LOGIC ---
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")

if not MONGO_URL:
    print("❌ ERROR: MONGO_URL variable is missing in Railway Secrets!")
elif TOKEN:
    print("🚀 Connecting to MongoDB and starting Globex Security...")
    bot.run(TOKEN)
else:
    print("❌ ERROR: DISCORD_TOKEN is missing!")
