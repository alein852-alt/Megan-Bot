"""
===========================================================
  📊 Megan Bot — v1.1
===========================================================
  🎯 متخصص في جمع المعلومات والإحصائيات
  📝 نظام طلبات الانضمام (Staff Applications)
  🎨 تصميم مطابق للهوية البصرية المطلوبة
  🆕 v1.1: /help محسّن يعرض كل الأوامر
===========================================================
"""

import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

# 🆕 تحميل ملف .env تلقائياً (محلياً فقط)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("megan")

# ============================================================
# CONFIG
# ============================================================
BOT_NAME = "Megan"
BOT_VERSION = "1.1"
BOT_FOOTER = "Megan Bot"
BOT_OWNER_ID = 1077949215772250143
BOT_OWNER_NAME = "aizenx000"

COLORS = {
    "primary":     0xE67E22,   # برتقالي
    "warning":     0xE67E22,
    "success":     0x2ECC71,   # أخضر
    "error":       0xE74C3C,   # أحمر
    "info":        0x3498DB,   # أزرق
    "dark":        0x2B2D31,
    "staff":       0x95A5A6,
    "checker":     0x3498DB,
    "influencer":  0x2ECC71,
    "pro_player":  0xF1C40F,
}

# 🆕 V1.7: أسماء الـ Roles لكل نوع طلب — تُعطى تلقائياً عند القبول
# البوت ينشئها لو غير موجودة
APPLICATION_ROLES = {
    "staff":       {"name": "🛡️ Staff",              "color": 0x95A5A6, "hoisted": True},
    "checker":     {"name": "🔍 Checker",            "color": 0x3498DB, "hoisted": True},
    "influencer":  {"name": "📱 Influencer",         "color": 0x2ECC71, "hoisted": True},
    "pro_player":  {"name": "🎮 Professional Player", "color": 0xF1C40F, "hoisted": True},
}

# 🆕 صورة التاطير — محفوظة محلياً
BANNER_IMAGE_LOCAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "megan-assets", "banner.png")
BANNER_IMAGE_URL = os.getenv("MEGAN_BANNER_URL", "")


# ============================================================
# DATABASE
# ============================================================
class Database:
    def __init__(self, db_path="megan_bot.db"):
        self.db_path = db_path
        self._init_db()

    def _conn(self):
        c = sqlite3.connect(self.db_path, timeout=30.0)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def _init_db(self):
        c = self._conn()
        try:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    admin_channel_id INTEGER DEFAULT NULL,
                    applications_channel_id INTEGER DEFAULT NULL,
                    applications_message_id INTEGER DEFAULT NULL,
                    banner_url TEXT DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    application_type TEXT NOT NULL,
                    answers TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_applications_guild
                    ON applications(guild_id);
                CREATE INDEX IF NOT EXISTS idx_applications_user
                    ON applications(user_id);
                CREATE INDEX IF NOT EXISTS idx_applications_status
                    ON applications(status);
            """)
            try:
                c.execute("ALTER TABLE guild_settings ADD COLUMN banner_url TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass
            c.commit()
        finally:
            c.close()

    def get_guild_settings(self, guild_id):
        c = self._conn()
        try:
            row = c.execute("SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)).fetchone()
            if not row:
                c.execute("INSERT INTO guild_settings (guild_id) VALUES (?)", (guild_id,))
                c.commit()
                row = c.execute("SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)).fetchone()
            return dict(row)
        finally:
            c.close()

    def set_admin_channel(self, guild_id, channel_id):
        c = self._conn()
        try:
            c.execute("""
                INSERT INTO guild_settings (guild_id, admin_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET admin_channel_id=?
            """, (guild_id, channel_id, channel_id))
            c.commit()
        finally:
            c.close()

    def set_applications_channel(self, guild_id, channel_id):
        c = self._conn()
        try:
            c.execute("""
                INSERT INTO guild_settings (guild_id, applications_channel_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET applications_channel_id=?
            """, (guild_id, channel_id, channel_id))
            c.commit()
        finally:
            c.close()

    def set_applications_message(self, guild_id, message_id):
        c = self._conn()
        try:
            c.execute("""
                INSERT INTO guild_settings (guild_id, applications_message_id)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET applications_message_id=?
            """, (guild_id, message_id, message_id))
            c.commit()
        finally:
            c.close()

    def set_banner_url(self, guild_id, banner_url):
        c = self._conn()
        try:
            c.execute("""
                INSERT INTO guild_settings (guild_id, banner_url)
                VALUES (?, ?)
                ON CONFLICT(guild_id) DO UPDATE SET banner_url=?
            """, (guild_id, banner_url, banner_url))
            c.commit()
        finally:
            c.close()

    def get_banner_url(self, guild_id):
        c = self._conn()
        try:
            row = c.execute("SELECT banner_url FROM guild_settings WHERE guild_id=?", (guild_id,)).fetchone()
            return row["banner_url"] if row else None
        finally:
            c.close()

    def save_application(self, guild_id, user_id, app_type, answers_json):
        c = self._conn()
        try:
            c.execute("""
                INSERT INTO applications (guild_id, user_id, application_type, answers)
                VALUES (?, ?, ?, ?)
            """, (guild_id, user_id, app_type, answers_json))
            c.commit()
            return c.execute("SELECT last_insert_rowid()").fetchone()[0]
        finally:
            c.close()

    def get_application(self, app_id):
        c = self._conn()
        try:
            row = c.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
            return dict(row) if row else None
        finally:
            c.close()

    def get_user_applications(self, guild_id, user_id, limit=10):
        c = self._conn()
        try:
            rows = c.execute("""
                SELECT * FROM applications
                WHERE guild_id=? AND user_id=?
                ORDER BY submitted_at DESC
                LIMIT ?
            """, (guild_id, user_id, limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()

    def get_all_applications(self, guild_id, status=None, limit=50):
        c = self._conn()
        try:
            if status:
                rows = c.execute("""
                    SELECT * FROM applications
                    WHERE guild_id=? AND status=?
                    ORDER BY submitted_at DESC
                    LIMIT ?
                """, (guild_id, status, limit)).fetchall()
            else:
                rows = c.execute("""
                    SELECT * FROM applications
                    WHERE guild_id=?
                    ORDER BY submitted_at DESC
                    LIMIT ?
                """, (guild_id, limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            c.close()

    def update_application_status(self, app_id, status):
        c = self._conn()
        try:
            c.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
            c.commit()
        finally:
            c.close()

    def get_application_stats(self, guild_id):
        c = self._conn()
        try:
            stats = {}
            for app_type in ["staff", "checker", "influencer", "pro_player"]:
                row = c.execute("""
                    SELECT COUNT(*) as total,
                           SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                           SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) as approved,
                           SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as rejected
                    FROM applications
                    WHERE guild_id=? AND application_type=?
                """, (guild_id, app_type)).fetchone()
                stats[app_type] = dict(row) if row else {"total": 0, "pending": 0, "approved": 0, "rejected": 0}
            return stats
        finally:
            c.close()


db = Database()


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def separator():
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


async def get_or_create_role(guild, role_name, color_hex):
    """🆕 V1.7: يبحث عن role، وينشئه لو غير موجود، ويرجعه."""
    # ابحث عن role موجود بنفس الاسم
    for role in guild.roles:
        if role.name == role_name:
            return role
    # أنشئ role جديد
    try:
        new_role = await guild.create_role(
            name=role_name,
            color=discord.Color(color_hex),
            hoist=True,
            reason=f"Megan Bot — Auto-create role for accepted applications"
        )
        logger.info(f"✅ Created role: {role_name}")
        return new_role
    except discord.Forbidden:
        logger.warning(f"❌ No permission to create role: {role_name}")
        return None
    except discord.HTTPException as e:
        logger.warning(f"❌ Failed to create role {role_name}: {e}")
        return None


async def assign_role_to_member(guild, member, app_type):
    """🆕 V1.7: يعطي الـ role المناسب للعضو حسب نوع الطلب."""
    if app_type not in APPLICATION_ROLES:
        return None
    role_config = APPLICATION_ROLES[app_type]
    role = await get_or_create_role(guild, role_config["name"], role_config["color"])
    if not role:
        return None
    try:
        if role not in member.roles:
            await member.add_roles(role, reason=f"Application accepted — {app_type}")
            logger.info(f"📥 Added role {role.name} to {member.display_name}")
        return role
    except (discord.HTTPException, discord.Forbidden) as e:
        logger.warning(f"❌ Failed to add role {role.name} to {member.id}: {e}")
        return None


def get_application_emoji(app_type):
    return {
        "staff":       "🛡️",
        "checker":     "🔍",
        "influencer":  "📱",
        "pro_player":  "🎮",
    }.get(app_type, "📝")


def get_application_label(app_type):
    return {
        "staff":       "Staff",
        "checker":     "Checker",
        "influencer":  "Influencer",
        "pro_player":  "Professional Player",
    }.get(app_type, "Unknown")


def get_application_color(app_type):
    return {
        "staff":       COLORS["staff"],
        "checker":     COLORS["checker"],
        "influencer":  COLORS["influencer"],
        "pro_player":  COLORS["pro_player"],
    }.get(app_type, COLORS["primary"])


# ============================================================
# APPLICATION QUESTIONS
# ============================================================
APPLICATION_QUESTIONS = {
    "staff": {
        "title": "Application for Staff",
        "questions": [
            {"label": "Chhal fl3mar dyalk ?", "placeholder": "اكتب عمرك", "required": True, "style": discord.TextStyle.short},
            {"label": "Wach kat9assar apostado ?", "placeholder": "نعم / لا", "required": True, "style": discord.TextStyle.short},
            {"label": "Wach 3amrak konti staff fchi server ?", "placeholder": "اكتب تجربتك السابقة", "required": True, "style": discord.TextStyle.paragraph},
            {"label": "bach ta9dar t3awna fserver ?", "placeholder": "كيف تساعدنا؟", "required": True, "style": discord.TextStyle.paragraph},
        ],
    },
    "checker": {
        "title": "Application for Checker",
        "questions": [
            {"label": "chcker d pc ou la iphone ou android", "placeholder": "PC / iPhone / Android", "required": True, "style": discord.TextStyle.short},
            {"label": "chno tools li kt5dm bihom", "placeholder": "اكتب الأدوات اللي تستعملها", "required": True, "style": discord.TextStyle.short},
            {"label": "ch7al l age dialk", "placeholder": "عمرك", "required": True, "style": discord.TextStyle.short},
            {"label": "wx active f server", "placeholder": "نعم / لا + كم ساعة باليوم", "required": True, "style": discord.TextStyle.short},
            {"label": "ch7al rank dialk f server", "placeholder": "RANK #?", "required": True, "style": discord.TextStyle.short},
        ],
    },
    "influencer": {
        "title": "Application for influencer",
        "questions": [
            {"label": "how much folowers you have?", "placeholder": "عدد المتابعين", "required": True, "style": discord.TextStyle.short},
            {"label": "what is your average views?", "placeholder": "متوسط المشاهدات", "required": True, "style": discord.TextStyle.short},
            {"label": "akhir video la7tih mn imta?", "placeholder": "آخر فيديو رفعته متى؟", "required": True, "style": discord.TextStyle.short},
            {"label": "will you post a video about server?", "placeholder": "نعم / لا", "required": True, "style": discord.TextStyle.short},
            {"label": "username f tiktok (ou la platform li ktlo7)", "placeholder": "@username", "required": True, "style": discord.TextStyle.short},
        ],
    },
    "pro_player": {
        "title": "Application for professional player",
        "questions": [
            {"label": "Ch7al rank dialk f server ?", "placeholder": "RANK #?", "required": True, "style": discord.TextStyle.short},
            {"label": "ch7al dial loses 3ndk?", "placeholder": "عدد الخسارات", "required": True, "style": discord.TextStyle.short},
            {"label": "iphone, android ou la pc ? (bx ktl3b)", "placeholder": "iPhone / Android / PC", "required": True, "style": discord.TextStyle.short},
            {"label": "ila 3ndk tiktok 3tina user (nchofo videos)", "placeholder": "@username (ou leave)", "required": True, "style": discord.TextStyle.short},
            {"label": "wx active ?", "placeholder": "نعم / لا + كم ساعة", "required": True, "style": discord.TextStyle.short},
        ],
    },
}


# ============================================================
# BOT SETUP
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    logger.info(f"✅ {bot.user} online!")
    logger.info(f"📊 Megan Bot v{BOT_VERSION}")
    logger.info(f"👑 Owner: {BOT_OWNER_NAME}")
    logger.info(f"🏠 Servers: {len(bot.guilds)}")

    bot.add_view(ApplicationsView())

    try:
        synced = await bot.tree.sync()
        logger.info(f"🔄 Synced {len(synced)} slash commands")
    except Exception as e:
        logger.exception(f"Failed to sync commands: {e}")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="Applications | /help"),
        status=discord.Status.online
    )


# ============================================================
# APPLICATIONS VIEW (اللائحة الرئيسية)
# ============================================================
class ApplicationsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Staff", style=discord.ButtonStyle.secondary, custom_id="megan_app_staff", emoji="🛡️")
    async def staff_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("staff"))

    @discord.ui.button(label="Checker", style=discord.ButtonStyle.primary, custom_id="megan_app_checker", emoji="🔍")
    async def checker_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("checker"))

    @discord.ui.button(label="influencer", style=discord.ButtonStyle.success, custom_id="megan_app_influencer", emoji="📱")
    async def influencer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("influencer"))

    @discord.ui.button(label="professional player", style=discord.ButtonStyle.success, custom_id="megan_app_pro_player", emoji="🎮")
    async def pro_player_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("pro_player"))


# ============================================================
# APPLICATION MODAL
# ============================================================
class ApplicationModal(discord.ui.Modal):
    def __init__(self, app_type: str):
        self.app_type = app_type
        config = APPLICATION_QUESTIONS[app_type]
        super().__init__(title=config["title"], timeout=600)

        for q in config["questions"]:
            text_input = discord.ui.TextInput(
                label=q["label"],
                placeholder=q.get("placeholder", ""),
                required=q.get("required", True),
                style=q.get("style", discord.TextStyle.short),
                max_length=1024 if q.get("style") == discord.TextStyle.paragraph else 200,
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        import json
        answers = []
        for child in self.children:
            if isinstance(child, discord.ui.TextInput):
                answers.append({"label": child.label, "value": child.value})

        app_id = db.save_application(
            interaction.guild.id,
            interaction.user.id,
            self.app_type,
            json.dumps(answers, ensure_ascii=False)
        )

        # 🆕 V1.6: رسالة التأكيد تحتوي على الصورة الزرقاء
        success_embed = discord.Embed(
            title="✅  Application Submitted",
            description=(
                f"> 🎯  **Type:**  {get_application_emoji(self.app_type)}  {get_application_label(self.app_type)}\n"
                f"> 🆔  **Application ID:**  `#{app_id}`\n"
                f"> 📅  **Submitted at:**  {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n"
                f"{separator()}\n"
                f"> 📬  ستتم مراجعة طلبك من قبل الأدمنز قريباً.\n"
                f"> ⏳  يرجى الانتظار — سيتم إعلامك بالنتيجة."
            ),
            color=COLORS["success"],
            timestamp=discord.utils.utcnow()
        )
        success_embed.set_footer(text=f"{BOT_FOOTER}  •  Application #{app_id}")
        if interaction.guild.icon:
            success_embed.set_thumbnail(url=interaction.guild.icon.url)
        # 🆕 V1.6: أضف الصورة الزرقاء في رسالة التأكيد
        if os.path.exists(BANNER_IMAGE_LOCAL_PATH):
            try:
                with open(BANNER_IMAGE_LOCAL_PATH, "rb") as f:
                    banner_file = discord.File(f, filename="megan_banner.png")
                success_embed.set_image(url="attachment://megan_banner.png")
                await interaction.response.send_message(embed=success_embed, file=banner_file, ephemeral=True)
            except Exception as e:
                logger.warning(f"Failed to attach banner to success message: {e}")
                await interaction.response.send_message(embed=success_embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=success_embed, ephemeral=True)
        await self.send_to_admin_channel(interaction, app_id, answers)

    async def send_to_admin_channel(self, interaction: discord.Interaction, app_id: int, answers: list):
        try:
            settings = db.get_guild_settings(interaction.guild.id)
            admin_channel_id = settings.get("admin_channel_id")
            if not admin_channel_id:
                logger.warning(f"No admin channel set for guild {interaction.guild.id}")
                return

            admin_channel = interaction.guild.get_channel(admin_channel_id)
            if not admin_channel:
                logger.warning(f"Admin channel {admin_channel_id} not found")
                return

            app_type = self.app_type
            app_label = get_application_label(app_type)
            app_emoji = get_application_emoji(app_type)
            app_color = get_application_color(app_type)

            embed = discord.Embed(
                title=f"{app_emoji}  New {app_label} Application",
                description=(
                    f"> 👤  **User:**  {interaction.user.mention}  (`{interaction.user.id}`)\n"
                    f"> 📛  **Username:**  {interaction.user.display_name}\n"
                    f"> 🆔  **Application ID:**  `#{app_id}`\n"
                    f"> 📅  **Submitted:**  {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n"
                    f"> 📊  **Status:**  `Pending`\n"
                    f"{separator()}"
                ),
                color=app_color,
                timestamp=discord.utils.utcnow()
            )

            for ans in answers:
                embed.add_field(
                    name=f"📝  {ans['label']}",
                    value=f"```\n{ans['value']}\n```",
                    inline=False
                )

            embed.set_footer(text=f"{BOT_FOOTER}  •  Application #{app_id}  •  {app_label}")
            if interaction.user.display_avatar:
                embed.set_thumbnail(url=interaction.user.display_avatar.url)

            view = AdminApplicationView(app_id, interaction.user.id, self.app_type)
            await admin_channel.send(
                content=f"🔔  **New Application**  —  {interaction.user.mention}",
                embed=embed,
                view=view
            )
            logger.info(f"📤 Application #{app_id} sent to admin channel #{admin_channel.name}")

        except Exception as e:
            logger.exception(f"Failed to send application to admin channel: {e}")


# ============================================================
# ADMIN APPLICATION VIEW
# ============================================================
class AdminApplicationView(discord.ui.View):
    def __init__(self, app_id: int, applicant_id: int, app_type: str = None):
        super().__init__(timeout=None)
        self.app_id = app_id
        self.applicant_id = applicant_id
        self.app_type = app_type  # 🆕 V1.7: نوع الطلب (staff/checker/influencer/pro_player)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, custom_id="megan_app_accept", emoji="✅")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
            return

        # 🆕 V1.7: اجلب نوع الطلب من الـ DB لو غير محدد في الـ view
        if not self.app_type:
            app = db.get_application(self.app_id)
            if app:
                self.app_type = app.get("application_type")

        db.update_application_status(self.app_id, "approved")
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.color = COLORS["success"]
            embed.add_field(
                name="✅  Decision",
                value=f"> **Accepted by:**  {interaction.user.mention}\n> **At:**  {discord.utils.format_dt(discord.utils.utcnow(), 'F')}",
                inline=False
            )
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message(
            f"✅  تم قبول الطلب `#{self.app_id}` من <@{self.applicant_id}>",
            ephemeral=True
        )

        try:
            applicant = await interaction.guild.fetch_member(self.applicant_id)
            if applicant:
                # 🆕 V1.7: أعطِ الـ role تلقائياً حسب نوع الطلب
                assigned_role = None
                if self.app_type:
                    assigned_role = await assign_role_to_member(interaction.guild, applicant, self.app_type)

                dm_embed = discord.Embed(
                    title="🎉  Application Accepted!",
                    description=(
                        f"> 🏆  مبروك! تم قبول طلبك في **{interaction.guild.name}**\n"
                        f"> 🆔  **Application ID:**  `#{self.app_id}`\n"
                        f"> 👮  **Accepted by:**  {interaction.user.mention}\n"
                        + (f"> 🏅  **Role granted:**  {assigned_role.mention}\n" if assigned_role else "")
                        + f"{separator()}\n"
                        f"> 📬  سيتم التواصل معك قريباً للمتابعة."
                    ),
                    color=COLORS["success"],
                    timestamp=discord.utils.utcnow()
                )
                dm_embed.set_footer(text=f"{BOT_FOOTER}  •  {interaction.guild.name}")
                await applicant.send(embed=dm_embed)

                # 🆕 رد إضافي للأدمن بتأكيد إعطاء الـ role
                if assigned_role:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="🏅  Role Granted",
                            description=(
                                f"> 👤  **User:**  {applicant.mention}\n"
                                f"> 🏅  **Role:**  {assigned_role.mention}\n"
                                f"> 📝  **Type:**  `{self.app_type}`"
                            ),
                            color=COLORS["success"]
                        ),
                        ephemeral=True
                    )
        except Exception as e:
            logger.warning(f"Could not DM applicant {self.applicant_id}: {e}")

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger, custom_id="megan_app_reject", emoji="❌")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
            return

        db.update_application_status(self.app_id, "rejected")
        embed = interaction.message.embeds[0] if interaction.message.embeds else None
        if embed:
            embed.color = COLORS["error"]
            embed.add_field(
                name="❌  Decision",
                value=f"> **Rejected by:**  {interaction.user.mention}\n> **At:**  {discord.utils.format_dt(discord.utils.utcnow(), 'F')}",
                inline=False
            )
        await interaction.message.edit(embed=embed, view=None)
        await interaction.response.send_message(
            f"❌  تم رفض الطلب `#{self.app_id}` من <@{self.applicant_id}>",
            ephemeral=True
        )

        try:
            applicant = await interaction.guild.fetch_member(self.applicant_id)
            if applicant:
                dm_embed = discord.Embed(
                    title="❌  Application Rejected",
                    description=(
                        f"> 📋  تم رفض طلبك في **{interaction.guild.name}**\n"
                        f"> 🆔  **Application ID:**  `#{self.app_id}`\n"
                        f"> 👮  **Reviewed by:**  {interaction.user.mention}\n"
                        f"{separator()}\n"
                        f"> 💪  حظ أوفر في المرة القادمة!"
                    ),
                    color=COLORS["error"],
                    timestamp=discord.utils.utcnow()
                )
                dm_embed.set_footer(text=f"{BOT_FOOTER}  •  {interaction.guild.name}")
                await applicant.send(embed=dm_embed)
        except Exception as e:
            logger.warning(f"Could not DM applicant {self.applicant_id}: {e}")


# ============================================================
# SLASH COMMANDS
# ============================================================
@bot.tree.command(name="setup-applications", description="📋 إنشاء لائحة طلبات الانضمام في شات محدد (Admin only)")
@app_commands.describe(channel="الشات اللي تحط فيه اللائحة")
@app_commands.default_permissions(manage_guild=True)
async def setup_applications(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
        return

    await interaction.response.send_message(
        embed=discord.Embed(
            title="⏳  جارٍ الإعداد...",
            description="> 📋  جاري إنشاء لائحة الطلبات ورفع صورة الـ banner...",
            color=COLORS["primary"]
        ),
        ephemeral=True
    )

    db.set_applications_channel(interaction.guild.id, channel.id)

    # 🆕 حدّد رابط الـ banner
    banner_url = db.get_banner_url(interaction.guild.id)
    if not banner_url and BANNER_IMAGE_URL:
        banner_url = BANNER_IMAGE_URL

    # 🆕 ارفع الصورة المحلية لو ما فيه رابط
    if not banner_url and os.path.exists(BANNER_IMAGE_LOCAL_PATH):
        try:
            with open(BANNER_IMAGE_LOCAL_PATH, "rb") as f:
                banner_file = discord.File(f, filename="megan_banner.png")
                upload_msg = await channel.send(file=banner_file)
                if upload_msg.attachments:
                    banner_url = upload_msg.attachments[0].url
                    db.set_banner_url(interaction.guild.id, banner_url)
                    try:
                        await upload_msg.delete()
                    except:
                        pass
                    logger.info(f"🖼️  Banner uploaded and saved: {banner_url}")
        except Exception as e:
            logger.warning(f"Failed to upload banner: {e}")

    # 🆕 V1.7: صورتان متتاليتان + النص + الأزرار
    # الرسالة الأولى: صورة كبيرة (1)
    # الرسالة الثانية: صورة كبيرة (2) + النص + الأزرار
    banner_file_1 = None
    banner_file_2 = None
    if os.path.exists(BANNER_IMAGE_LOCAL_PATH):
        try:
            with open(BANNER_IMAGE_LOCAL_PATH, "rb") as f:
                banner_file_1 = discord.File(f, filename="megan_banner1.png")
            with open(BANNER_IMAGE_LOCAL_PATH, "rb") as f:
                banner_file_2 = discord.File(f, filename="megan_banner2.png")
        except Exception as e:
            logger.warning(f"Failed to load banner files: {e}")

    # 🆕 رسالة 1: الصورة الأولى فقط
    if banner_file_1:
        image_embed_1 = discord.Embed(color=COLORS["primary"])
        image_embed_1.set_image(url="attachment://megan_banner1.png")
        await channel.send(embed=image_embed_1, file=banner_file_1)
        logger.info(f"🖼️  Banner image 1 sent")

    # 🆕 رسالة 2: الصورة الثانية + النص + الأزرار
    embed = discord.Embed(
        title="📋  طلبات الانضمام للفريق",
        description=(
            f"> اقرأ كل شيء بعناية قبل التقديم\n"
            f"{separator()}\n"
            f"\n"
            f"🟠  **شروط الانضمام للفريق**\n"
            f"> ─  يجب أن تكون نشطاً وناضجاً\n"
            f"> ─  سلوك جيد واحترام للجميع\n"
            f"> ─  عدم استغلال الصلاحيات\n"
            f"> ─  معرفة قوانين السيرفر وتطبيقها\n"
            f"> ─  لا دراما بين الفريق ولا محاباة\n"
            f"> ─  يجب الاستماع لقرارات الفريق الأعلى\n"
            f"> ─  خبرة سابقة في الفريق ميزة وليست شرطاً\n"
            f"\n"
            f"🟠  **كيفية التقديم**\n"
            f"> ─  اضغط على أحد الأزرار بالأسفل وأجب على الأسئلة\n"
            f"\n"
            f"{separator()}\n"
            f"> ⚠️  أي استغلال كبير أو كذب في الطلب قد يؤدي إلى حظر  💖"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{interaction.guild.name}  •  طلبات الانضمام", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"{BOT_FOOTER}  •  طلبات الانضمام")
    # 🆕 V1.7: الصورة الثانية في embed النص
    if banner_file_2:
        embed.set_image(url="attachment://megan_banner2.png")

    view = ApplicationsView()
    # 🆕 V1.7: أرسل embed النص مع الصورة الثانية كـ attachment
    if banner_file_2:
        msg = await channel.send(embed=embed, view=view, file=banner_file_2)
    else:
        msg = await channel.send(embed=embed, view=view)
    db.set_applications_message(interaction.guild.id, msg.id)

    confirm_embed = discord.Embed(
        title="✅  تم الإعداد بنجاح",
        description=(
            f"> 📋  **قناة الطلبات:**  {channel.mention}\n"
            f"> 🆔  **رقم الرسالة:**  `{msg.id}`\n"
            f"> 🖼️  **الصورة:**  {'✅ مرفوعة' if banner_url else '❌ غير متوفرة'}\n"
            f"> 📅  **تاريخ الإنشاء:**  {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n"
            f"{separator()}\n"
            f"> 💡  اللاعبون يمكنهم الآن الضغط على الأزرار للتقديم.\n"
            f"> ⚠️  لا تنسَ تحديد شات الأدمن بـ `/set-admin-channel`"
        ),
        color=COLORS["success"],
        timestamp=discord.utils.utcnow()
    )
    confirm_embed.set_footer(text=f"{BOT_FOOTER}  •  الإعداد")

    await interaction.edit_original_response(embed=confirm_embed)
    logger.info(f"📋 Applications setup in {interaction.guild.name} #{channel.name}")


@bot.tree.command(name="set-admin-channel", description="🔔 تحديد شات الأدمن اللي ترسل له الطلبات (Admin only)")
@app_commands.describe(channel="الشات اللي تحب تستقبل فيه الطلبات")
@app_commands.default_permissions(manage_guild=True)
async def set_admin_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
        return

    db.set_admin_channel(interaction.guild.id, channel.id)

    confirm_embed = discord.Embed(
        title="✅  Admin Channel Set",
        description=(
            f"> 🔔  **Admin channel:**  {channel.mention}\n"
            f"> 📅  **Set at:**  {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n"
            f"{separator()}\n"
            f"> 📬  كل الطلبات الجديدة ستصل لهذا الشات."
        ),
        color=COLORS["success"],
        timestamp=discord.utils.utcnow()
    )
    confirm_embed.set_footer(text=f"{BOT_FOOTER}  •  Admin Channel")

    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
    logger.info(f"🔔 Admin channel set to #{channel.name} in {interaction.guild.name}")


@bot.tree.command(name="myapplications", description="📨 عرض طلباتي السابقة")
async def my_applications(interaction: discord.Interaction):
    apps = db.get_user_applications(interaction.guild.id, interaction.user.id, limit=10)

    if not apps:
        no_apps_embed = discord.Embed(
            title="📭  No Applications",
            description=(
                f"> 📋  ليس لديك أي طلبات سابقة.\n"
                f"> 💡  اذهب لقناة الطلبات واضغط على أحد الأزرار للتقديم."
            ),
            color=COLORS["info"],
            timestamp=discord.utils.utcnow()
        )
        no_apps_embed.set_footer(text=f"{BOT_FOOTER}  •  My Applications")
        await interaction.response.send_message(embed=no_apps_embed, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📨  Applications — {interaction.user.display_name}",
        description=(
            f"> 👤  **User:**  {interaction.user.mention}\n"
            f"> 📊  **Total:**  `{len(apps)}`\n"
            f"{separator()}"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )

    for app in apps:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(app["status"], "❓")
        app_emoji = get_application_emoji(app["application_type"])
        app_label = get_application_label(app["application_type"])
        submitted = app["submitted_at"][:19] if app["submitted_at"] else "N/A"

        embed.add_field(
            name=f"{app_emoji}  #{app['id']}  —  {app_label}  {status_emoji}",
            value=f"> 📅  `{submitted}`  •  **Status:**  `{app['status']}`",
            inline=False
        )

    embed.set_footer(text=f"{BOT_FOOTER}  •  My Applications")
    if interaction.user.display_avatar:
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="application-stats", description="📊 إحصائيات الطلبات (Admin only)")
@app_commands.default_permissions(manage_guild=True)
async def application_stats(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
        return

    stats = db.get_application_stats(interaction.guild.id)
    total_all = sum(s["total"] for s in stats.values())
    pending_all = sum(s["pending"] for s in stats.values())
    approved_all = sum(s["approved"] for s in stats.values())
    rejected_all = sum(s["rejected"] for s in stats.values())

    embed = discord.Embed(
        title="📊  Application Statistics",
        description=(
            f"> 🏠  **Server:**  {interaction.guild.name}\n"
            f"> 📊  **Total:**  `{total_all}`\n"
            f"> ⏳  **Pending:**  `{pending_all}`\n"
            f"> ✅  **Approved:**  `{approved_all}`\n"
            f"> ❌  **Rejected:**  `{rejected_all}`\n"
            f"{separator()}"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )

    for app_type, s in stats.items():
        emoji = get_application_emoji(app_type)
        label = get_application_label(app_type)
        embed.add_field(
            name=f"{emoji}  {label}",
            value=(
                f"> 📊  Total:  `{s['total']}`\n"
                f"> ⏳  Pending:  `{s['pending']}`\n"
                f"> ✅  Approved:  `{s['approved']}`\n"
                f"> ❌  Rejected:  `{s['rejected']}`"
            ),
            inline=True
        )

    embed.set_footer(text=f"{BOT_FOOTER}  •  Stats")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="recent-applications", description="📋 عرض آخر الطلبات (Admin only)")
@app_commands.describe(limit="عدد الطلبات (افتراضي 10)")
@app_commands.default_permissions(manage_guild=True)
async def recent_applications(interaction: discord.Interaction, limit: int = 10):
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
        return

    if limit < 1: limit = 1
    if limit > 25: limit = 25

    apps = db.get_all_applications(interaction.guild.id, limit=limit)

    if not apps:
        embed = discord.Embed(
            title="📭  No Applications",
            description="> 📋  لا توجد طلبات بعد.",
            color=COLORS["info"]
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title=f"📋  Recent Applications  —  Last {len(apps)}",
        description=(
            f"> 🏠  **Server:**  {interaction.guild.name}\n"
            f"> 📊  **Showing:**  `{len(apps)}` applications\n"
            f"{separator()}"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )

    for app in apps:
        member = interaction.guild.get_member(app["user_id"])
        name = member.display_name if member else f"User#{app['user_id']}"
        mention = member.mention if member else f"<@{app['user_id']}>"
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(app["status"], "❓")
        emoji = get_application_emoji(app["application_type"])
        label = get_application_label(app["application_type"])
        submitted = app["submitted_at"][:19] if app["submitted_at"] else "N/A"

        embed.add_field(
            name=f"{emoji}  #{app['id']}  —  {name}  {status_emoji}",
            value=(
                f"> 👤  {mention}\n"
                f"> 📝  `{label}`\n"
                f"> 📅  `{submitted}`  •  **Status:**  `{app['status']}`"
            ),
            inline=False
        )

    embed.set_footer(text=f"{BOT_FOOTER}  •  Recent")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# 🆕 /help — يعرض كل أوامر البوت
# ============================================================
@bot.tree.command(name="help", description="❓ عرض كل أوامر Megan Bot")
async def help_cmd(interaction: discord.Interaction):
    """❓ Help command — يعرض كل الأوامر."""
    is_admin = interaction.user.guild_permissions.manage_guild or interaction.user.id == BOT_OWNER_ID

    # 🆕 Embed رئيسي
    main_embed = discord.Embed(
        title=f"📊  {BOT_NAME} Bot — Help",
        description=(
            f"> 🤖  **Bot:**  {BOT_NAME} v{BOT_VERSION}\n"
            f"> 🎯  **Purpose:**  جمع المعلومات والإحصائيات\n"
            f"> 🏠  **Server:**  {interaction.guild.name}\n"
            f"> 📅  **Online since:**  {discord.utils.format_dt(discord.utils.utcnow(), 'R')}\n"
            f"{separator()}"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )

    # 🆕 قسم الأوامر العامة (للجميع)
    public_commands = (
        f"> 📨  `/myapplications`  —  عرض طلباتي السابقة\n"
        f"> ❓  `/help`  —  عرض هذه القائمة\n"
        f"> 🤖  `/botinfo`  —  معلومات البوت"
    )
    main_embed.add_field(name="👤  Public Commands", value=public_commands, inline=False)

    # 🆕 قسم أوامر الأدمن (لو المستخدم أدمن)
    if is_admin:
        admin_commands = (
            f"> 📋  `/setup-applications #channel`  —  إنشاء لائحة الطلبات\n"
            f"> 🔔  `/set-admin-channel #channel`  —  تحديد شات الأدمن\n"
            f"> 📋  `/recent-applications [limit]`  —  عرض آخر الطلبات\n"
            f"> 📊  `/application-stats`  —  إحصائيات الطلبات"
        )
        main_embed.add_field(name="👮  Admin Commands", value=admin_commands, inline=False)

    # 🆕 قسم كيفية التقديم
    main_embed.add_field(
        name="📋  How to Apply",
        value=(
            f"> 1️⃣  اذهب لقناة الطلبات\n"
            f"> 2️⃣  اضغط على أحد الأزرار:\n"
            f">      🛡️  **Staff**  •  🔍  **Checker**  •  📱  **Influencer**  •  🎮  **Pro Player**\n"
            f"> 3️⃣  املأ النموذج وأرسله\n"
            f"> 4️⃣  انتظر قرار الأدمن"
        ),
        inline=False
    )

    # 🆕 قسم أنواع الطلبات
    main_embed.add_field(
        name="📝  Application Types",
        value=(
            f"> 🛡️  **Staff**  —  فريق الإدارة  (4 أسئلة)\n"
            f"> 🔍  **Checker**  —  مدقق  (5 أسئلة)\n"
            f"> 📱  **Influencer**  —  صانع محتوى  (5 أسئلة)\n"
            f"> 🎮  **Professional Player**  —  لاعب محترف  (5 أسئلة)"
        ),
        inline=False
    )

    # 🆕 قسم الروابط السريعة
    main_embed.add_field(
        name="🔗  Quick Links",
        value=(
            f"> 📋  لإنشاء لائحة الطلبات:  `/setup-applications`\n"
            f"> 🔔  لتحديد شات الأدمن:  `/set-admin-channel`\n"
            f"> 📨  لعرض طلباتك:  `/myapplications`"
        ),
        inline=False
    )

    # 🆕 قسم معلومات إضافية
    main_embed.add_field(
        name="ℹ️  Additional Info",
        value=(
            f"> 📊  إجمالي الأوامر:  `7`\n"
            f"> 🆕  النسخة:  `v{BOT_VERSION}`\n"
            f"> 👑  المالك:  {BOT_OWNER_NAME}\n"
            f"> 🏠  السيرفرات:  `{len(bot.guilds)}`"
        ),
        inline=False
    )

    main_embed.set_footer(text=f"{BOT_FOOTER}  •  Help  •  v{BOT_VERSION}")
    if bot.user.display_avatar:
        main_embed.set_thumbnail(url=bot.user.display_avatar.url)
    if interaction.guild.icon:
        main_embed.set_author(name=f"{interaction.guild.name}", icon_url=interaction.guild.icon.url)

    await interaction.response.send_message(embed=main_embed, ephemeral=True)


@bot.tree.command(name="botinfo", description="🤖 معلومات البوت")
async def botinfo_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"🤖  {BOT_NAME} Bot",
        description=(
            f"> 📛  **Name:**  {BOT_NAME}\n"
            f"> 🔢  **Version:**  v{BOT_VERSION}\n"
            f"> 🎯  **Purpose:**  جمع المعلومات والإحصائيات\n"
            f"> 👑  **Owner:**  {BOT_OWNER_NAME}\n"
            f"> 🏠  **Servers:**  `{len(bot.guilds)}`\n"
            f"> 📅  **Online since:**  {discord.utils.format_dt(bot.user.created_at, 'R')}\n"
            f"{separator()}\n"
            f"> 💡  استخدم `/help` لعرض كل الأوامر"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )
    embed.set_footer(text=f"{BOT_FOOTER}  •  Info")
    if bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_guild_join(guild):
    logger.info(f"🏠 Added to: {guild.name}  (ID: {guild.id})  —  Members: {guild.member_count}")


@bot.event
async def on_guild_remove(guild):
    logger.info(f"👋 Removed from: {guild.name}  (ID: {guild.id})")


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    # 🆕 V1.6: التوكن من متغير البيئة فقط — لا تكتبه في الكود!
    # 🔴 Discord يكتشف التوكن المسروق ويُلغيه تلقائياً
    TOKEN = os.getenv("MEGAN_TOKEN")
    if not TOKEN:
        raise RuntimeError(
            "❌ MEGAN_TOKEN غير مضبوط في متغيرات البيئة!\n"
            "\n"
            "📋 طريقة الضبط:\n"
            "\n"
            "🪟 على Windows (Command Prompt):\n"
            "   set MEGAN_TOKEN=your_token_here\n"
            "   python megan-bot.py\n"
            "\n"
            "🐧 على Linux/Mac:\n"
            "   export MEGAN_TOKEN=\"your_token_here\"\n"
            "   python megan-bot.py\n"
            "\n"
            "📄 أو ضعه في ملف .env:\n"
            "   MEGAN_TOKEN=your_token_here\n"
            "\n"
            "⚠️  لا تكتب التوكن في الكود مباشرة!"
        )
    logger.info(f"🚀 Starting {BOT_NAME} Bot v{BOT_VERSION}...")
    bot.run(TOKEN)
