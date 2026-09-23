import json
import os
import re
import asyncio
import discord
import firebase_admin

from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from firebase_admin import credentials, firestore


# =========================================================
# ENV
# =========================================================

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")


# =========================================================
# FIREBASE
# =========================================================

firebase_json = os.getenv("FIREBASE_CREDENTIALS")

if firebase_json:
    firebase_dict = json.loads(firebase_json)
    cred = credentials.Certificate(firebase_dict)
else:
    cred = credentials.Certificate("firebase-key.json")

firebase_admin.initialize_app(cred)

db = firestore.client()

# =========================================================
# DISCORD CONFIG
# =========================================================

GUILD_ID = 1549186217449492481
GUILD = discord.Object(id=GUILD_ID)

CONTRACTS_CHANNEL_ID = 1549213306655481866
WELCOME_CHANNEL_ID = 1549217102114857062
LOG_CHANNEL_ID = 1549213596007800912

TICKETS_CATEGORY_ID = 1550954905144135691
TICKETS_PANEL_CHANNEL_ID = 1550955036492963861


# =========================================================
# ARTISTAS
# =========================================================

ARTIST_DISCORD_IDS = {
    "zanx": 1434278973403299980,
    "dro": 693897321879961651,
    "dragho": 634540784309239833,
    "fayre": 722873638906363915
}


# =========================================================
# BOT
# =========================================================

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================================================
# VARIABLES
# =========================================================

contract_cache = {}

monitor_started = False
views_registered = False


# =========================================================
# LOGS ADMIN
# =========================================================

async def send_admin_log(
    interaction: discord.Interaction,
    accion: str,
    detalles: str
):

    channel = bot.get_channel(LOG_CHANNEL_ID)

    if channel is None:
        print("ERROR: No se encontró el canal de logs.")
        return

    embed = discord.Embed(
        title="🛠 ADMIN LOG",
        description=(
            f"**Usuario:** {interaction.user.mention}\n"
            f"**Acción:** `{accion}`\n\n"
            f"{detalles}"
        )
    )

    embed.set_footer(
        text="LOWCUT// RECORDS"
    )

    await channel.send(
        embed=embed,
        allowed_mentions=discord.AllowedMentions.none()
    )


# =========================================================
# CONTRACT MONITOR
# =========================================================

async def monitor_contracts():

    await bot.wait_until_ready()

    channel = bot.get_channel(
        CONTRACTS_CHANNEL_ID
    )

    if channel is None:

        print(
            "ERROR: No se encontró "
            "el canal #contratos."
        )

        return

    print("Monitor de contratos iniciado.")

    while not bot.is_closed():

        try:

            docs = db.collection(
                "contracts"
            ).stream()

            for doc in docs:

                data = doc.to_dict()

                contract_id = doc.id

                status = str(
                    data.get(
                        "status",
                        ""
                    )
                ).lower().strip()

                title = data.get(
                    "title",
                    "Contrato"
                )

                artist_ids = data.get(
                    "artistIds",
                    []
                )

                contract_url = data.get(
                    "contractUrl",
                    ""
                )

                discord_message_id = data.get(
                    "discordMessageId"
                )

                if not artist_ids:
                    continue

                artist = str(
                    artist_ids[0]
                ).lower().strip()

                if artist not in ARTIST_DISCORD_IDS:
                    continue

                discord_user_id = (
                    ARTIST_DISCORD_IDS[
                        artist
                    ]
                )

                old_status = (
                    contract_cache.get(
                        contract_id
                    )
                )

                # =========================================
                # PRIMERA VEZ
                # =========================================

                if old_status is None:

                    contract_cache[
                        contract_id
                    ] = status

                    # Ya tiene mensaje en Discord
                    if discord_message_id:
                        continue

                    # Contrato pendiente nuevo
                    if status == "pending":

                        embed = discord.Embed(
                            title=(
                                "📄 CONTRATO "
                                "PENDIENTE"
                            ),
                            description=(
                                f"**{title}**\n\n"
                                f"**Artista:** "
                                f"{artist.upper()}\n"
                                "⏳ **Estado:** "
                                "Pendiente de firma\n\n"
                                "Tenés un contrato "
                                "pendiente de firma en "
                                "LOWCUT// Records."
                            )
                        )

                        if contract_url:

                            embed.add_field(
                                name="Contrato",
                                value=(
                                    f"[Abrir contrato]"
                                    f"({contract_url})"
                                ),
                                inline=False
                            )

                        embed.set_footer(
                            text="LOWCUT// RECORDS"
                        )

                        message = (
                            await channel.send(
                                content=(
                                    f"<@"
                                    f"{discord_user_id}"
                                    f">"
                                ),
                                embed=embed,
                                allowed_mentions=
                                discord.AllowedMentions(
                                    users=True
                                )
                            )
                        )

                        doc.reference.update({
                            "discordMessageId":
                                str(message.id)
                        })

                        print(
                            "Contrato pendiente "
                            f"publicado: {contract_id}"
                        )

                    continue

                # =========================================
                # SIN CAMBIOS
                # =========================================

                if old_status == status:
                    continue

                print(
                    f"Contrato {contract_id}: "
                    f"{old_status} -> {status}"
                )

                contract_cache[
                    contract_id
                ] = status

                # =========================================
                # FIRMADO
                # =========================================

                if status == "signed":

                    embed = discord.Embed(
                        title="✅ CONTRATO FIRMADO",
                        description=(
                            f"**{title}**\n\n"
                            f"**Artista:** "
                            f"{artist.upper()}\n"
                            "✅ **Estado:** Firmado\n\n"
                            "El contrato fue marcado "
                            "como firmado en el portal."
                        )
                    )

                    if contract_url:

                        embed.add_field(
                            name="Contrato",
                            value=(
                                f"[Abrir contrato]"
                                f"({contract_url})"
                            ),
                            inline=False
                        )

                    embed.set_footer(
                        text="LOWCUT// RECORDS"
                    )

                    if discord_message_id:

                        try:

                            message = (
                                await channel.fetch_message(
                                    int(
                                        discord_message_id
                                    )
                                )
                            )

                            await message.edit(
                                content=(
                                    f"<@"
                                    f"{discord_user_id}"
                                    f">"
                                ),
                                embed=embed,
                                allowed_mentions=
                                discord.AllowedMentions(
                                    users=True
                                )
                            )

                            print(
                                "Mensaje actualizado "
                                "a firmado."
                            )

                        except discord.NotFound:

                            message = (
                                await channel.send(
                                    content=(
                                        f"<@"
                                        f"{discord_user_id}"
                                        f">"
                                    ),
                                    embed=embed,
                                    allowed_mentions=
                                    discord.AllowedMentions(
                                        users=True
                                    )
                                )
                            )

                            doc.reference.update({
                                "discordMessageId":
                                    str(message.id)
                            })

                    else:

                        message = (
                            await channel.send(
                                content=(
                                    f"<@"
                                    f"{discord_user_id}"
                                    f">"
                                ),
                                embed=embed,
                                allowed_mentions=
                                discord.AllowedMentions(
                                    users=True
                                )
                            )
                        )

                        doc.reference.update({
                            "discordMessageId":
                                str(message.id)
                        })

                # =========================================
                # VUELVE A PENDING
                # =========================================

                elif status == "pending":

                    embed = discord.Embed(
                        title="📄 CONTRATO PENDIENTE",
                        description=(
                            f"**{title}**\n\n"
                            f"**Artista:** "
                            f"{artist.upper()}\n"
                            "⏳ **Estado:** "
                            "Pendiente de firma\n\n"
                            "El contrato está "
                            "pendiente de firma."
                        )
                    )

                    if contract_url:

                        embed.add_field(
                            name="Contrato",
                            value=(
                                f"[Abrir contrato]"
                                f"({contract_url})"
                            ),
                            inline=False
                        )

                    embed.set_footer(
                        text="LOWCUT// RECORDS"
                    )

                    if discord_message_id:

                        try:

                            message = (
                                await channel.fetch_message(
                                    int(
                                        discord_message_id
                                    )
                                )
                            )

                            await message.edit(
                                content=(
                                    f"<@"
                                    f"{discord_user_id}"
                                    f">"
                                ),
                                embed=embed,
                                allowed_mentions=
                                discord.AllowedMentions(
                                    users=True
                                )
                            )

                        except discord.NotFound:

                            message = (
                                await channel.send(
                                    content=(
                                        f"<@"
                                        f"{discord_user_id}"
                                        f">"
                                    ),
                                    embed=embed
                                )
                            )

                            doc.reference.update({
                                "discordMessageId":
                                    str(message.id)
                            })

                    else:

                        message = (
                            await channel.send(
                                content=(
                                    f"<@"
                                    f"{discord_user_id}"
                                    f">"
                                ),
                                embed=embed,
                                allowed_mentions=
                                discord.AllowedMentions(
                                    users=True
                                )
                            )
                        )

                        doc.reference.update({
                            "discordMessageId":
                                str(message.id)
                        })

        except Exception as e:

            print(
                f"ERROR revisando contratos: {e}"
            )

        await asyncio.sleep(10)


# =========================================================
# TICKETS - UTILIDADES
# =========================================================

def clean_channel_name(name: str):

    name = name.lower()

    name = re.sub(
        r"[^a-z0-9-]",
        "-",
        name
    )

    name = re.sub(
        r"-+",
        "-",
        name
    )

    name = name.strip("-")

    if not name:
        name = "usuario"

    return name[:70]


async def find_existing_ticket(
    guild: discord.Guild,
    user: discord.Member
):

    category = guild.get_channel(
        TICKETS_CATEGORY_ID
    )

    if category is None:
        return None

    for channel in category.channels:

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            continue

        if (
            channel.topic
            == f"ticket_owner:{user.id}"
        ):
            return channel

    return None


# =========================================================
# TICKETS - BOTON CERRAR
# =========================================================

class CloseTicketView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Cerrar ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="lowcut_close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):

            await interaction.response.send_message(
                "Este botón solo funciona "
                "dentro de un ticket.",
                ephemeral=True
            )

            return

        if not channel.topic:

            await interaction.response.send_message(
                "Este canal no parece "
                "ser un ticket.",
                ephemeral=True
            )

            return

        if not channel.topic.startswith(
            "ticket_owner:"
        ):

            await interaction.response.send_message(
                "Este canal no parece "
                "ser un ticket.",
                ephemeral=True
            )

            return

        owner_id = channel.topic.replace(
            "ticket_owner:",
            ""
        )

        is_owner = (
            str(interaction.user.id)
            == owner_id
        )

        is_admin = (
            interaction.user.guild_permissions
            .administrator
        )

        if not is_owner and not is_admin:

            await interaction.response.send_message(
                "Solo el creador del ticket "
                "o un administrador puede cerrarlo.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 Cerrando ticket..."
        )

        log_channel = bot.get_channel(
            LOG_CHANNEL_ID
        )

        if log_channel:

            embed = discord.Embed(
                title="🎫 TICKET CERRADO",
                description=(
                    f"**Canal:** "
                    f"`{channel.name}`\n"
                    f"**Cerrado por:** "
                    f"{interaction.user.mention}"
                )
            )

            embed.set_footer(
                text="LOWCUT// RECORDS"
            )

            await log_channel.send(
                embed=embed,
                allowed_mentions=
                discord.AllowedMentions.none()
            )

        await asyncio.sleep(3)

        try:

            await channel.delete(
                reason=(
                    "Ticket cerrado por "
                    f"{interaction.user}"
                )
            )

        except discord.Forbidden:

            print(
                "ERROR: El bot no tiene "
                "permiso para borrar el ticket."
            )


# =========================================================
# TICKETS - PANEL
# =========================================================

class TicketPanelView(
    discord.ui.View
):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    @discord.ui.button(
        label="Abrir ticket",
        style=discord.ButtonStyle.primary,
        emoji="🎫",
        custom_id="lowcut_open_ticket"
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        guild = interaction.guild

        if guild is None:

            await interaction.response.send_message(
                "No pude acceder "
                "al servidor.",
                ephemeral=True
            )

            return

        category = guild.get_channel(
            TICKETS_CATEGORY_ID
        )

        if category is None:

            await interaction.response.send_message(
                "No encontré la "
                "categoría de tickets.",
                ephemeral=True
            )

            return

        existing = (
            await find_existing_ticket(
                guild,
                interaction.user
            )
        )

        if existing:

            await interaction.response.send_message(
                f"Ya tenés un ticket "
                f"abierto: {existing.mention}",
                ephemeral=True
            )

            return

        await interaction.response.defer(
            ephemeral=True
        )

        channel_name = (
            "ticket-"
            + clean_channel_name(
                interaction.user.name
            )
        )

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                    manage_messages=True
                )
        }

        try:

            ticket_channel = (
                await guild.create_text_channel(
                    name=channel_name,
                    category=category,
                    overwrites=overwrites,
                    topic=(
                        f"ticket_owner:"
                        f"{interaction.user.id}"
                    ),
                    reason=(
                        "Ticket creado por "
                        f"{interaction.user}"
                    )
                )
            )

            embed = discord.Embed(
                title="🎫 LOWCUT// SUPPORT",
                description=(
                    f"{interaction.user.mention}\n\n"
                    "Tu ticket fue creado "
                    "correctamente.\n\n"
                    "Contanos qué necesitás y "
                    "el staff de LOWCUT// "
                    "te responderá cuando pueda.\n\n"
                    "Cuando esté resuelto, "
                    "podés cerrar el ticket "
                    "con el botón de abajo."
                )
            )

            embed.set_footer(
                text="LOWCUT// RECORDS"
            )

            await ticket_channel.send(
                content=(
                    interaction.user.mention
                ),
                embed=embed,
                view=CloseTicketView(),
                allowed_mentions=
                discord.AllowedMentions(
                    users=True
                )
            )

            await interaction.followup.send(
                f"✅ Ticket creado: "
                f"{ticket_channel.mention}",
                ephemeral=True
            )

            log_channel = bot.get_channel(
                LOG_CHANNEL_ID
            )

            if log_channel:

                log_embed = discord.Embed(
                    title="🎫 TICKET ABIERTO",
                    description=(
                        f"**Usuario:** "
                        f"{interaction.user.mention}\n"
                        f"**Canal:** "
                        f"{ticket_channel.mention}"
                    )
                )

                log_embed.set_footer(
                    text="LOWCUT// RECORDS"
                )

                await log_channel.send(
                    embed=log_embed,
                    allowed_mentions=
                    discord.AllowedMentions.none()
                )

        except discord.Forbidden:

            await interaction.followup.send(
                "El bot no tiene permisos "
                "para crear tickets.",
                ephemeral=True
            )

        except Exception as e:

            print(
                f"Error creando ticket: {e}"
            )

            await interaction.followup.send(
                "Ocurrió un error "
                "al crear el ticket.",
                ephemeral=True
            )


# =========================================================
# BOT READY
# =========================================================

@bot.event
async def on_ready():

    global monitor_started
    global views_registered

    # =========================================
    # SOLO SERVER LOWCUT//
    # =========================================

    for guild in bot.guilds:

        if guild.id != GUILD_ID:

            print(
                "Servidor no autorizado "
                f"detectado: {guild.name} "
                f"({guild.id})"
            )

            await guild.leave()

    # =========================================
    # COMANDOS
    # =========================================

    bot.tree.clear_commands(
        guild=None
    )

    await bot.tree.sync()

    synced = await bot.tree.sync(
        guild=GUILD
    )

    print(
        "LOWCUT// BOT conectado como "
        f"{bot.user}"
    )

    print(
        "Comandos del servidor "
        "sincronizados: "
        f"{len(synced)}"
    )

    # =========================================
    # ESTADO
    # =========================================

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="LOWCUT// Records"
        )
    )

    # =========================================
    # BOTONES PERSISTENTES
    # =========================================

    if not views_registered:

        bot.add_view(
            TicketPanelView()
        )

        bot.add_view(
            CloseTicketView()
        )

        views_registered = True

    # =========================================
    # MONITOR FIREBASE
    # =========================================

    if not monitor_started:

        bot.loop.create_task(
            monitor_contracts()
        )

        monitor_started = True


# =========================================================
# SEGURIDAD OTROS SERVERS
# =========================================================

@bot.event
async def on_guild_join(
    guild
):

    if guild.id != GUILD_ID:

        print(
            "Intentaron agregar el bot a: "
            f"{guild.name} ({guild.id})"
        )

        await guild.leave()


# =========================================================
# BIENVENIDA
# =========================================================

@bot.event
async def on_member_join(
    member
):

    channel = bot.get_channel(
        WELCOME_CHANNEL_ID
    )

    if channel is None:

        print(
            "ERROR: No se encontró "
            "el canal de bienvenida."
        )

        return

    embed = discord.Embed(
        title="WELCOME TO LOWCUT//",
        description=(
            f"{member.mention}\n\n"
            "Bienvenido al servidor oficial "
            "de **LOWCUT// Records**.\n\n"
            "Revisá los canales, conocé "
            "nuestros artistas y descubrí "
            "los últimos lanzamientos "
            "del sello."
        )
    )

    embed.set_footer(
        text="LOWCUT// RECORDS"
    )

    try:

        file = discord.File(
            "welcome-banner.png",
            filename="welcome-banner.png"
        )

        embed.set_image(
            url=(
                "attachment://"
                "welcome-banner.png"
            )
        )

        await channel.send(
            content=member.mention,
            embed=embed,
            file=file,
            allowed_mentions=
            discord.AllowedMentions(
                users=True
            )
        )

    except FileNotFoundError:

        print(
            "No se encontró "
            "welcome-banner.png"
        )

        await channel.send(
            content=member.mention,
            embed=embed,
            allowed_mentions=
            discord.AllowedMentions(
                users=True
            )
        )


# =========================================================
# /ARTISTS
# PUBLICO
# =========================================================

@bot.tree.command(
    name="artists",
    description=(
        "Muestra los artistas "
        "de LOWCUT// Records"
    ),
    guild=GUILD
)
async def artists(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="LOWCUT// ARTISTS",
        description=(
            "**Fayre**\n"
            "Electronic producer — "
            "Santa Fe, Argentina\n\n"

            "**Dragho**\n"
            "Electronic producer — "
            "Chaco, Argentina\n\n"

            "**Dro**\n"
            "Trap / Experimental Urban — "
            "Santa Fe, Argentina\n\n"

            "**Zanx**\n"
            "Trap / Phonk / "
            "Experimental producer"
        )
    )

    embed.set_footer(
        text="LOWCUT// RECORDS"
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /DEMO
# PUBLICO
# =========================================================

@bot.tree.command(
    name="demo",
    description=(
        "Información para enviar "
        "demos a LOWCUT// Records"
    ),
    guild=GUILD
)
async def demo(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="LOWCUT// DEMOS",
        description=(
            "¿Querés enviar música "
            "a LOWCUT// Records?\n\n"

            "📩 **lowcut.label.arg@gmail.com**\n\n"

            "Electronic • Urban • Experimental"
        )
    )

    embed.set_footer(
        text="LOWCUT// RECORDS"
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# /LINKS
# PUBLICO
# =========================================================

@bot.tree.command(
    name="links",
    description=(
        "Links oficiales "
        "de LOWCUT// Records"
    ),
    guild=GUILD
)
async def links(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="LOWCUT// RECORDS",
        description=(
            "Links oficiales del sello\n\n"

            "📸 **Instagram**\n"
            "https://www.instagram.com/"
            "lowcut.records/\n\n"

            "☁️ **SoundCloud**\n"
            "https://soundcloud.com/"
            "lowcut_records\n\n"

            "🌐 **Website**\n"
            "https://lowcutrecords.github.io/"
            "LOWCUT-Records/"
        )
    )

    embed.set_footer(
        text="LOWCUT// RECORDS"
    )

    await interaction.response.send_message(
        embed=embed
    )


# =========================================================
# AUTOCOMPLETE CONTRATOS
# =========================================================

async def contratos_pendientes_autocomplete(
    interaction: discord.Interaction,
    current: str
):

    choices = []

    try:

        docs = db.collection(
            "contracts"
        ).stream()

        for doc in docs:

            data = doc.to_dict()

            status = str(
                data.get(
                    "status",
                    ""
                )
            ).lower().strip()

            if status != "pending":
                continue

            title = data.get(
                "title",
                "Sin título"
            )

            artist_ids = data.get(
                "artistIds",
                []
            )

            artist = (
                str(
                    artist_ids[0]
                ).upper()
                if artist_ids
                else "SIN ARTISTA"
            )

            label = (
                f"{artist} — {title}"
            )

            if (
                current.lower()
                not in label.lower()
            ):
                continue

            choices.append(
                app_commands.Choice(
                    name=label[:100],
                    value=doc.id
                )
            )

            if len(choices) >= 25:
                break

    except Exception as e:

        print(
            "Error cargando contratos: "
            f"{e}"
        )

    return choices


# =========================================================
# /NOTIFICARCONTRATO
# ADMIN
# =========================================================

@bot.tree.command(
    name="notificarcontrato",
    description=(
        "Notifica manualmente "
        "un contrato pendiente"
    ),
    guild=GUILD
)
@app_commands.default_permissions(
    administrator=True
)
@app_commands.autocomplete(
    contrato=
    contratos_pendientes_autocomplete
)
async def notificarcontrato(
    interaction: discord.Interaction,
    contrato: str
):

    doc_ref = (
        db.collection("contracts")
        .document(contrato)
    )

    doc = doc_ref.get()

    if not doc.exists:

        await interaction.response.send_message(
            "No encontré ese contrato.",
            ephemeral=True
        )

        return

    data = doc.to_dict()

    status = str(
        data.get(
            "status",
            ""
        )
    ).lower().strip()

    if status != "pending":

        await interaction.response.send_message(
            "Ese contrato ya no "
            "está pendiente.",
            ephemeral=True
        )

        return

    title = data.get(
        "title",
        "Contrato"
    )

    artist_ids = data.get(
        "artistIds",
        []
    )

    contract_url = data.get(
        "contractUrl",
        ""
    )

    if not artist_ids:

        await interaction.response.send_message(
            "El contrato no tiene "
            "artista asignado.",
            ephemeral=True
        )

        return

    artist = str(
        artist_ids[0]
    ).lower().strip()

    if artist not in ARTIST_DISCORD_IDS:

        await interaction.response.send_message(
            "No tengo configurado "
            f"Discord para {artist}.",
            ephemeral=True
        )

        return

    user_id = ARTIST_DISCORD_IDS[
        artist
    ]

    channel = bot.get_channel(
        CONTRACTS_CHANNEL_ID
    )

    if channel is None:

        await interaction.response.send_message(
            "No encontré el canal "
            "#contratos.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="📄 CONTRATO PENDIENTE",
        description=(
            f"**{title}**\n\n"
            f"**Artista:** "
            f"{artist.upper()}\n"
            "⏳ **Estado:** "
            "Pendiente de firma\n\n"
            "Tenés un contrato pendiente "
            "de firma en LOWCUT// Records."
        )
    )

    if contract_url:

        embed.add_field(
            name="Contrato",
            value=(
                f"[Abrir contrato]"
                f"({contract_url})"
            ),
            inline=False
        )

    embed.set_footer(
        text="LOWCUT// RECORDS"
    )

    discord_message_id = data.get(
        "discordMessageId"
    )

    if discord_message_id:

        try:

            message = (
                await channel.fetch_message(
                    int(
                        discord_message_id
                    )
                )
            )

            await message.edit(
                content=f"<@{user_id}>",
                embed=embed,
                allowed_mentions=
                discord.AllowedMentions(
                    users=True
                )
            )

            await send_admin_log(
                interaction,
                "/notificarcontrato",
                (
                    f"**Contrato:** {title}\n"
                    f"**Artista:** "
                    f"{artist.upper()}\n"
                    "**Acción:** "
                    "Notificación actualizada"
                )
            )

            await interaction.response.send_message(
                "Notificación de "
                f"**{title}** actualizada.",
                ephemeral=True
            )

            return

        except discord.NotFound:
            pass

    message = await channel.send(
        content=f"<@{user_id}>",
        embed=embed,
        allowed_mentions=
        discord.AllowedMentions(
            users=True
        )
    )

    doc_ref.update({
        "discordMessageId":
            str(message.id)
    })

    await send_admin_log(
        interaction,
        "/notificarcontrato",
        (
            f"**Contrato:** {title}\n"
            f"**Artista:** "
            f"{artist.upper()}\n"
            "**Acción:** "
            "Notificación enviada"
        )
    )

    await interaction.response.send_message(
        f"Contrato **{title}** notificado.",
        ephemeral=True
    )


# =========================================================
# /CONTRATOS
# ADMIN
# =========================================================

@bot.tree.command(
    name="contratos",
    description=(
        "Muestra los contratos "
        "del portal LOWCUT//"
    ),
    guild=GUILD
)
@app_commands.default_permissions(
    administrator=True
)
async def contratos(
    interaction: discord.Interaction
):

    await interaction.response.defer(
        ephemeral=True
    )

    try:

        docs = list(
            db.collection(
                "contracts"
            ).stream()
        )

        if not docs:

            await interaction.followup.send(
                "No hay contratos registrados.",
                ephemeral=True
            )

            return

        pendientes = []
        firmados = []
        otros = []

        for doc in docs:

            data = doc.to_dict()

            title = data.get(
                "title",
                "Sin título"
            )

            status = str(
                data.get(
                    "status",
                    ""
                )
            ).lower().strip()

            artist_ids = data.get(
                "artistIds",
                []
            )

            artist = (
                str(
                    artist_ids[0]
                ).upper()
                if artist_ids
                else "SIN ARTISTA"
            )

            line = (
                f"**{title}** — {artist}"
            )

            if status == "pending":

                pendientes.append(
                    line
                )

            elif status == "signed":

                firmados.append(
                    line
                )

            else:

                otros.append(
                    f"{line} — `{status}`"
                )

        embed = discord.Embed(
            title="📑 LOWCUT// CONTRATOS"
        )

        embed.add_field(
            name=(
                f"⏳ Pendientes "
                f"({len(pendientes)})"
            ),
            value=(
                "\n".join(
                    pendientes
                )[:1024]
                if pendientes
                else "Ninguno."
            ),
            inline=False
        )

        embed.add_field(
            name=(
                f"✅ Firmados "
                f"({len(firmados)})"
            ),
            value=(
                "\n".join(
                    firmados
                )[:1024]
                if firmados
                else "Ninguno."
            ),
            inline=False
        )

        if otros:

            embed.add_field(
                name="Otros estados",
                value="\n".join(
                    otros
                )[:1024],
                inline=False
            )

        embed.set_footer(
            text="LOWCUT// RECORDS"
        )

        await interaction.followup.send(
            embed=embed,
            ephemeral=True
        )

    except Exception as e:

        print(
            "Error en /contratos: "
            f"{e}"
        )

        await interaction.followup.send(
            "Hubo un error leyendo "
            "los contratos.",
            ephemeral=True
        )


# =========================================================
# /ANUNCIO
# ADMIN
# =========================================================

@bot.tree.command(
    name="anuncio",
    description=(
        "Publica un anuncio "
        "en formato embed"
    ),
    guild=GUILD
)
@app_commands.default_permissions(
    administrator=True
)
async def anuncio(
    interaction: discord.Interaction,
    canal: discord.TextChannel,
    titulo: str,
    mensaje: str
):

    try:

        embed = discord.Embed(
            title=titulo,
            description=mensaje
        )

        embed.set_footer(
            text="LOWCUT// RECORDS"
        )

        await canal.send(
            embed=embed
        )

        await send_admin_log(
            interaction,
            "/anuncio",
            (
                f"**Canal:** "
                f"{canal.mention}\n"
                f"**Título:** {titulo}\n"
                f"**Mensaje:** {mensaje}"
            )
        )

        await interaction.response.send_message(
            "Anuncio publicado en "
            f"{canal.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "No tengo permiso para "
            "escribir en ese canal.",
            ephemeral=True
        )


# =========================================================
# /SAY
# ADMIN
# =========================================================

@bot.tree.command(
    name="say",
    description=(
        "Hace que LOWCUT// BOT "
        "publique un mensaje"
    ),
    guild=GUILD
)
@app_commands.default_permissions(
    administrator=True
)
async def say(
    interaction: discord.Interaction,
    canal: discord.TextChannel,
    mensaje: str
):

    try:

        await canal.send(
            mensaje,
            allowed_mentions=
            discord.AllowedMentions(
                users=True,
                roles=True,
                everyone=False
            )
        )

        await send_admin_log(
            interaction,
            "/say",
            (
                f"**Canal:** "
                f"{canal.mention}\n"
                f"**Mensaje:** {mensaje}"
            )
        )

        await interaction.response.send_message(
            f"Mensaje enviado en "
            f"{canal.mention}.",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "No tengo permiso para "
            "escribir en ese canal.",
            ephemeral=True
        )


# =========================================================
# /DELETEMENSAJES
# ADMIN
# =========================================================

@bot.tree.command(
    name="deletemensajes",
    description=(
        "Elimina los últimos "
        "mensajes del canal"
    ),
    guild=GUILD
)
@app_commands.default_permissions(
    administrator=True
)
async def deletemensajes(
    interaction: discord.Interaction,
    cantidad: int
):

    if cantidad < 1 or cantidad > 100:

        await interaction.response.send_message(
            "La cantidad tiene que "
            "estar entre 1 y 100.",
            ephemeral=True
        )

        return

    if not isinstance(
        interaction.channel,
        discord.TextChannel
    ):

        await interaction.response.send_message(
            "Este comando solo funciona "
            "en canales de texto.",
            ephemeral=True
        )

        return

    await interaction.response.defer(
        ephemeral=True
    )

    try:

        deleted = (
            await interaction.channel.purge(
                limit=cantidad
            )
        )

        await send_admin_log(
            interaction,
            "/deletemensajes",
            (
                f"**Canal:** "
                f"{interaction.channel.mention}\n"
                f"**Cantidad:** "
                f"{len(deleted)} mensajes"
            )
        )

        await interaction.followup.send(
            f"Se eliminaron "
            f"{len(deleted)} mensajes.",
            ephemeral=True
        )

    except discord.Forbidden:

        await interaction.followup.send(
            "El bot no tiene permiso "
            "para eliminar mensajes.",
            ephemeral=True
        )

    except Exception as e:

        print(
            "Error en "
            f"/deletemensajes: {e}"
        )

        await interaction.followup.send(
            "Ocurrió un error al "
            "eliminar mensajes.",
            ephemeral=True
        )


# =========================================================
# /CREARTICKETS
# ADMIN
# =========================================================

@bot.tree.command(
    name="creartickets",
    description=(
        "Publica el panel "
        "para abrir tickets"
    ),
    guild=GUILD
)
@app_commands.default_permissions(
    administrator=True
)
async def creartickets(
    interaction: discord.Interaction
):

    channel = bot.get_channel(
        TICKETS_PANEL_CHANNEL_ID
    )

    if channel is None:

        await interaction.response.send_message(
            "No encontré el canal "
            "del panel de tickets.",
            ephemeral=True
        )

        return

    embed = discord.Embed(
        title="🎫 LOWCUT// SUPPORT",
        description=(
            "¿Necesitás ayuda?\n\n"
            "Abrí un ticket privado para "
            "hablar con el staff de "
            "**LOWCUT// Records**.\n\n"

            "Podés usarlo para:\n"
            "• 📄 Contratos\n"
            "• 👤 Consultas como artista\n"
            "• 🎵 Música / demos\n"
            "• 🛠 Soporte general\n"
            "• 💬 Otras consultas\n\n"

            "Tocá el botón de abajo "
            "para abrir tu ticket."
        )
    )

    embed.set_footer(
        text="LOWCUT// RECORDS"
    )

    await channel.send(
        embed=embed,
        view=TicketPanelView()
    )

    await send_admin_log(
        interaction,
        "/creartickets",
        (
            f"**Canal:** "
            f"{channel.mention}\n"
            "**Acción:** "
            "Panel de tickets publicado"
        )
    )

    await interaction.response.send_message(
        "Panel de tickets publicado "
        f"en {channel.mention}.",
        ephemeral=True
    )


# =========================================================
# START
# =========================================================

bot.run(TOKEN)