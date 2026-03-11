import discord
from discord import ui
import database as db
import re

# --- NEW ADM MODALS ---

class AdmRoleIDModal(ui.Modal):
    def __init__(self, index):
        super().__init__(title=f"Set ADM-Role-{index} ID")
        self.index = index
        self.role_id = ui.TextInput(label="Role ID", placeholder="Enter Role ID...", min_length=17, max_length=20)
        self.add_item(self.role_id)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.role_id.value.isdigit():
            return await interaction.response.send_message("❌ Numbers only allowed!", ephemeral=True)
        await db.update_data("adm_timer", interaction.guild_id, f"role_id_{self.index}", self.role_id.value)
        await interaction.response.edit_message(view=await AdmTimerView.create(interaction.guild_id))

class AdmTimeModal(ui.Modal):
    def __init__(self, index):
        super().__init__(title=f"Set Times for Role {index}")
        self.index = index
        self.give_input = ui.TextInput(label="Give Permission ADM (HH:MM)", placeholder="e.g. 13:34", min_length=5, max_length=5)
        self.remove_input = ui.TextInput(label="Remove Permission ADM (HH:MM)", placeholder="e.g. 17:57", min_length=5, max_length=5)
        self.add_item(self.give_input)
        self.add_item(self.remove_input)

    async def on_submit(self, interaction: discord.Interaction):
        pattern = re.compile(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
        if not pattern.match(self.give_input.value) or not pattern.match(self.remove_input.value):
            return await interaction.response.send_message("❌ Invalid format! Use HH:MM (00:00 - 23:59).", ephemeral=True)
        
        await db.update_data("adm_timer", interaction.guild_id, f"give_time_{self.index}", self.give_input.value)
        await db.update_data("adm_timer", interaction.guild_id, f"remove_time_{self.index}", self.remove_input.value)
        await interaction.response.edit_message(view=await AdmTimerView.create(interaction.guild_id))

# --- EXISTING MODALS ---

class LogChannelModal(ui.Modal, title="Config-Bot-Log Setup"):
    channel_id = ui.TextInput(label="Channel ID", placeholder="Enter the 18-digit ID...", min_length=17, max_length=20)
    async def on_submit(self, interaction: discord.Interaction):
        if not self.channel_id.value.isdigit():
            return await interaction.response.send_message("❌ Numbers only allowed!", ephemeral=True)
        await db.update_data("settings", interaction.guild_id, "log_channel", self.channel_id.value)
        await interaction.response.edit_message(view=await LogSettingsView.create(interaction.guild_id))

class LimitModal(ui.Modal):
    def __init__(self, title, db_col_limit, db_col_time, parent_view):
        super().__init__(title=title)
        self.db_col_limit, self.db_col_time, self.parent_view = db_col_limit, db_col_time, parent_view
        self.limit_input = ui.TextInput(label="Limit (Amount)", placeholder="Numbers only!", min_length=1, max_length=2)
        self.add_item(self.limit_input)
        if db_col_time:
            self.time_input = ui.TextInput(label="Timeframe (Seconds)", placeholder="Numbers only!", min_length=1, max_length=5)
            self.add_item(self.time_input)
            
    async def on_submit(self, interaction: discord.Interaction):
        if not self.limit_input.value.isdigit() or (self.db_col_time and not self.time_input.value.isdigit()):
            return await interaction.response.send_message("❌ Only numbers allowed!", ephemeral=True)
        
        await db.update_data("limits", interaction.guild_id, self.db_col_limit, int(self.limit_input.value))
        if self.db_col_time:
            await db.update_data("limits", interaction.guild_id, self.db_col_time, int(self.time_input.value))
            
        new_view = await ModuleSettingsView.create(self.parent_view.module_name, self.parent_view.db_prefix, interaction.guild_id, True, self.db_col_limit, self.db_col_time)
        await interaction.response.edit_message(view=new_view)

class ListManageModal(ui.Modal):
    def __init__(self, list_type, action, parent_view):
        super().__init__(title=f"{list_type.capitalize()}: {action}")
        self.list_type, self.action, self.parent_view = list_type, action, parent_view
        self.user_id = ui.TextInput(label="User ID", placeholder="18-digit ID...", min_length=17, max_length=20)
        self.add_item(self.user_id)
        
    async def on_submit(self, interaction: discord.Interaction):
        if not self.user_id.value.isdigit():
            return await interaction.response.send_message("❌ Numbers only!", ephemeral=True)
        uid = int(self.user_id.value)
        if self.action == "ADD": await db.add_to_list(interaction.guild_id, uid, self.list_type)
        else: await db.remove_from_list(interaction.guild_id, uid, self.list_type)
        await interaction.response.edit_message(content=await self.parent_view.get_content(interaction), view=self.parent_view)

# --- PERMS ---
async def check_perms(interaction, owner_only=False):
    if interaction.user.id == interaction.guild.owner_id: return True
    if not owner_only and await db.is_on_list(interaction.guild.id, interaction.user.id, "trusted"): return True
    await interaction.response.send_message("❌ No Permission!", ephemeral=True)
    return False

# --- VIEWS ---

class AdmTimerView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    async def create(cls, guild_id):
        self = cls()
        data = await db.get_data("adm_timer", guild_id)
        status = data.get("adm_status", 0)
        self.toggle_adm.label = f"Status: {'ON' if status == 1 else 'OFF'}"
        self.toggle_adm.style = discord.ButtonStyle.green if status == 1 else discord.ButtonStyle.red
        
        is_off = (status == 0)
        self.role1_btn.label = f"ADM-Role-1: {data.get('role_id_1', 'None')}"
        self.role1_btn.disabled = is_off
        self.time1_btn.label = f"Time: [{data.get('give_time_1', '00:00')} - {data.get('remove_time_1', '00:00')}]"
        self.time1_btn.disabled = is_off
        self.role2_btn.label = f"ADM-Role-2: {data.get('role_id_2', 'None')}"
        self.role2_btn.disabled = is_off
        self.time2_btn.label = f"Time: [{data.get('give_time_2', '00:00')} - {data.get('remove_time_2', '00:00')}]"
        self.time2_btn.disabled = is_off
        return self

    @ui.button(label="Status", row=0, custom_id="adm_status_toggle")
    async def toggle_adm(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        data = await db.get_data("adm_timer", interaction.guild_id)
        new_val = 1 if data.get("adm_status", 0) == 0 else 0
        await db.update_data("adm_timer", interaction.guild_id, "adm_status", new_val)
        await interaction.response.edit_message(view=await AdmTimerView.create(interaction.guild_id))

    @ui.button(style=discord.ButtonStyle.gray, row=1, custom_id="adm_r1")
    async def role1_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.send_modal(AdmRoleIDModal(1))

    @ui.button(style=discord.ButtonStyle.blurple, row=1, custom_id="adm_t1")
    async def time1_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.send_modal(AdmTimeModal(1))

    @ui.button(style=discord.ButtonStyle.gray, row=2, custom_id="adm_r2")
    async def role2_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.send_modal(AdmRoleIDModal(2))

    @ui.button(style=discord.ButtonStyle.blurple, row=2, custom_id="adm_t2")
    async def time2_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        await interaction.response.send_modal(AdmTimeModal(2))

    @ui.button(label="Back", style=discord.ButtonStyle.red, row=3, custom_id="adm_back")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

class LogSettingsView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @classmethod
    async def create(cls, guild_id):
        self = cls()
        settings = await db.get_data("settings", guild_id)
        status = settings.get("log_status", 0)
        self.toggle_btn.label = f"Status: {'ON' if status == 1 else 'OFF'}"
        self.toggle_btn.style = discord.ButtonStyle.green if status == 1 else discord.ButtonStyle.red
        channel_id = settings.get("log_channel", "Not yet processed")
        self.set_channel.label = f"Channel: {channel_id}"
        return self

    @ui.button(label="Status", custom_id="log_status_toggle")
    async def toggle_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        data = await db.get_data("settings", interaction.guild_id)
        new_val = 1 if data.get("log_status", 0) == 0 else 0
        await db.update_data("settings", interaction.guild_id, "log_status", new_val)
        await interaction.response.edit_message(view=await LogSettingsView.create(interaction.guild_id))

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
        collection = db.db[self.list_type]
        data = await collection.find_one({"_id": str(interaction.guild_id)})
        uids = data.get("users", []) if data else []
        
        entries = []
        for uid in uids:
            member = interaction.guild.get_member(int(uid))
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
    def __init__(self, module_name, db_prefix, has_limits, limit_col, time_col):
        super().__init__(timeout=None)
        self.module_name, self.db_prefix, self.limit_col, self.time_col = module_name, db_prefix, limit_col, time_col

    @classmethod
    async def create(cls, module_name, db_prefix, guild_id, has_limits=False, limit_col=None, time_col=None):
        self = cls(module_name, db_prefix, has_limits, limit_col, time_col)
        settings = await db.get_data("settings", guild_id)
        limits = await db.get_data("limits", guild_id)
        
        status = settings.get(f"{db_prefix}_status", 0)
        self.toggle_btn.label = f"Status: {'ON' if status == 1 else 'OFF'}"
        self.toggle_btn.style = discord.ButtonStyle.green if status == 1 else discord.ButtonStyle.red
        punish = settings.get(f"{db_prefix}_punish", "kick")
        self.select_punish.placeholder = f"Punishment: {punish.upper()}"
        
        if has_limits:
            l_val = limits.get(limit_col, "None")
            t_val = limits.get(time_col) if time_col else None
            self.edit_limits.label = f"Limit: {l_val}x / {t_val}s" if t_val else (f"Limit: {l_val}x" if l_val != "None" else "Not yet processed")
        else:
            self.edit_limits.label = "No Limits needed"
            self.edit_limits.disabled = True
            
        if db_prefix == "channel_create":
            current_action = settings.get("channel_create_action", "delete")
            btn = ui.Button(label=f"Extra Action: {current_action.upper()}", style=discord.ButtonStyle.gray, row=2)
            async def toggle_extra(interaction):
                if not await check_perms(interaction): return
                data = await db.get_data("settings", interaction.guild_id)
                new_val = "keep" if data.get("channel_create_action", "delete") == "delete" else "delete"
                await db.update_data("settings", interaction.guild_id, "channel_create_action", new_val)
                await interaction.response.edit_message(view=await ModuleSettingsView.create(module_name, db_prefix, interaction.guild_id, has_limits, limit_col, time_col))
            btn.callback = toggle_extra
            self.add_item(btn)
            
        if db_prefix == "anti_ping":
            current_direct = settings.get("anti_ping_direct", "Direct")
            self.add_item(ui.Button(label="Direct delete or after penalty?", disabled=True, row=2))
            btn_direct = ui.Button(label=f"Mode: {current_direct}", style=discord.ButtonStyle.gray, row=3)
            async def toggle_ping(interaction):
                if not await check_perms(interaction): return
                data = await db.get_data("settings", interaction.guild_id)
                new_val = "Not Direct" if data.get("anti_ping_direct", "Direct") == "Direct" else "Direct"
                await db.update_data("settings", interaction.guild_id, "anti_ping_direct", new_val)
                await interaction.response.edit_message(view=await ModuleSettingsView.create(module_name, db_prefix, interaction.guild_id, has_limits, limit_col, time_col))
            btn_direct.callback = toggle_ping
            self.add_item(btn_direct)
        return self
        
    @ui.button(label="Status", custom_id="mod_status_btn")
    async def toggle_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        data = await db.get_data("settings", interaction.guild_id)
        new_val = 1 if data.get(f"{self.db_prefix}_status", 0) == 0 else 0
        await db.update_data("settings", interaction.guild_id, f"{self.db_prefix}_status", new_val)
        await interaction.response.edit_message(view=await ModuleSettingsView.create(self.module_name, self.db_prefix, interaction.guild_id, not self.edit_limits.disabled, self.limit_col, self.time_col))
        
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
        await db.update_data("settings", interaction.guild_id, f"{self.db_prefix}_punish", select.values[0])
        await interaction.response.edit_message(view=await ModuleSettingsView.create(self.module_name, self.db_prefix, interaction.guild_id, not self.edit_limits.disabled, self.limit_col, self.time_col))
        
    @ui.button(label="Back", style=discord.ButtonStyle.red, row=4, custom_id="mod_back_btn")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

class SpamSelectView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    @ui.button(label="Anti-Invite", custom_id="spam_inv_btn")
    async def inv(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Invite", "anti_invite", self.guild_id, True, "invite_limit", "invite_time")
        await interaction.response.edit_message(content="🛡️ **Anti-Invite**", view=v)
    @ui.button(label="Anti-Ping", custom_id="spam_ping_btn")
    async def ping(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Ping", "anti_ping", self.guild_id, True, "ping_limit", "ping_time")
        await interaction.response.edit_message(content="🛡️ **Anti-Ping**", view=v)
    @ui.button(label="Anti-Webhook", custom_id="spam_web_btn")
    async def web(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Webhook", "anti_webhook", self.guild_id, True, "webhook_limit", None)
        await interaction.response.edit_message(content="🛡️ **Anti-Webhook**", view=v)
    @ui.button(label="Back", style=discord.ButtonStyle.red, row=2, custom_id="spam_back_btn")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

class NukeSelectView(ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    @ui.button(label="Anti-Channel Create", custom_id="nuke_cc_btn")
    async def cc(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Channel Create", "channel_create", self.guild_id)
        await interaction.response.edit_message(content="☢️ **Anti-Channel Create**", view=v)
    @ui.button(label="Anti-Channel Delete", custom_id="nuke_cd_btn")
    async def cd(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Channel Delete", "channel_delete", self.guild_id)
        await interaction.response.edit_message(content="☢️ **Anti-Channel Delete**", view=v)
    @ui.button(label="Anti-Role Create", row=1, custom_id="nuke_rc_btn")
    async def rc(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Role Create", "role_create", self.guild_id)
        await interaction.response.edit_message(content="☢️ **Anti-Role Create**", view=v)
    @ui.button(label="Anti-Role Delete", row=1, custom_id="nuke_rd_btn")
    async def rd(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Role Delete", "role_delete", self.guild_id)
        await interaction.response.edit_message(content="☢️ **Anti-Role Delete**", view=v)
    @ui.button(label="Anti-Bot Join", row=2, custom_id="nuke_bot_btn")
    async def bot_join(self, interaction: discord.Interaction, button: ui.Button):
        v = await ModuleSettingsView.create("Anti-Bot Join", "anti_bot", self.guild_id, True, "bot_limit", None)
        await interaction.response.edit_message(content="☢️ **Anti-Bot Join**", view=v)
    @ui.button(label="Back", style=discord.ButtonStyle.red, row=2, custom_id="nuke_back_btn")
    async def back(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="🛡️ HQ Main Menu", view=MainMenuView())

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
    
    @ui.button(label="Edit-ADM-Roles", style=discord.ButtonStyle.gray, emoji="⏱️", row=1, custom_id="main_adm_btn")
    async def adm_timer(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        v = await AdmTimerView.create(interaction.guild_id)
        await interaction.response.edit_message(content="⏱️ **ADM Role Timer Settings**", view=v)

    @ui.button(label="User-config-bot", style=discord.ButtonStyle.green, emoji="🔑", row=1, custom_id="main_trusted_btn")
    async def trusted(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        v = ListView("trusted")
        await interaction.response.edit_message(content=await v.get_content(interaction), view=v)
    @ui.button(label="🗂Config-Bot-Log", style=discord.ButtonStyle.gray, row=2, custom_id="main_log_btn")
    async def log_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction): return
        v = await LogSettingsView.create(interaction.guild_id)
        await interaction.response.edit_message(content="🗂 **Config-Bot-Log Settings**", view=v)
    @ui.button(label="Whitelist", style=discord.ButtonStyle.gray, row=2, custom_id="main_white_btn")
    async def white(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        v = ListView("whitelist")
        await interaction.response.edit_message(content=await v.get_content(interaction), view=v)
    @ui.button(label="Blacklist", style=discord.ButtonStyle.gray, row=3, custom_id="main_black_btn")
    async def black(self, interaction: discord.Interaction, button: ui.Button):
        if not await check_perms(interaction, owner_only=True): return
        v = ListView("blacklist")
        await interaction.response.edit_message(content=await v.get_content(interaction), view=v)
    @ui.button(label="Help / Hilfe", style=discord.ButtonStyle.gray, emoji="❔", row=3, custom_id="main_help_btn")
    async def help_btn(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(title="❔ User-config-bot Help Center (EN/DE)", color=0x3498db)
        en_text = (
            "**🔑 User-config-bot:** Authorized users who can manage security modules.\n"
            "**🔢 Limits/Timeframe:** ONLY numbers allowed.\n"
            "**⚠️ Anti-Invite/Ping:** 'Limit' refers to the **number of links/pings** in one message.\n"
            "**🛡️ Anti-Channel Create:** We recommend **'Keep'** action.\n"
            "**⏱️ Edit-ADM-Roles:** Set roles for timed Admin permissions."
        )
        de_text = (
            "**🔑 User-config-bot:** Autorisierte Nutzer für Sicherheitsmodule.\n"
            "**🔢 Limits/Zeitrahmen:** NUR Zahlen erlaubt.\n"
            "**⚠️ Anti-Invite/Ping:** 'Limit' ist die **Anzahl der Links/Pings** pro Nachricht.\n"
            "**🛡️ Anti-Channel Create:** Wir empfehlen die Aktion **'Keep'**.\n"
            "**⏱️ Edit-ADM-Roles:** Rollen für zeitgesteuerte Admin-Rechte."
        )
        embed.add_field(name="🇬🇧 English", value=en_text, inline=False)
        embed.add_field(name="🇩🇪 Deutsch", value=de_text, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
