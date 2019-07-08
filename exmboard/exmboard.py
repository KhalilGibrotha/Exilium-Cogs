import discord
from discord.ext import commands
import pathlib
from cogs.utils.dataIO import dataIO
import aiohttp
import io
from .utils import checks
import json
import operator
import collections
from PIL import Image, ImageDraw, ImageFont
import urllib.request as urllib
import subprocess
import os
import math

path = 'data/exilium/exmboard'

bgImage = Image.open(path + '/bg.png').convert('RGB')
headerFont = ImageFont.truetype(path + '/battlefieldv4.ttf', size=60)
fnt = ImageFont.truetype(path + '/futura.ttf', size=50)

#bot = commands.Bot(command_prefix=commands.when_mentioned, description="Battlefield Stats Tracker")

class ExmBoard:

    __author__ = "mengy007 (mengy#1441)"
    __version__ = "1.0"

    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        try:
            self.settings = dataIO.load_json(path + '/settings.json')
            #self.bgImage = Image.open(path + '/bg.jpg').convert('RBGA')
        except Exception:
            self.settings = {}

    def save_json(self):
        dataIO.save_json(path + '/settings.json', self.settings)

    def init_server(self, server: discord.Server, reset=False):
        if server.id not in self.settings or reset:
            self.settings[server.id] = {
              'whitelist': [],
              'players': [],
              'recruits': {}
            }
        else:
            if 'recruits' not in self.settings[server.id]:
                self.settings[server.id]['recruits'] = {}

    @commands.group(name='exmboardset', pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_messages=True)
    async def _group(self, ctx):
        """
        settings for leaderboard
        """
        if ctx.invoked_subcommand is None:
            #await self.bot.send_help(ctx)
            #await ctx.send_help()
            await self.send_cmd_help(ctx)

    @_group.command(name='addrecruit', pass_context=True, no_pm=True)
    async def addrecruit(self, ctx, playername):
        """
        add recruit to player
        """
        server = ctx.message.server
        self.init_server(server)

        if playername in self.settings[server.id]['recruits'].keys():
          self.settings[server.id]['recruits'][playername] += 1
        else:
          self.settings[server.id]['recruits'][playername] = 1        

        self.save_json()
        await self.bot.say('Recruit added to ' + playername)
        return await self.bot.say(playername + ' currently has ' + str(self.settings[server.id]['recruits'][playername]) + ' recruits!')


    @_group.command(name='removerecruit', pass_context=True, no_pm=True)
    async def removerecruit(self, ctx, playername):
        """
        remove recruit to player
        """
        server = ctx.message.server
        self.init_server(server)

        if playername in self.settings[server.id]['recruits'].keys():
          if self.settings[server.id]['recruits'][playername] == 0:
            return await self.bot.say(playername + ' currently has 0 recruits!')
          else:
            self.settings[server.id]['recruits'][playername] -= 1
        else:
          return await self.bot.say(playername + ' currently has 0 recruits!')

        self.save_json()
        await self.bot.say('Recruit removed from ' + playername)
        return await self.bot.say(playername + ' currently has ' + str(self.settings[server.id]['recruits'][playername]) + ' recruits!')

    @_group.command(name='add', pass_context=True, no_pm=True)
    async def add(self, ctx, playername):
        """
        add a player to be tracked on leaderboard
        """
        server = ctx.message.server
        self.init_server(server)

        url = "https://api.battlefieldtracker.com/api/v1/bfv/profile/origin/" + playername.replace(" ", "%20")
        
        async with aiohttp.get(url) as response:
            jsonObj = await response.json()
            if response.status == 200 and jsonObj['status'] == 'Success':
                if playername in self.settings[server.id]['players']:
                    return await self.bot.say('Player already on leaderboard')
                self.settings[server.id]['players'].append(playername)
                self.save_json()                
                await self.bot.say('Player added to leaderboard')
                await self.bot.say('Updating player data. This may take a few minutes')
                await update_player_data()
                return await self.bot.say('Done updating player data!')

            elif response.status == 200 and jsonObj['status'] == 'Private':
                return await self.bot.say('Player chose to not share data. :(')

            else:
                return await self.bot.say('Player not found in Origin')
        

    @_group.command(name='remove', pass_context=True, no_pm=True)
    async def remove(self, ctx, playername):
        """
        remove a player from being tracked on leaderboard
        """

        server = ctx.message.server
        self.init_server(server)

        if playername in self.settings[server.id]['players']:
            self.settings[server.id]['players'].remove(playername)
            self.save_json()
            await self.bot.say('Player removed from leaderboard')            
            await self.bot.say('Updating player data. This may take a few minutes')
            await update_player_data()
            return await self.bot.say('Done updating player data!')

        await self.bot.say('Player not on leaderboard')

    @_group.command(name='whitelist', pass_context=True, no_pm=True)
    async def whitelist(self, ctx, channel: discord.Channel):
        """
        add a channel where the leaderboard is allowed (if you want)
        """

        server = ctx.message.server
        self.init_server(server)

        if channel.id in self.settings[server.id]['whitelist']:
            return await self.bot.say('Channel already whitelisted')
        self.settings[server.id]['whitelist'].append(channel.id)
        self.save_json()
        await self.bot.say('Channel whitelisted.')

    @_group.command(name='unwhitelist', pass_context=True, no_pm=True)
    async def unwhitelist(self, ctx, channel: discord.Channel):
        """
        unwhitelist a channel
        """

        server = ctx.message.server
        self.init_server(server)

        if channel.id not in self.settings[server.id]['whitelist']:
            return await self.bot.say('Channel wasn\'t whitelisted')
        self.settings[server.id]['whitelist'].remove(channel.id)
        self.save_json()
        await self.bot.say('Channel unwhitelisted.')

    @_group.command(name='reset', pass_context=True, no_pm=True)
    async def rset(self, ctx):
        """
        resets to defaults
        """

        server = ctx.message.server
        self.init_server(server, True)
        await self.bot.say('Settings reset')

    @commands.command(pass_context=True, no_pm=True, name="exmboard")
    async def exmboard(self, ctx, scope, stat, limit = 0):
        """Leaderboard Stats"""

        server = ctx.message.server
        channel = ctx.message.channel
        bgImage = Image.open(path + '/bg.png').convert('RGB')
        validScopes = ['assault', 'recon', 'support', 'medic', 'tanker', 'pilot', 'firestorm']
        validFirestormStats = ['squadLosses', 'safes', 'killsPerMinute', 'squadWins', 'roadKills', 'vehicleBreakouts', 'vehiclesDestroyed', 'matchesPlayed', 'tanks', 'capturePoints', 'healing', 'kills', 'supplyDrops', 'killsPerMatch', 'headshots', 'timePlayed', 'vehicleWeaponKills', 'soloLosses', 'downs', 'soloWinPercentage', 'deaths', 'teamKills', 'kdRatio', 'soloWins', 'killsMelee', 'revives', 'squadWinPercentage']
        validAllStats = ['saviorKills', 'scoreCombat', 'scoreAssault', 'wlPercentage', 'scoreGeneral', 'rank', 'scoreAward', 'headshots', 'shotsAccuracy', 'assistsAsKills', 'longestHeadshot', 'dogtagsTaken', 'draws', 'scoreDefensive', 'scoreSquad', 'avengerKills', 'losses', 'revivesRecieved', 'rounds', 'killStreak', 'deaths', 'damage', 'scoreLand', 'assists', 'scoreRecon', 'squadWipes', 'timePlayed', 'repairs', 'scoreAir', 'scoreSupport', 'heals', 'resupplies', 'scoreBonus', 'squadSpawns', 'damagePerMinute', 'rankScore', 'scoreRound', 'killsPerMinute', 'ordersCompleted', 'shotsHit', 'aceSquad', 'scorePerMinute', 'scoreTransports', 'shotsTaken', 'scoreObjective', 'scoreMedic', 'suppressionAssists', 'roundsPlayed', 'killsAggregated', 'kills', 'revives', 'scoreTanks', 'wins', 'kdRatio']
        validClassStats = ['deaths', 'kills', 'kdRatio', 'shotsFired', 'shotsHit', 'score', 'killsPerMinute', 'scorePerMinute', 'timePlayed', 'shotsAccuracy']

        if server.id not in self.settings:
            return
        if channel.id not in self.settings[server.id]['whitelist']:
            return

        if scope not in validScopes and scope != 'all':
            return await self.bot.say("`Supported stat scopes are 'all' or " + str(validScopes) + "`")

        if scope == 'all' and stat not in validAllStats:
            return await self.bot.say("`Supported stats are " + str(validAllStats) + "`")
        
        if scope in validScopes and scope not in ['all', 'firestorm'] and stat not in validClassStats:
            return await self.bot.say("`Supported class stats are " + str(validClassStats) + "`")

        if scope == 'firestorm' and stat not in validFirestormStats:
            return await self.bot.say("`Supported firestorm stats are " + str(validFirestormStats) + "`")

        await self.bot.send_typing(channel)

        try:
            #reload settings
            self.settings = dataIO.load_json(path + '/settings.json')

            bigW, bigH = bgImage.size
            d = ImageDraw.Draw(bgImage)
            #d.rectangle([(0, 0), bgImage.size], fill=50, outline=None, width=0)
            
            # Header text
            headerText = stat.lower() + ' leaders'
            if scope.lower() != 'all':
                headerText = scope.lower() + ' ' + headerText

            w, h = d.textsize(headerText, font=headerFont)
            d.text(((bigW - w) / 2, 10), headerText, font=headerFont, fill="rgb(255,255,255)")
            
            # background stuff
            lineY = 650
            labelY = 590
            d.line([(50, lineY), (bigW - 50, lineY)], fill="rgb(255,255,255)", width=5)
            d.text((50, labelY), 'Player', font=fnt, fill="rgb(255,255,255)")
            d.text((int(bigW / 2) + 90, labelY), 'Player', font=fnt, fill="rgb(255,255,255)")
            statLabel = stat.capitalize()
            w, h = d.textsize(statLabel, font=fnt)
            d.text((int((bigW / 2) - w - 50), labelY), statLabel, font=fnt, fill="rgb(255,255,255)")
            d.text((int(bigW - w - 50), labelY), statLabel, font=fnt, fill="rgb(255,255,255)")

            players = []
            for player in self.settings[server.id]['playerData']:
                players.append(await fetch_local_stats(self, ctx, player, scope, stat))

            sortedPlayers = sorted(players, key=lambda i: i['value'], reverse=True)

            #botMessage = "```css\n[EXM] " + scope.upper() + " " + stat.upper() + " LEADERS\n"
            count = 1

            playersPerColumn = math.ceil((len(sortedPlayers) - 3) / 2)
            if limit > 0 and limit < len(sortedPlayers):
              playersPerColumn = math.ceil((limit - 3) / 2)
            if playersPerColumn > 50:
              playersPerColumn = 50

            for player in sortedPlayers:
                value = ''
                if isinstance(player['value'], float):
                    value = '{0:.3g}'.format(player['value'])
                else:
                    value = '{:,}'.format(player['value'])

                #botMessage += str(count) + ". " + player['name'] + ": " + value + "\n"
                # avatar images
                if count < 4:
                    placedImage = await create_placed_image(self, ctx, player, scope, stat, count, value)
                    pX = 0
                    pY = 0
                    if count > 1:
                        placedImage = placedImage.resize((400, 400), Image.ANTIALIAS)
                        if count == 2:
                            pX = int((bigW / 2) - 400 - 250)
                            pY =  140
                        elif count == 3:
                            pX = int((bigW / 2) + 250)
                            pY = 140
                    else:
                        pX = int((bigW / 2) - 250)
                        pY = 90

                    pW, pH = placedImage.size
                    avatarCrop = placedImage.crop((0, 0, pW, pH))
                    bgImage.paste(avatarCrop, (pX, pY))
                else:
                    avatar = urllib.urlopen(player['avatarUrl'])
                    avatarImageFile = io.BytesIO(avatar.read())                
                    avatarImage = Image.open(avatarImageFile).convert('RGB').resize((50, 50), Image.ANTIALIAS)
                    avatarCrop = avatarImage.crop((0, 0, 50, 50))
                    textX = 110
                    textY = (450 + (count * 50))
                    if count > playersPerColumn + 3:
                        textX = int((bigW / 2) + 150)
                        textY = (450 + ((count - playersPerColumn) * 50))
                        
                    bgImage.paste(avatarCrop, (textX-55, textY+4))
                    # name and scores
                    d.text((textX, textY), str(count) + ". " + player['name'], font=fnt, fill="rgb(255,255,255)")
                    w, h = d.textsize(value, font=fnt)
                    valueX = int((bigW / 2) - w - 50)
                    if count > playersPerColumn + 3:
                        valueX = int(bigW - w - 50)

                    d.text((valueX, textY), value, font=fnt, fill="rgb(255,255,255)")

                count += 1

                if limit > 0 and count > limit:
                    break

            #botMessage += "```"
            #await self.bot.say(botMessage)

            with io.BytesIO() as out:
                cH = bigH
                croppedH = (700 + (playersPerColumn * 50))
                if croppedH < bigH:
                  cH = croppedH
                cropped = bgImage.crop((0, 0, bigW, cH))
                cropped.save(out, 'PNG')
                await self.bot.send_file(ctx.message.channel, io.BytesIO(out.getvalue()), filename='exmboard.png')

        except Exception as e:
            #await self.bot.say("error: " + e.message + " -- " + e.args)
            err = e.message

    def __unload(self):
        self.session.close()

    async def send_cmd_help(self, ctx):
        if ctx.invoked_subcommand:
            pages = self.bot.formatter.format_help_for(ctx, ctx.invoked_subcommand)
            for page in pages:
                await self.bot.send_message(ctx.message.channel, page)
        else:
            pages = self.bot.formatter.format_help_for(ctx, ctx.command)
            for page in pages:
                await self.bot.send_message(ctx.message.channel, page)

async def update_player_data():
    print('Path: ' + os.path.dirname(os.path.realpath(__file__)))
    subprocess.run([os.path.dirname(os.path.realpath(__file__)) + "/../cron.sh"])

async def create_placed_image(self, ctx, player, scope, stat, place, value):
    fillColor = "#b08d57" # bronze
    filename = 'bronze.png'
    if place == 2:
        fillColor = "#C0C0C0" # silver
        filename = 'silver.png'
    elif place == 1:
        fillColor = "#D4AF37" # gold
        filename = 'gold.png'
    #playerImage = Image.new('RGB', (500, 500), fillColor)
    playerImage = Image.open(path + '/' + filename).convert('RGB')
    avatar = urllib.urlopen(player['avatarUrl'])
    avatarImageFile = io.BytesIO(avatar.read())                
    avatarImage = Image.open(avatarImageFile).convert('RGB').resize((200, 200), Image.ANTIALIAS)
    avatarCrop = avatarImage.crop((0, 0, 200, 200))
    playerImage.paste(avatarCrop, (150, 75))
    d = ImageDraw.Draw(playerImage)
    placeString = str(place) + "st."
    if place == 2:
        placeString = str(place) + "nd."
    elif place == 3:
        placeString = str(place) + "rd."
    playerNameString = player['name']
    w, h = d.textsize(placeString, font=headerFont)
    d.text((int(250 - (w / 2)), 10), placeString, font=headerFont, fill="rgb(255,255,255)")
    w, h = d.textsize(playerNameString, font=fnt)
    d.text((int(250 - (w / 2)), 320), playerNameString, font=fnt, fill="rgb(255,255,255)")
    w, h=d.textsize(value, font=fnt)
    d.text((int(250 - (w / 2)), 400), value, font=fnt, fill="rgb(255,255,255)")

    return playerImage

async def fetch_local_stats(self, ctx, player, scope, stat):
    if scope == 'all':
        return {'name': player['data']['account']['playerNameNormalized'], 'avatarUrl': player['avatarUrl'], 'value': player['data']['stats'][stat]['value']}
    elif scope == 'firestorm':
        value = 0
        if player['data']['statsFirestorm'] and player['data']['statsFirestorm'][stat] and player['data']['statsFirestorm'][stat]['value']:
            value = player['data']['statsFirestorm'][stat]['value']

        return {'name': player['data']['account']['playerNameNormalized'], 'avatarUrl': player['avatarUrl'], 'value': value}
    else:
        classIndex = {
            'assault': 0,
            'medic': 1,
            'pilot': 2,
            'recon': 3,
            'support': 4,
            'tanker': 5
        }
        
        return {'name': player['data']['account']['playerNameNormalized'], 'avatarUrl': player['avatarUrl'], 'value': player['data']['classes'][classIndex[scope]][stat]['value']}
 

async def fetch_stats(self, ctx, playername, scope, stat):
    url = "https://api.battlefieldtracker.com/api/v1/bfv/profile/origin/" + playername.replace(" ", "%20")
    
    print("URL: " + url)

    async with aiohttp.get(url) as response:
        jsonObj = await response.json()
        #print("JSON: " + json.dumps(jsonObj));
        if scope == 'all':
            return {'name': playername, 'avatarUrl': jsonObj['avatarUrl'], 'value': jsonObj['data']['stats'][stat]['value']}
        elif scope == 'firestorm':
            return {'name': playername, 'avatarUrl': jsonObj['avatarUrl'], 'value': jsonObj['data']['statsFirestorm'][stat]['value']}
        else:
            classIndex = {
              'assault': 0,
              'medic': 1,
              'pilot': 2,
              'recon': 3,
              'support': 4,
              'tanker': 5
            }
            
            return {'name': playername, 'avatarUrl': jsonObj['avatarUrl'], 'value': jsonObj['data']['classes'][classIndex[scope]][stat]['value']}

def setup(bot):
    pathlib.Path(path).mkdir(exist_ok=True, parents=True)
    bot.add_cog(ExmBoard(bot))