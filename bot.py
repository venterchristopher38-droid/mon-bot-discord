import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import asyncio
from datetime import datetime, timedelta
import os

# ────────────────────────────────────────────
#  CONFIGURATION
# ────────────────────────────────────────────
TOKEN = os.getenv("TOKEN")          # Remplace par ton token
PREFIX = "!"                      # Préfixe des commandes
LOG_CHANNEL_NAME = "logs"         # Nom du salon de logs
WELCOME_CHANNEL_NAME = "bienvenue"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree  # Slash commands


# ════════════════════════════════════════════
#  ÉVÉNEMENTS
# ════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ Connecté en tant que {bot.user} (ID: {bot.user.id})")
    await tree.sync()
    auto_message.start()
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching,
        name=f"{PREFIX}help | {len(bot.guilds)} serveur(s)"
    ))


@bot.event
async def on_member_join(member: discord.Member):
    """Message de bienvenue + attribution du rôle automatique."""
    guild = member.guild

    # Message de bienvenue
    channel = discord.utils.get(guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if channel:
        embed = discord.Embed(
            title=f"👋 Bienvenue, {member.display_name} !",
            description=f"Tu es le membre **#{guild.member_count}** de **{guild.name}**.\nLis bien les règles et amuse-toi bien !",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    # Rôle automatique
    role = discord.utils.get(guild.roles, name="Faction Roleplayer")
    if role:
        await member.add_roles(role)
        print(f"✅ Rôle 'Membre' attribué à {member}")


@bot.event
async def on_member_remove(member: discord.Member):
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL_NAME)
    if channel:
        await channel.send(f"👋 **{member.display_name}** a quitté le serveur.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Tu n'as pas la permission d'utiliser cette commande.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Membre introuvable.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Argument manquant. Utilise `{PREFIX}help {ctx.command}` pour plus d'infos.")
    else:
        await ctx.send(f"❌ Erreur : `{error}`")


# ════════════════════════════════════════════
#  HELPER : LOG
# ════════════════════════════════════════════

async def send_log(guild: discord.Guild, embed: discord.Embed):
    log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)
    if log_channel:
        await log_channel.send(embed=embed)


# ════════════════════════════════════════════
#  MODÉRATION
# ════════════════════════════════════════════

@bot.command(name="ban", help="Bannir un membre. Usage: !ban @membre [raison]")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    await member.ban(reason=reason)
    embed = discord.Embed(title="🔨 Bannissement", color=discord.Color.red(), timestamp=datetime.utcnow())
    embed.add_field(name="Membre", value=str(member), inline=True)
    embed.add_field(name="Par", value=str(ctx.author), inline=True)
    embed.add_field(name="Raison", value=reason, inline=False)
    await ctx.send(embed=embed)
    await send_log(ctx.guild, embed)


@bot.command(name="unban", help="Débannir un membre. Usage: !unban nom#tag")
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, member_name: str):
    banned = [entry async for entry in ctx.guild.bans()]
    for ban_entry in banned:
        if str(ban_entry.user) == member_name:
            await ctx.guild.unban(ban_entry.user)
            await ctx.send(f"✅ **{ban_entry.user}** a été débanni.")
            return
    await ctx.send("❌ Membre introuvable dans les bans.")


@bot.command(name="kick", help="Expulser un membre. Usage: !kick @membre [raison]")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "Aucune raison fournie"):
    await member.kick(reason=reason)
    embed = discord.Embed(title="👢 Expulsion", color=discord.Color.orange(), timestamp=datetime.utcnow())
    embed.add_field(name="Membre", value=str(member), inline=True)
    embed.add_field(name="Par", value=str(ctx.author), inline=True)
    embed.add_field(name="Raison", value=reason, inline=False)
    await ctx.send(embed=embed)
    await send_log(ctx.guild, embed)


@bot.command(name="mute", help="Mute un membre. Usage: !mute @membre [durée en minutes]")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, duration: int = 10):
    until = discord.utils.utcnow() + timedelta(minutes=duration)
    await member.timeout(until, reason=f"Mute par {ctx.author}")
    await ctx.send(f"🔇 **{member.display_name}** a été mute pour **{duration} minute(s)**.")


@bot.command(name="unmute", help="Unmute un membre. Usage: !unmute @membre")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"🔊 **{member.display_name}** a été unmute.")


@bot.command(name="clear", aliases=["purge"], help="Supprimer des messages. Usage: !clear [nombre]")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🗑️ **{len(deleted) - 1}** message(s) supprimé(s).")
    await asyncio.sleep(3)
    await msg.delete()


@bot.command(name="warn", help="Avertir un membre. Usage: !warn @membre [raison]")
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason: str = "Aucune raison"):
    embed = discord.Embed(title="⚠️ Avertissement", color=discord.Color.yellow(), timestamp=datetime.utcnow())
    embed.add_field(name="Membre", value=str(member), inline=True)
    embed.add_field(name="Par", value=str(ctx.author), inline=True)
    embed.add_field(name="Raison", value=reason, inline=False)
    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        pass
    await ctx.send(embed=embed)
    await send_log(ctx.guild, embed)


@bot.command(name="slowmode", help="Définir le slowmode. Usage: !slowmode [secondes]")
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx, seconds: int = 0):
    await ctx.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await ctx.send("⏩ Slowmode désactivé.")
    else:
        await ctx.send(f"🐢 Slowmode défini à **{seconds} seconde(s)**.")


@bot.command(name="lock", help="Verrouiller un salon.")
@commands.has_permissions(manage_channels=True)
async def lock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Salon verrouillé.")


@bot.command(name="unlock", help="Déverrouiller un salon.")
@commands.has_permissions(manage_channels=True)
async def unlock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Salon déverrouillé.")


# ════════════════════════════════════════════
#  GESTION DES RÔLES
# ════════════════════════════════════════════

@bot.command(name="addrole", help="Ajouter un rôle. Usage: !addrole @membre NomDuRole")
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send(f"❌ Rôle `{role_name}` introuvable.")
        return
    await member.add_roles(role)
    await ctx.send(f"✅ Rôle **{role.name}** ajouté à **{member.display_name}**.")


@bot.command(name="removerole", help="Retirer un rôle. Usage: !removerole @membre NomDuRole")
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send(f"❌ Rôle `{role_name}` introuvable.")
        return
    await member.remove_roles(role)
    await ctx.send(f"✅ Rôle **{role.name}** retiré à **{member.display_name}**.")


@bot.command(name="roles", help="Lister les rôles d'un membre. Usage: !roles @membre")
async def roles(ctx, member: discord.Member = None):
    member = member or ctx.author
    role_list = [r.mention for r in member.roles if r.name != "@everyone"]
    embed = discord.Embed(
        title=f"🎭 Rôles de {member.display_name}",
        description=", ".join(role_list) if role_list else "Aucun rôle",
        color=member.color
    )
    await ctx.send(embed=embed)


@bot.command(name="roleinfo", help="Infos sur un rôle. Usage: !roleinfo NomDuRole")
async def roleinfo(ctx, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        await ctx.send(f"❌ Rôle `{role_name}` introuvable.")
        return
    embed = discord.Embed(title=f"🎭 {role.name}", color=role.color)
    embed.add_field(name="ID", value=role.id)
    embed.add_field(name="Membres", value=len(role.members))
    embed.add_field(name="Mentionnable", value=role.mentionable)
    embed.add_field(name="Hoisted", value=role.hoist)
    embed.add_field(name="Créé le", value=role.created_at.strftime("%d/%m/%Y"))
    await ctx.send(embed=embed)


# ════════════════════════════════════════════
#  COMMANDES UTILES
# ════════════════════════════════════════════

@bot.command(name="userinfo", aliases=["ui"], help="Infos sur un membre. Usage: !userinfo [@membre]")
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"👤 {member}", color=member.color, timestamp=datetime.utcnow())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Pseudo", value=member.display_name)
    embed.add_field(name="Compte créé", value=member.created_at.strftime("%d/%m/%Y"))
    embed.add_field(name="Rejoint le", value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "?")
    embed.add_field(name="Rôles", value=len(member.roles) - 1)
    embed.add_field(name="Bot ?", value="✅" if member.bot else "❌")
    await ctx.send(embed=embed)


@bot.command(name="serverinfo", aliases=["si"], help="Infos sur le serveur.")
async def serverinfo(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=f"🏠 {guild.name}", color=discord.Color.blurple(), timestamp=datetime.utcnow())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="ID", value=guild.id)
    embed.add_field(name="Propriétaire", value=str(guild.owner))
    embed.add_field(name="Membres", value=guild.member_count)
    embed.add_field(name="Salons", value=len(guild.channels))
    embed.add_field(name="Rôles", value=len(guild.roles))
    embed.add_field(name="Créé le", value=guild.created_at.strftime("%d/%m/%Y"))
    await ctx.send(embed=embed)


@bot.command(name="ping", help="Latence du bot.")
async def ping(ctx):
    await ctx.send(f"🏓 Pong ! Latence : **{round(bot.latency * 1000)}ms**")


@bot.command(name="say", help="Faire parler le bot. Usage: !say [#salon] message")
@commands.has_permissions(manage_messages=True)
async def say(ctx, channel: discord.TextChannel = None, *, message: str):
    target = channel or ctx.channel
    await ctx.message.delete()
    await target.send(message)


@bot.command(name="embed", help="Envoyer un embed. Usage: !embed titre | description | couleur(hex)")
@commands.has_permissions(manage_messages=True)
async def send_embed(ctx, *, args: str):
    parts = [p.strip() for p in args.split("|")]
    title = parts[0] if len(parts) > 0 else "Titre"
    description = parts[1] if len(parts) > 1 else ""
    try:
        color = discord.Color(int(parts[2].strip("#"), 16)) if len(parts) > 2 else discord.Color.blurple()
    except Exception:
        color = discord.Color.blurple()
    embed = discord.Embed(title=title, description=description, color=color)
    await ctx.message.delete()
    await ctx.send(embed=embed)


@bot.command(name="poll", help="Créer un sondage. Usage: !poll Question | Option1 | Option2 ...")
async def poll(ctx, *, args: str):
    parts = [p.strip() for p in args.split("|")]
    question = parts[0]
    options = parts[1:]
    if len(options) < 2:
        await ctx.send("❌ Il faut au moins 2 options.")
        return
    emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    description = "\n".join([f"{emojis[i]} {opt}" for i, opt in enumerate(options[:10])])
    embed = discord.Embed(title=f"📊 {question}", description=description, color=discord.Color.gold())
    embed.set_footer(text=f"Sondage par {ctx.author.display_name}")
    msg = await ctx.send(embed=embed)
    for i in range(len(options[:10])):
        await msg.add_reaction(emojis[i])





# ════════════════════════════════════════════
#  MESSAGES AUTOMATIQUES (tâche planifiée)
# ════════════════════════════════════════════

AUTO_CHANNEL = "général"   # Nom du salon pour les messages automatiques
AUTO_INTERVAL_HOURS = 6    # Intervalle en heures

AUTO_MESSAGES = [
    "📌 N'oubliez pas de lire le règlement du serveur !",
    "🎉 Merci d'être là, la communauté grandit grâce à vous !",
    "💡 Une question ? Posez-la dans le bon salon !",
    "🔔 Activez les notifications pour ne rien rater !",
]
auto_msg_index = 0

@tasks.loop(hours=AUTO_INTERVAL_HOURS)
async def auto_message():
    global auto_msg_index
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, name=AUTO_CHANNEL)
        if channel:
            msg = AUTO_MESSAGES[auto_msg_index % len(AUTO_MESSAGES)]
            await channel.send(msg)
    auto_msg_index += 1


# ════════════════════════════════════════════
#  SYSTÈME DE TICKETS
# ════════════════════════════════════════════

TICKET_CATEGORY_NAME = "Tickets"      # Catégorie où créer les salons tickets
TICKET_SUPPORT_ROLE  = "Support"      # Rôle qui peut voir les tickets
TICKET_LOG_CHANNEL   = "ticket-logs"  # Salon de logs des tickets

# Dictionnaire en mémoire : user_id -> channel_id
open_tickets: dict[int, int] = {}


class TicketCloseView(discord.ui.View):
    """Bouton 'Fermer le ticket' affiché dans le salon ticket."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild   = interaction.guild

        # Log avant suppression
        log_ch = discord.utils.get(guild.text_channels, name=TICKET_LOG_CHANNEL)
        if log_ch:
            embed = discord.Embed(
                title="🎫 Ticket fermé",
                description=f"Salon : **#{channel.name}**\nFermé par : {interaction.user.mention}",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            await log_ch.send(embed=embed)

        # Retire le ticket de la mémoire
        uid = next((k for k, v in open_tickets.items() if v == channel.id), None)
        if uid:
            del open_tickets[uid]

        await interaction.response.send_message("🔒 Fermeture du ticket dans 5 secondes...")
        await asyncio.sleep(5)
        await channel.delete()


class TicketOpenView(discord.ui.View):
    """Bouton 'Ouvrir un ticket' affiché dans le salon de support."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Ouvrir un ticket", style=discord.ButtonStyle.success, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild  = interaction.guild
        author = interaction.user

        # Vérifie si un ticket est déjà ouvert
        if author.id in open_tickets:
            existing = guild.get_channel(open_tickets[author.id])
            if existing:
                await interaction.response.send_message(
                    f"❌ Tu as déjà un ticket ouvert : {existing.mention}", ephemeral=True
                )
                return

        # Cherche / crée la catégorie
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if not category:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        # Permissions du salon
        support_role = discord.utils.get(guild.roles, name=TICKET_SUPPORT_ROLE)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            author:             discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        # Crée le salon
        channel_name = f"ticket-{author.name}".lower().replace(" ", "-")[:32]
        ticket_channel = await guild.create_text_channel(
            channel_name,
            category=category,
            overwrites=overwrites
        )
        open_tickets[author.id] = ticket_channel.id

        # Message d'accueil dans le ticket
        embed = discord.Embed(
            title="🎫 Ticket ouvert — 22 Side Illégal",
            description=(
                f"Bonjour {author.mention} !\n\n"
                "Merci de contacter le support de **22 Side Illégal**.\n\n"
                "📋 **Merci de préciser :**\n"
                "• Ton nom de personnage In-Game\n"
                "• Le motif de ta demande\n"
                "• Les détails de la situation (date, lieu, personnes impliquées)\n\n"
                "⚠️ Rappel : toute action IC doit être traitée via les leviers internes "
                "(Justice, Police, Services de Santé).\n\n"
                "Un membre du staff va prendre en charge ton ticket rapidement.\n"
                "Clique sur **🔒 Fermer le ticket** une fois ta demande traitée."
            ),
            color=discord.Color.from_rgb(30, 30, 30),
            timestamp=datetime.utcnow()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text="Administration Générale — 22 Side Illégal")
        await ticket_channel.send(embed=embed, view=TicketCloseView())

        await interaction.response.send_message(
            f"✅ Ton ticket a été créé : {ticket_channel.mention}", ephemeral=True
        )

        # Log
        log_ch = discord.utils.get(guild.text_channels, name=TICKET_LOG_CHANNEL)
        if log_ch:
            log_embed = discord.Embed(
                title="🎫 Ticket ouvert",
                description=f"Par : {author.mention}\nSalon : {ticket_channel.mention}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            await log_ch.send(embed=log_embed)


@bot.command(name="ticket", help="Envoyer le panel d'ouverture de ticket. Usage: !ticket [#salon]")
@commands.has_permissions(manage_channels=True)
async def ticket_panel(ctx, channel: discord.TextChannel = None):
    target = channel or ctx.channel
    await ctx.message.delete()
    embed = discord.Embed(
        title="🎫 Support — 22 Side Illégal",
        description=(
            "**Bienvenue sur le système de support de 22 Side Illégal.**\n\n"
            "Tu rencontres un problème en jeu, tu as une question sur le serveur "
            "ou tu souhaites contacter l'équipe administrative ?\n\n"
            "📌 **Avant d'ouvrir un ticket :**\n"
            "• Vérifie que ta demande ne peut pas être traitée In-Character (IC)\n"
            "• Sois précis et respectueux dans ta demande\n"
            "• Un seul ticket à la fois par joueur\n\n"
            "Clique sur le bouton ci-dessous pour ouvrir un ticket privé.\n"
            "Un membre du staff te répondra dans les plus brefs délais."
        ),
        color=discord.Color.from_rgb(30, 30, 30)
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text="Administration Générale — 22 Side Illégal")
    await target.send(embed=embed, view=TicketOpenView())
    await ctx.send(f"✅ Panel ticket envoyé dans {target.mention}.", delete_after=5)


@bot.command(name="addticket", help="Ajouter un membre à un ticket. Usage: !addticket @membre")
@commands.has_permissions(manage_channels=True)
async def addticket(ctx, member: discord.Member):
    await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
    await ctx.send(f"✅ **{member.display_name}** a été ajouté au ticket.")


@bot.command(name="removeticket", help="Retirer un membre d'un ticket. Usage: !removeticket @membre")
@commands.has_permissions(manage_channels=True)
async def removeticket(ctx, member: discord.Member):
    await ctx.channel.set_permissions(member, view_channel=False)
    await ctx.send(f"✅ **{member.display_name}** a été retiré du ticket.")


# ════════════════════════════════════════════
#  COMMANDE ANNONCE (style screen RP)
# ════════════════════════════════════════════

@bot.command(name="annonce", help="Envoyer une annonce richement formatée. Usage: !annonce [#salon]")
@commands.has_permissions(manage_messages=True)
async def annonce(ctx, channel: discord.TextChannel = None):
    """
    Lance un assistant interactif en DM pour construire l'annonce étape par étape,
    puis l'envoie dans le salon cible avec le même style que le screen (embed + bullet points).
    """
    target = channel or ctx.channel
    author = ctx.author
    await ctx.message.delete()

    def check(m):
        return m.author == author and isinstance(m.channel, discord.DMChannel)

    try:
        await author.send(
            "📝 **Assistant Annonce** — Je vais t'aider à créer ton annonce.\n\n"
            "**Étape 1/5** — Quel est le **titre** de l'annonce ?"
        )
    except discord.Forbidden:
        await ctx.send("❌ Je ne peux pas t'envoyer de DM. Active les DMs depuis ce serveur.", delete_after=10)
        return

    await ctx.send(f"📬 {author.mention} Vérifie tes DMs pour créer l'annonce !", delete_after=8)

    try:
        # Titre
        msg = await bot.wait_for("message", check=check, timeout=120)
        titre = msg.content

        # Sous-titre / intro
        await author.send("**Étape 2/5** — Écris le **texte d'introduction** (description principale) :")
        msg = await bot.wait_for("message", check=check, timeout=120)
        intro = msg.content

        # Sections avec bullet points
        await author.send(
            "**Étape 3/5** — Ajoute des **sections à bullet points**.\n"
            "Format : `Titre Section :: Contenu de la section`\n"
            "Envoie autant de lignes que tu veux, puis tape `STOP` pour terminer."
        )
        sections = []
        while True:
            msg = await bot.wait_for("message", check=check, timeout=120)
            if msg.content.upper() == "STOP":
                break
            if "::" in msg.content:
                parts = msg.content.split("::", 1)
                sections.append((parts[0].strip(), parts[1].strip()))
            else:
                await author.send("⚠️ Format invalide. Utilise `Titre :: Contenu` ou tape `STOP`.")

        # Texte de conclusion
        await author.send("**Étape 4/5** — Texte de **conclusion** (ex: lien vers vérification, instructions finales) :")
        msg = await bot.wait_for("message", check=check, timeout=120)
        conclusion = msg.content

        # Signature
        await author.send("**Étape 5/5** — **Signature** (ex: Administration Générale — Mon Serveur) :")
        msg = await bot.wait_for("message", check=check, timeout=120)
        signature = msg.content

    except asyncio.TimeoutError:
        await author.send("⏰ Temps écoulé. Annonce annulée.")
        return

    # ── Construction de l'embed ──
    embed = discord.Embed(
        title=titre,
        color=discord.Color.from_rgb(32, 34, 37)   # couleur sombre style Discord
    )
    embed.description = intro

    for section_title, section_body in sections:
        embed.add_field(
            name=f"**{section_title}**",
            value=f"• {section_body}",
            inline=False
        )

    if conclusion:
        embed.add_field(name="\u200b", value=conclusion, inline=False)

    embed.set_footer(text=signature)
    embed.timestamp = datetime.utcnow()

    # Icône du serveur en thumbnail
    if ctx.guild.icon:
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url)

    await target.send(embed=embed)
    await author.send(f"✅ Annonce envoyée dans **#{target.name}** !")


# ════════════════════════════════════════════
#  MISE À JOUR DU !help
# ════════════════════════════════════════════

# (remplacement de l'ancienne commande help pour inclure les nouvelles features)
bot.remove_command("help")  # Supprime le help par défaut de discord.py

@bot.command(name="help", aliases=["aide"], help="Afficher l'aide complète.")
async def help_v2(ctx):
    embed = discord.Embed(title="📖 Aide du Bot", color=discord.Color.blue())
    embed.set_footer(text=f"Préfixe : {PREFIX}")

    embed.add_field(name="🔨 Modération", value=
        f"`{PREFIX}ban` `{PREFIX}unban` `{PREFIX}kick`\n"
        f"`{PREFIX}mute` `{PREFIX}unmute` `{PREFIX}warn`\n"
        f"`{PREFIX}clear` `{PREFIX}slowmode` `{PREFIX}lock` `{PREFIX}unlock`",
        inline=False)

    embed.add_field(name="🎭 Rôles", value=
        f"`{PREFIX}addrole` `{PREFIX}removerole` `{PREFIX}roles` `{PREFIX}roleinfo`",
        inline=False)

    embed.add_field(name="🎫 Tickets", value=
        f"`{PREFIX}ticket` — affiche le panel\n"
        f"`{PREFIX}addticket` `{PREFIX}removeticket`",
        inline=False)

    embed.add_field(name="📢 Annonces", value=
        f"`{PREFIX}annonce [#salon]` — assistant interactif par DM",
        inline=False)

    embed.add_field(name="ℹ️ Infos", value=
        f"`{PREFIX}userinfo` `{PREFIX}serverinfo` `{PREFIX}ping`",
        inline=False)

    embed.add_field(name="💬 Messages", value=
        f"`{PREFIX}say` `{PREFIX}embed` `{PREFIX}poll`",
        inline=False)

    await ctx.send(embed=embed)


# ════════════════════════════════════════════
#  LANCEMENT
# ════════════════════════════════════════════

# Enregistre les vues persistantes (survive aux redémarrages)
bot.add_view(TicketOpenView())
bot.add_view(TicketCloseView())

bot.run(TOKEN)
