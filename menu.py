import discord
from discord import ui
import database as db

# --- MODALS ---

class LogChannelModal(ui.Modal, title="Config-Bot-Log Setup"):
    channel_id = ui.TextInput(label="Channel ID", placeholder="Enter the 18-digit ID...", min_length=17, max_length=20)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.channel_id.value.isdigit():
            return await interaction.response.send_message("❌ Numbers only allowed! / Nur Zahlen erlaubt!", ephemeral=True)
        
        db.update_db("settings", interaction.guild_id, "log_channel", self.channel_id.value)
        await interaction.response.edit_message(view=LogSettingsView(interaction.guild_id))

class LimitModal(ui.Modal):
    def __init__(self, title, db_col_limit, db_col_time, parent_view):
        super().__init__(title=title)
        self.db_col_limit, self.db_col_time, self.parent_view = db_col_limit, db_col_time, parent_view
        self.limit_input = ui.TextInput(label="Limit (Amount / Anzahl)", placeholder="Only numbers / Nur Zahlen!", min_length=1, max_length=2)
        self.add_item(self.limit_input)
        if db_col_time:
            self.time_input = ui.TextInput(label="Timeframe (Seconds / Sekunden)", placeholder="Only numbers / Nur Zahlen!", min_length=1, max_length=5)
            self.add_item(self.time_input)

    async def on_submit(self, interaction: discord.Interaction):
        # Fix: Verhindert Absturz bei nicht-numerischer Eingabe
        if not self.limit_input.value.isdigit() or (self.db_col_time and not self.time_input.value.isdigit()):
            return await interaction.response.send_message("❌ Only numbers are allowed! / Nur Zahlen sind erlaubt!", ephemeral=True)

        db.update_db("limits", interaction.guild_id, self.db_col_limit, int(self.limit_input.value))
        if self.db_col_time:
            db.update_db("limits", interaction.guild_id, self.db_col_time, int(self.time_input.value))
        
        new_view = ModuleSettingsView(self.parent_view.module_name, self.parent_view.db_prefix, interaction.guild_id, True, self.db_col_limit, self.db_col_time)
        await interaction.response.edit_message(view=new_view)

class ListManageModal(ui.Modal):
    def __init__(self, list_type, action, parent_view):
        super().__init__(title=f"{list_type.capitalize()}: {action}")
        self.list_type, self.action, self.parent_view = list_type, action, parent_view
        self.user_id = ui.TextInput(label="User ID", placeholder="18-digit ID...", min_length=17, max_length=20)
        self.add_item(self.user_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.user_id.value.isdigit():
            return await interaction.response.send_message("❌ Numbers only! / Nur Zahlen!", ephemeral=True)
        
        uid = int(self.user_id.value)
        if self.action == "ADD": db.add_to_list(interaction.guild_id, uid, self.list_type)
        else: db.remove_from_list(interaction.guild_id, uid, self.list_type)
        await interaction.response.edit_message(content=await self.parent_view.get_content(interaction), view=self.parent_view)

# --- PERMS ---
async def check_perms(interaction, owner_only=False):
    if interaction.user.id == interaction.guild.owner_id: return True
    if not owner_only and db.is_on_list(interaction.guild.id, interaction.user.id, "trusted"): return True
    await interaction.response.send_message("❌ No Permission! / Keine Berechtigung!", ephemeral=True)
    return False

# --- VIEWS (LOG, LIST, MODULE) ---
# [Hier bleiben die restlichen Klassen LogSettingsView, ListView, ModuleSettingsView, SpamSelectView, NukeSelectView gleich wie zuvor...]
# Ich kürze hier für die Übersichtlichkeit, aber stelle sicher, dass die Help-Section unten vollständig ist.

class LogSettingsView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        settings = db.get_data("settings", guild_id)
        status = settings.get("log_status", 0)
        self.toggle_btn.label = f"Status: {'ON' if status == 1 else 'OFF'}"
        self.toggle_btn.style = discord.ButtonStyle.green if status == 1 else discord.ButtonStyle.red
        channel_id = settings.get("log_channel", "Not yet processed")
        self.set_channel.label = f"Channel: {channel_id}"

    @ui.button(label="Status", custom_id="log_status_toggle")
    async def toggle_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        data = db.get_data("settings", interaction.guild_id)
        new_val = 1 if data.get("log_status", 0) == 0 else 0
        db.update_db("settings", interaction.guild_id, "log_status", new_val)
        button.label = f"Status: {'ON' if new_val == 1 else 'OFF'}"
        button.style = discord.ButtonStyle.green if new_val == 1 else discord.ButtonStyle.red
        await interaction.response.edit_message(view=self)

    @ui.button(label="Set Channel ID", style=discord.ButtonStyle.blurple, custom_id="log_channel_id_set")
    async def set_channel(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.send_modal(LogChannelModal())

    @ui.button(label="Back", style=discord.ButtonStyle.red, row=2, custom_id="log_back_main")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

class ListView(ui.View):
    def __init__(self, list_type):
        super().__init__(timeout=None)
        self.list_type = list_type

    async def get_content(self, interaction):
        conn = db.connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM lists WHERE guild_id = ? AND list_type = ?", (interaction.guild_id, self.list_type))
        rows = cursor.fetchall()
        conn.close()
        entries = []
        for r in rows:
            uid = r[0]
            member = interaction.guild.get_member(uid)
            name = f"**{member.display_name}**" if member else f"`{uid}`"
            entries.append(f"• {name} [ID: `{uid}`]")
        display_name = "USER-CONFIG-BOT" if self.list_type == "trusted" else self.list_type.upper()
        user_list = "\n".join(entries) if entries else "_Empty / Leer_"
        return f"📋 **{display_name} MANAGEMENT**\n\n**Users:**\n{user_list}"

    @ui.button(label="Add ID", style=discord.ButtonStyle.green, custom_id="list_add_btn")
    async def add(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        await interaction.response.send_modal(ListManageModal(self.list_type, "ADD", self))

    @ui.button(label="Remove ID", style=discord.ButtonStyle.red, custom_id="list_remove_btn")
    async def rem(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        await interaction.response.send_modal(ListManageModal(self.list_type, "REMOVE", self))

    @ui.button(label="Back", style=discord.ButtonStyle.gray, row=1, custom_id="list_back_btn")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

class ModuleSettingsView(ui.View):
    def __init__(self, module_name, db_prefix, guild_id, has_limits=False, limit_col=None, time_col=None):
        super().__init__(timeout=None)
        self.module_name, self.db_prefix, self.limit_col, self.time_col = module_name, db_prefix, limit_col, time_col
        settings = db.get_data("settings", guild_id)
        limits = db.get_data("limits", guild_id)
        
        status = settings.get(f"{db_prefix}_status", 0)
        self.toggle_btn.label = f"Status: {'ON' if status == 1 else 'OFF'}"
        self.toggle_btn.style = discord.ButtonStyle.green if status == 1 else discord.ButtonStyle.red
        
        punish = settings.get(f"{db_prefix}_punish")
        self.select_punish.placeholder = f"Punishment: {punish.upper() if punish else 'NOT SET'}"
        
        if has_limits:
            l_val = limits.get(limit_col)
            t_val = limits.get(time_col) if time_col else None
            self.edit_limits.label = f"Limit: {l_val}x / {t_val}s" if t_val else (f"Limit: {l_val}x" if l_val else "Not yet processed")
        else:
            self.edit_limits.label = "No Limits needed"
            self.edit_limits.disabled = True

    @ui.button(label="Status", custom_id="mod_status_btn")
    async def toggle_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        data = db.get_data("settings", interaction.guild_id)
        new_val = 1 if data.get(f"{self.db_prefix}_status", 0) == 0 else 0
        db.update_db("settings", interaction.guild_id, f"{self.db_prefix}_status", new_val)
        button.label = f"Status: {'ON' if new_val == 1 else 'OFF'}"
        button.style = discord.ButtonStyle.green if new_val == 1 else discord.ButtonStyle.red
        await interaction.response.edit_message(view=self)

    @ui.button(label="Edit Limits", custom_id="mod_limits_btn")
    async def edit_limits(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.send_modal(LimitModal(self.module_name, self.limit_col, self.time_col, self))

    @ui.select(placeholder="Punishment", custom_id="mod_punish_select", options=[
        discord.SelectOption(label="Kick", value="kick"),
        discord.SelectOption(label="Ban", value="ban"),
        discord.SelectOption(label="Timeout", value="timeout")
    ])
    async def select_punish(self, interaction: discord.Interaction, select: ui.Select):
        if not await check_perms(interaction): return
        db.update_db("settings", interaction.guild_id, f"{self.db_prefix}_punish", select.values[0])
        select.placeholder = f"Punishment: {select.values[0].upper()}"
        await interaction.response.edit_message(view=self)

    @ui.button(label="Back", style=discord.ButtonStyle.red, row=3, custom_id="mod_back_btn")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

class SpamSelectView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    @ui.button(label="Anti-Invite", custom_id="spam_inv_btn")
    async def inv(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ **Anti-Invite**", view=ModuleSettingsView("Anti-Invite", "anti_invite", self.guild_id, True, "invite_limit", "invite_time"))
    @ui.button(label="Anti-Ping", custom_id="spam_ping_btn")
    async def ping(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ **Anti-Ping**", view=ModuleSettingsView("Anti-Ping", "anti_ping", self.guild_id, True, "ping_limit", "ping_time"))
    @ui.button(label="Anti-Webhook", custom_id="spam_web_btn")
    async def web(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ **Anti-Webhook**", view=ModuleSettingsView("Anti-Webhook", "anti_webhook", self.guild_id, True, "webhook_limit", None))
    @ui.button(label="Back", style=discord.ButtonStyle.red, row=2, custom_id="spam_back_btn")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

class NukeSelectView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    @ui.button(label="Anti-Channel Create", custom_id="nuke_cc_btn")
    async def cc(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="☢️ **Anti-Channel Create**", view=ModuleSettingsView("Anti-Channel Create", "channel_create", self.guild_id))
    @ui.button(label="Anti-Channel Delete", custom_id="nuke_cd_btn")
    async def cd(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="☢️ **Anti-Channel Delete**", view=ModuleSettingsView("Anti-Channel Delete", "channel_delete", self.guild_id))
    @ui.button(label="Anti-Role Create", row=1, custom_id="nuke_rc_btn")
    async def rc(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="☢️ **Anti-Role Create**", view=ModuleSettingsView("Anti-Role Create", "role_create", self.guild_id))
    @ui.button(label="Anti-Role Delete", row=1, custom_id="nuke_rd_btn")
    async def rd(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="☢️ **Anti-Role Delete**", view=ModuleSettingsView("Anti-Role Delete", "role_delete", self.guild_id))
    @ui.button(label="Anti-Bot Join", row=2, custom_id="nuke_bot_btn")
    async def bot_join(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="☢️ **Anti-Bot Join**", view=ModuleSettingsView("Anti-Bot Join", "anti_bot", self.guild_id, True, "bot_limit", None))
    @ui.button(label="Back", style=discord.ButtonStyle.red, row=2, custom_id="nuke_back_btn")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

# --- MAIN MENU & HELP ---
class MainMenuView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def base_embed(self):
        return discord.Embed(title="🛡️ Globex Security HQ", color=0x2b2d31, description="Choose a category / Wähle eine Kategorie:")

    @ui.button(label="Anti-Spam", style=discord.ButtonStyle.blurple, emoji="🛡️", custom_id="main_spam_btn")
    async def spam(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.edit_message(content="🛡️ **Anti-Spam Settings**", view=SpamSelectView(interaction.guild_id))

    @ui.button(label="Anti-Nuke", style=discord.ButtonStyle.danger, emoji="☢️", custom_id="main_nuke_btn")
    async def nuke(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.edit_message(content="☢️ **Anti-Nuke Settings**", view=NukeSelectView(interaction.guild_id))

    @ui.button(label="User-config-bot", style=discord.ButtonStyle.green, emoji="🔑", row=1, custom_id="main_trusted_btn")
    async def trusted(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        v = ListView("trusted")
        await interaction.response.edit_message(content=await v.get_content(interaction), view=v)

    @ui.button(label="🗂Config-Bot-Log", style=discord.ButtonStyle.gray, row=1, custom_id="main_log_btn")
    async def log_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.edit_message(content="🗂 **Config-Bot-Log Settings**", view=LogSettingsView(interaction.guild_id))

    @ui.button(label="Whitelist", style=discord.ButtonStyle.gray, row=2, custom_id="main_white_btn")
    async def white(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        v = ListView("whitelist")
        await interaction.response.edit_message(content=await v.get_content(interaction), view=v)

    @ui.button(label="Blacklist", style=discord.ButtonStyle.gray, row=2, custom_id="main_black_btn")
    async def black(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        v = ListView("blacklist")
        await interaction.response.edit_message(content=await v.get_content(interaction), view=v)

    @ui.button(label="Help / Hilfe", style=discord.ButtonStyle.gray, emoji="❔", row=3, custom_id="main_help_btn")
    async def help_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(title="❔ Globex Help Center (EN/DE)", color=0x3498db)
        
        # English Section
        en_text = (
            "**🔑 User-config-bot:** Authorized users who can manage security modules.\n"
            "**🔢 Limits/Timeframe:** ONLY numbers are allowed. If non-numeric input is given, the system prevents crashes.\n"
            "**⚠️ Anti-Invite/Ping:** 'Limit' refers to the **number of links or pings** within one message, not the number of attempts.\n"
            "**🗂 Config-Bot-Log:** Logs all actions to your chosen channel."
        )
        embed.add_field(name="🇬🇧 English", value=en_text, inline=False)
        
        # German Section
        de_text = (
            "**🔑 User-config-bot:** Autorisierte Nutzer, die Sicherheitsmodule verwalten dürfen.\n"
            "**🔢 Limits/Zeitrahmen:** NUR Zahlen sind erlaubt. Das System verhindert Abstürze bei falscher Eingabe.\n"
            "**⚠️ Anti-Invite/Ping:** 'Limit' bezieht sich auf die **Anzahl der Links oder Pings** in einer Nachricht, nicht auf die Versuche.\n"
            "**🗂 Config-Bot-Log:** Protokolliert alle Aktionen im gewählten Kanal."
        )
        embed.add_field(name="🇩🇪 Deutsch", value=de_text, inline=False)
        
        embed.description = "**Website:** [globex-security.vercel.app](https://globex-security.vercel.app)"
        await interaction.response.send_message(embed=embed, ephemeral=True)