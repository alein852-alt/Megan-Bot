"""
===========================================================
  📊 Megan Bot — v1.0
===========================================================
  🎯 متخصص في جمع المعلومات والإحصائيات
  📝 نظام طلبات الانضمام (Staff Applications)
  🎨 تصميم مطابق للهوية البصرية المطلوبة
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

# 🆕 تحميل ملف .env تلقائياً (محلياً فقط — Railway يستخدم Variables مباشرة)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv غير مثبت — لا مشكلة (Railway لا يحتاجه)

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
BOT_VERSION = "1.0"
BOT_FOOTER = "Megan Bot"
BOT_OWNER_ID = 1077949215772250143
BOT_OWNER_NAME = "aizenx000"

# 🆕 ألوان الهوية البصرية (مطابقة للصور)
COLORS = {
    "primary":     0xE67E22,   # برتقالي (للعناوين الرئيسية)
    "warning":     0xE67E22,   # برتقالي (للتحذيرات)
    "success":     0x2ECC71,   # أخضر
    "error":       0xE74C3C,   # أحمر
    "info":        0x3498DB,   # أزرق
    "dark":        0x2B2D31,   # داكن (مطابق لـ Discord dark theme)
    "staff":       0x95A5A6,   # رمادي (لزر Staff)
    "checker":     0x3498DB,   # أزرق (لزر Checker)
    "influencer":  0x2ECC71,   # أخضر (لزر Influencer)
    "pro_player":  0xF1C40F,   # ذهبي (لزر Pro Player)
}

# 🆕 صورة التاطير (banner)
# الصورة محفوظة محلياً في megan-assets/banner.png وستُرفع تلقائياً كـ attachment
# عند إنشاء اللائحة الأولى — ويُحفظ الرابط في DB
BANNER_IMAGE_LOCAL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "megan-assets", "banner.png")
BANNER_IMAGE_URL = os.getenv("MEGAN_BANNER_URL", "")  # لو متوفر كرابط مباشر


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
            # 🆕 Migration: أضف عمود banner_url لو غير موجود
            try:
                c.execute("ALTER TABLE guild_settings ADD COLUMN banner_url TEXT DEFAULT NULL")
            except sqlite3.OperationalError:
                pass  # العمود موجود بالفعل
            c.commit()
        finally:
            c.close()

    # ============================================================
    # Guild Settings
    # ============================================================
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
        """🆕 يحفظ رابط الـ banner في DB."""
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
        """🆕 يرجع رابط الـ banner المحفوظ، أو None."""
        c = self._conn()
        try:
            row = c.execute("SELECT banner_url FROM guild_settings WHERE guild_id=?", (guild_id,)).fetchone()
            return row["banner_url"] if row else None
        finally:
            c.close()

    # ============================================================
    # Applications
    # ============================================================
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
    """فاصل بصري احترافي."""
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def get_application_emoji(app_type):
    """إيموجي حسب نوع الطلب."""
    return {
        "staff":       "🛡️",
        "checker":     "🔍",
        "influencer":  "📱",
        "pro_player":  "🎮",
    }.get(app_type, "📝")


def get_application_label(app_type):
    """عنوان حسب نوع الطلب."""
    return {
        "staff":       "Staff",
        "checker":     "Checker",
        "influencer":  "Influencer",
        "pro_player":  "Professional Player",
    }.get(app_type, "Unknown")


def get_application_color(app_type):
    """لون حسب نوع الطلب."""
    return {
        "staff":       COLORS["staff"],
        "checker":     COLORS["checker"],
        "influencer":  COLORS["influencer"],
        "pro_player":  COLORS["pro_player"],
    }.get(app_type, COLORS["primary"])


# ============================================================
# APPLICATION QUESTIONS (مطابقة للصور)
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

    # 🆕 سجّل الـ persistent views
    bot.add_view(ApplicationsView())

    # 🆕 sync slash commands
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
# APPLICATIONS VIEW (اللائحة الرئيسية مع 4 أزرار)
# ============================================================
class ApplicationsView(discord.ui.View):
    """اللائحة الرئيسية مع 4 أزرار."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Staff",
        style=discord.ButtonStyle.secondary,
        custom_id="megan_app_staff",
        emoji="🛡️"
    )
    async def staff_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("staff"))

    @discord.ui.button(
        label="Checker",
        style=discord.ButtonStyle.primary,
        custom_id="megan_app_checker",
        emoji="🔍"
    )
    async def checker_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("checker"))

    @discord.ui.button(
        label="influencer",
        style=discord.ButtonStyle.success,
        custom_id="megan_app_influencer",
        emoji="📱"
    )
    async def influencer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("influencer"))

    @discord.ui.button(
        label="professional player",
        style=discord.ButtonStyle.success,
        custom_id="megan_app_pro_player",
        emoji="🎮"
    )
    async def pro_player_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ApplicationModal("pro_player"))


# ============================================================
# APPLICATION MODAL (النموذج اللي يفتح عند الضغط على الزر)
# ============================================================
class ApplicationModal(discord.ui.Modal):
    """نموذج طلب الانضمام — ديناميكي حسب نوع الطلب."""

    def __init__(self, app_type: str):
        self.app_type = app_type
        config = APPLICATION_QUESTIONS[app_type]

        super().__init__(title=config["title"], timeout=600)

        # أضف حقول الإدخال ديناميكياً
        for i, q in enumerate(config["questions"]):
            text_input = discord.ui.TextInput(
                label=q["label"],
                placeholder=q.get("placeholder", ""),
                required=q.get("required", True),
                style=q.get("style", discord.TextStyle.short),
                max_length=1024 if q.get("style") == discord.TextStyle.paragraph else 200,
            )
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        # اجمع الإجابات
        answers = []
        for i, child in enumerate(self.children):
            if isinstance(child, discord.ui.TextInput):
                answers.append({
                    "label": child.label,
                    "value": child.value,
                })

        # احفظ في DB
        import json
        app_id = db.save_application(
            interaction.guild.id,
            interaction.user.id,
            self.app_type,
            json.dumps(answers, ensure_ascii=False)
        )

        # رسالة تأكيد للمستخدم
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

        await interaction.response.send_message(embed=success_embed, ephemeral=True)

        # 🆕 أرسل الطلب لشات الأدمن
        await self.send_to_admin_channel(interaction, app_id, answers)

    async def send_to_admin_channel(self, interaction: discord.Interaction, app_id: int, answers: list):
        """أرسل تفاصيل الطلب لشات الأدمن."""
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

            # بناء الـ embed اللي يراه الأدمن
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

            # أضف الإجابات كـ fields
            for ans in answers:
                embed.add_field(
                    name=f"📝  {ans['label']}",
                    value=f"```\n{ans['value']}\n```",
                    inline=False
                )

            embed.set_footer(text=f"{BOT_FOOTER}  •  Application #{app_id}  •  {app_label}")
            if interaction.user.display_avatar:
                embed.set_thumbnail(url=interaction.user.display_avatar.url)

            # أرسل مع أزرار التحكم (Accept / Reject)
            view = AdminApplicationView(app_id, interaction.user.id)
            await admin_channel.send(
                content=f"🔔  **New Application**  —  {interaction.user.mention}",
                embed=embed,
                view=view
            )
            logger.info(f"📤 Application #{app_id} sent to admin channel #{admin_channel.name}")

        except Exception as e:
            logger.exception(f"Failed to send application to admin channel: {e}")


# ============================================================
# ADMIN APPLICATION VIEW (أزرار Accept/Reject لكل طلب)
# ============================================================
class AdminApplicationView(discord.ui.View):
    """أزرار التحكم في الطلب — للأدمن فقط."""

    def __init__(self, app_id: int, applicant_id: int):
        super().__init__(timeout=None)
        self.app_id = app_id
        self.applicant_id = applicant_id

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.success,
        custom_id="megan_app_accept",
        emoji="✅"
    )
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # تحقق من الصلاحيات
        if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
            return

        db.update_application_status(self.app_id, "approved")
        # عدّل الرسالة
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

        # حاول إرسال رسالة للمستخدم
        try:
            applicant = await interaction.guild.fetch_member(self.applicant_id)
            if applicant:
                dm_embed = discord.Embed(
                    title="🎉  Application Accepted!",
                    description=(
                        f"> 🏆  مبروك! تم قبول طلبك في **{interaction.guild.name}**\n"
                        f"> 🆔  **Application ID:**  `#{self.app_id}`\n"
                        f"> 👮  **Accepted by:**  {interaction.user.mention}\n"
                        f"{separator()}\n"
                        f"> 📬  سيتم التواصل معك قريباً للمتابعة."
                    ),
                    color=COLORS["success"],
                    timestamp=discord.utils.utcnow()
                )
                dm_embed.set_footer(text=f"{BOT_FOOTER}  •  {interaction.guild.name}")
                await applicant.send(embed=dm_embed)
        except Exception as e:
            logger.warning(f"Could not DM applicant {self.applicant_id}: {e}")

    @discord.ui.button(
        label="Reject",
        style=discord.ButtonStyle.danger,
        custom_id="megan_app_reject",
        emoji="❌"
    )
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # تحقق من الصلاحيات
        if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
            await interaction.response.send_message("❌  انت لا تملك صلاحية القيام بهذا.", ephemeral=True)
            return

        db.update_application_status(self.app_id, "rejected")
        # عدّل الرسالة
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

        # حاول إرسال رسالة للمستخدم
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
    """📋 إنشاء لائحة طلبات الانضمام في شات محدد."""
    # تحقق من الصلاحيات
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message(
            "❌  انت لا تملك صلاحية القيام بهذا.",
            ephemeral=True
        )
        return

    # أرسل رسالة "جارٍ الإعداد"
    await interaction.response.send_message(
        embed=discord.Embed(
            title="⏳  جارٍ الإعداد...",
            description="> 📋  جاري إنشاء لائحة الطلبات ورفع صورة الـ banner...",
            color=COLORS["primary"]
        ),
        ephemeral=True
    )

    # احفظ الشات في DB
    db.set_applications_channel(interaction.guild.id, channel.id)

    # 🆕 حدّد رابط الـ banner (لو موجود محفوظ في DB، أو متغير بيئة، أو ارفع محلي)
    banner_url = db.get_banner_url(interaction.guild.id)
    if not banner_url and BANNER_IMAGE_URL:
        banner_url = BANNER_IMAGE_URL

    # 🆕 لو ما فيه رابط، ارفع الصورة المحلية كـ attachment واحفظ رابطها
    if not banner_url and os.path.exists(BANNER_IMAGE_LOCAL_PATH):
        try:
            with open(BANNER_IMAGE_LOCAL_PATH, "rb") as f:
                banner_file = discord.File(f, filename="megan_banner.png")
                # ارفع في الشات اللي راح تنشأ فيه اللائحة
                upload_msg = await channel.send(file=banner_file)
                if upload_msg.attachments:
                    banner_url = upload_msg.attachments[0].url
                    db.set_banner_url(interaction.guild.id, banner_url)
                    # احذف رسالة الرفع (الصورة تبقى على CDN)
                    try:
                        await upload_msg.delete()
                    except:
                        pass
                    logger.info(f"🖼️  Banner uploaded and saved: {banner_url}")
        except Exception as e:
            logger.warning(f"Failed to upload banner: {e}")

    # أنشئ الـ embed الرئيسي (مطابق للصورة 1)
    embed = discord.Embed(
        title="📋  Staff Applications",
        description=(
            f"> Read everything carefully before applying\n"
            f"{separator()}\n"
            f"\n"
            f"🟠  **Staff Requirements**\n"
            f"> ─  Must be active and mature\n"
            f"> ─  Good behavior and respect to everyone\n"
            f"> ─  No abuse of power\n"
            f"> ─  Must know and enforce server rules\n"
            f"> ─  No staff drama or favoritism\n"
            f"> ─  Must listen to higher staff decisions\n"
            f"> ─  Previous staff experience is a plus but not required\n"
            f"\n"
            f"🟠  **How to Apply**\n"
            f"> ─  Press the button below and answer the questions\n"
            f"\n"
            f"{separator()}\n"
            f"> ⚠️  any big abuse or lying in applications can cause a ban  💖"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )
    embed.set_author(name=f"{interaction.guild.name}  •  Applications", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    embed.set_footer(text=f"{BOT_FOOTER}  •  Staff Applications")

    # أضف صورة الـ banner (لو موجودة)
    if banner_url:
        embed.set_image(url=banner_url)
    elif interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    # أرسل اللائحة في الشات المحدد
    view = ApplicationsView()
    msg = await channel.send(embed=embed, view=view)

    # احفظ ID الرسالة
    db.set_applications_message(interaction.guild.id, msg.id)

    # عدّل رسالة التأكيد
    confirm_embed = discord.Embed(
        title="✅  Setup Complete",
        description=(
            f"> 📋  **Applications channel:**  {channel.mention}\n"
            f"> 🆔  **Message ID:**  `{msg.id}`\n"
            f"> 🖼️  **Banner:**  {'✅ مرفوع' if banner_url else '❌ غير متوفر'}\n"
            f"> 📅  **Created at:**  {discord.utils.format_dt(discord.utils.utcnow(), 'F')}\n"
            f"{separator()}\n"
            f"> 💡  اللاعبون يمكنهم الآن الضغط على الأزرار للتقديم.\n"
            f"> ⚠️  لا تنسى تحديد شات الأدمن بـ `/set-admin-channel`"
        ),
        color=COLORS["success"],
        timestamp=discord.utils.utcnow()
    )
    confirm_embed.set_footer(text=f"{BOT_FOOTER}  •  Setup")

    await interaction.edit_original_response(embed=confirm_embed)
    logger.info(f"📋 Applications setup in {interaction.guild.name} #{channel.name}")


@bot.tree.command(name="set-admin-channel", description="🔔 تحديد شات الأدمن اللي ترسل له الطلبات (Admin only)")
@app_commands.describe(channel="الشات اللي تحب تستقبل فيه الطلبات")
@app_commands.default_permissions(manage_guild=True)
async def set_admin_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """🔔 تحديد شات الأدمن."""
    # تحقق من الصلاحيات
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message(
            "❌  انت لا تملك صلاحية القيام بهذا.",
            ephemeral=True
        )
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
    """📨 عرض طلبات المستخدم."""
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
    """📊 إحصائيات الطلبات."""
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message(
            "❌  انت لا تملك صلاحية القيام بهذا.",
            ephemeral=True
        )
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
    """📋 عرض آخر الطلبات."""
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id != BOT_OWNER_ID:
        await interaction.response.send_message(
            "❌  انت لا تملك صلاحية القيام بهذا.",
            ephemeral=True
        )
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


@bot.tree.command(name="help", description="❓ قائمة أوامر Megan Bot")
async def help_cmd(interaction: discord.Interaction):
    """❓ Help command."""
    is_admin = interaction.user.guild_permissions.manage_guild or interaction.user.id == BOT_OWNER_ID

    embed = discord.Embed(
        title="📊  Megan Bot — Help",
        description=(
            f"> 🤖  **Bot:**  {BOT_NAME} v{BOT_VERSION}\n"
            f"> 🎯  **Purpose:**  جمع المعلومات والإحصائيات\n"
            f"> 📅  **Built:**  {discord.utils.format_dt(discord.utils.utcnow(), 'd')}\n"
            f"{separator()}"
        ),
        color=COLORS["primary"],
        timestamp=discord.utils.utcnow()
    )

    # أوامر عامة
    embed.add_field(
        name="👤  Public Commands",
        value=(
            f"> `/myapplications`  —  عرض طلباتي السابقة\n"
            f"> `/help`  —  قائمة الأوامر"
        ),
        inline=False
    )

    if is_admin:
        embed.add_field(
            name="👮  Admin Commands",
            value=(
                f"> `/setup-applications #channel`  —  إنشاء لائحة الطلبات\n"
                f"> `/set-admin-channel #channel`  —  تحديد شات الأدمن\n"
                f"> `/recent-applications [limit]`  —  عرض آخر الطلبات\n"
                f"> `/application-stats`  —  إحصائيات الطلبات"
            ),
            inline=False
        )

    embed.add_field(
        name="📋  How to Apply",
        value=(
            f"> 1️⃣  اذهب لقناة الطلبات\n"
            f"> 2️⃣  اضغط على أحد الأزرار:\n"
            f">      🛡️  Staff  •  🔍  Checker  •  📱  Influencer  •  🎮  Pro Player\n"
            f"> 3️⃣  املأ النموذج وأرسله\n"
            f"> 4️⃣  انتظر قرار الأدمن"
        ),
        inline=False
    )

    embed.set_footer(text=f"{BOT_FOOTER}  •  Help")
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="botinfo", description="🤖 معلومات البوت")
async def botinfo_cmd(interaction: discord.Interaction):
    """🤖 Bot info."""
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
            f"> 💡  استخدم `/help` لعرض الأوامر"
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
    # 🔴 التوكن يجب أن يأتي من متغير البيئة MEGAN_TOKEN فقط
    # ⚠️ لا تضع التوكن في الكود أبداً عند الرفع لـ GitHub
    # محلياً: ضعه في ملف .env أو export MEGAN_TOKEN="your_token"
    # Railway: أضفه في Variables tab
    TOKEN = os.getenv("MEGAN_TOKEN")
    if not TOKEN:
        raise RuntimeError(
            "❌ MEGAN_TOKEN غير مضبوط!\n"
            "   اضبط متغير البيئة MEGAN_TOKEN:\n"
            "   • محلياً: ضعه في ملف .env أو: export MEGAN_TOKEN=\"your_token\"\n"
            "   • Railway: أضف Variable باسم MEGAN_TOKEN في تبويب Variables\n"
            "   • GitHub Actions: أضفه كـ Secret"
        )
    logger.info(f"🚀 Starting {BOT_NAME} Bot v{BOT_VERSION}...")
    bot.run(TOKEN)
