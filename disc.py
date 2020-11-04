# -*- coding: utf-8 -*-
#
# disc.py
#
# Copyright (C) 2020, Philipp Göldner  <pgoeldner (at) stud.uni-heidelberg.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

# Discord Queue Bot der während der eLearning Challenge https://elearning.mathphys.info/ entstanden ist.

# Importieren der Packages
import discord
import yaml
from discord.ext import commands
from collections import deque

# Lade Config
with open('config.yaml') as f:
    config = yaml.load(f, Loader=yaml.SafeLoader)

token   = config.get('token')
prefix  = config.get('prefix')
roles   = config.get('roles')

# Initialisierung
bot = commands.Bot(command_prefix=prefix)
bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="mit anderen Bots"))

# Kontrolliere, ob API-Key und Rollen vorhanden 
if not token:
    raise RuntimeError("Config must contain api_key")
if not roles:
    raise RuntimeError("Config must contain roles")

# Speichert Mitglieder der 
member_queues = {}
# Speichert ID's der Server und den Aktivitaetszustand
enabled = {}

# Definiere gebrauchte Funktionen
def get_displaynick(author):
    '''Funktion gibt Anzeigenamen auf dem aktuellen Server zurueck.

    Args:
        author (discord.abc.User):  Mitglied eines Servers

    Returns:
        str:                        Anzeigenamen des Benutzers
    '''
    nick = ""
    # Erhalte Nicknamen, wenn vorhanden
    if author.nick:
        nick = author.nick
    # Ansonsten erhalte Discord-Benutzernamen 
    else:
        nick = str(author).split("#")[0]
    return nick

def checkRoles(userMessage, accessRoles):
    '''Kontrolliert, ob Nutzer mindestens einer der angegebenen Rollen angehört.

    Args:
        userMessage (discord.message):  Nachricht des Nutzers
        accessRoles (list):             Zu kontrollierende Rollen

    Returns:
        bool
    '''
    if set(role.name for role in userMessage.author.roles) & set(accessRoles):
        return True
    else:
        return False


# Administrative Befehle

# Startet die Warteschlange auf dem aktuellen Server für alle Nutzer in beliebiegen Kanälen. Aktiviert Nutzerbefehle.
@bot.command(pass_context=True, help="Öffnet die Warteschlange")
async def start(ctx):
    print(__name__, 'issued')
    # Teste die Rechte
    if checkRoles(ctx.message, roles['tutor']):
        # Setze Status des Bots auf aktiv
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="ob Studis warten"))
        # Feedback an Tutor
        await ctx.send("Warteschlange ist nun geöffnet.")
        # Server wird als aktiv gelistet
        enabled[ctx.message.guild.id] = True

# Schließt die Warteschlange auf dem aktuellen Server. Deaktiviert Nutzerbefehle.
@bot.command(pass_context=True, help="Schließt die Warteschlange")
async def stop(ctx):
    if checkRoles(ctx.message, roles['tutor']):
        # Inaktiven Status wenn auf keinem Server aktiv
        if not enabled:
            await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="mit anderen Bots"))
        # Server wird als inaktiv gelistet
        enabled[ctx.message.guild.id] = False
        # Feedback an Tutor
        try:
            member_queues.pop(ctx.message.guild.id, default=False)
            await ctx.send("Warteschlange ist nun geschlossen.")
        except KeyError:
            await ctx.send('Die Warteschlange ist noch nicht geöffnet worden.')

# Schiebt den Nächsten aus der Warteschlange in den Raum des Ausführenden. Beide müssen mit dem Voicechat verbunden sein.
@bot.command(pass_context=True)
async def next(ctx):
    guild = ctx.message.guild.id
    author = ctx.message.author
    voice_state = author.voice
    vc = voice_state.channel

    if guild not in enabled:
        enabled[guild] = False

    if checkRoles(ctx.message, roles['tutor']):
        if not enabled[guild]:
            await ctx.send(f"Hallo {get_displaynick(author)}. Die Warteschlange ist aktuell noch geschlossen. Du kannst sie mit $start öffnen.")
        else:
            if len(member_queues[guild]) >= 1:
                member = member_queues[guild].popleft()
            else:
                await ctx.send("Die Warteschlange ist leer :(")
            try:
                next_member = member_queues[guild].popleft()
                member_queues[guild].appendleft(next_member)
                await ctx.send(f"{get_displaynick(member)} ist dran. Der nächste ist {next_member.mention}")
                await member.move_to(vc)
            except IndexError:
                await member.move_to(vc)
                await ctx.send(f"{get_displaynick(member)} ist dran. Der nächste ist Niemand :(")

# Gibt eine Liste der Mitglieder der Warteschlange auf dem aktuellen Server aus
@bot.command(pass_context=True)
async def ls(ctx):
    author = ctx.message.author
    guild = ctx.message.guild.id
    if guild not in enabled:
        enabled[guild] = False
    if checkRoles(ctx.message, roles['tutor']):
        if not enabled[guild]:
            await ctx.send(f"Hallo {get_displaynick(author)}. Die Warteschlange ist aktuell noch geschlossen. Du kannst sie mit $start öffnen.")
        else:
            if member_queues[guild]:
                for number, member in enumerate(member_queues[guild]):
                    await ctx.send(f"{number+1}. {get_displaynick(member)}")
            else:
                await ctx.send(f"Es ist im Moment niemand in der Warteschlange!")


# Nutzerbefehle

# Gibt den aktuellen Status der Warteschlange auf dem Server an.
@bot.command(pass_context=True, help="Aktueller Status der Warteschlange")
async def status(ctx):
    # todo this can fail
    if ctx.message.guild.id in enabled:
        if enabled[ctx.message.guild.id]:
            await ctx.send("Warteschlange ist offen")
        else:
            await ctx.send("Warteschlange ist geschlossen")
    else:
        enabled[ctx.message.guild.id] = False

# Nutzer trägt sich in die Warteschlange ein. 
@bot.command(pass_context=True, help="Anstellen in Warteschlange")
async def wait(ctx):
    author = ctx.message.author
    guild = ctx.message.guild.id
    if guild not in enabled:
        enabled[guild] = False

    if not enabled[guild]:
        await ctx.send(f"Hallo {get_displaynick(author)} die Warteschlange ist aktuell geschlossen.")
    else:
        if guild not in member_queues:
                member_queues[guild] = deque()
                member_queues[guild].append(author)
                await ctx.send(f"Hallo {get_displaynick(author)} du bist aktuell in Position {member_queues[guild].index(author)+1}. Mit $wait kannst du dir deine aktuelle Position anzeigen lassen")
        else:
            if author in member_queues[guild]:
                pass
            else:
                member_queues[guild].append(author)
            await ctx.send(f"Hallo {get_displaynick(author)} du bist aktuell in Position {member_queues[guild].index(author)+1}. Mit $wait kannst du dir deine aktuelle Position anzeigen lassen")

# Nutzer verlässt die Warteschlange
@bot.command(pass_context=True)
async def leave(ctx, help="Verlassen der Warteschlange"):
    author = ctx.message.author
    guild = ctx.message.guild.id
    if guild not in enabled:
        enabled[guild] = False
    if not enabled[guild]:
        await ctx.send(f"Hallo {get_displaynick(author)} die Warteschlange ist aktuell geschlossen. Bei Fragen kannst du unseren 24/7 Chatbot befragen.")
    else:
        if guild not in member_queues:
                await ctx.send(f"Hallo {get_displaynick(author)} du bist aktuell nicht in der Warteschlange. Du kannst dich mit $wait anstellen")
        else:
            if author in member_queues[guild]:
                member_queues[guild].remove(author)
                await ctx.send(f"Hallo {get_displaynick(author)} du hast die Warteschlange verlassen.")
            else:
                await ctx.send(f"Hallo {get_displaynick(author)} du bist aktuell nicht in der Warteschlange. Du kannst dich mit $wait anstellen")

# Bot starten
bot.run(token)