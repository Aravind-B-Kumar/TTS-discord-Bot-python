import os
import discord
from discord.ext import commands,tasks

import sys, time, io, contextlib, textwrap, asyncio
from traceback import format_exception
from util import clean_code, paginator
from database import Database
import config
from loguru import logger
from typing import Optional, Literal

start_time = time.time()
logger.remove()
logger.add(sys.stdout,format="<yellow>[{time:YYYY-MM-DD HH:mm:ss}]</yellow> | <blue>{function}</blue> <cyan>{line}</cyan> --> <level>{message}</level>")

if sys.platform!='win32':
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except Exception as e:
        logger.error(e)

initial_extensions = (
    'cogs.help','cogs.tts'
)


intents = discord.Intents.default()
intents.members = True
#intents.presences = True
#intents.message_content = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("+"),
                   strip_after_prefix=True,
                   owner_ids=[758681854424514561, 844086740401520690],
                   case_insensitive=True,
                   intents=intents)

bot.db = Database()
bot.remove_command('help')

@tasks.loop(seconds=60)
async def statusbar():
    #await bot.change_presence(activity=discord.Activity(
    #    type=discord.ActivityType.listening,
    #    name=f"{len(bot.users)} members in {len(bot.guilds)} servers"))
    
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="you"))

    await asyncio.sleep(30)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="/say"))
    
    await asyncio.sleep(30)

    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening,
        name=f"{len(bot.guilds)} servers"))

    await asyncio.sleep(15)

@bot.event
async def on_ready():
    print( "Starting Bot...")
    statusbar.start()

    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
        except Exception as e:
            logger.error(e)
        
    await bot.load_extension('jishaku')

    #DATABASE
    await bot.db.execute("CREATE TABLE IF NOT EXISTS language (gid BIGINT PRIMARY KEY,langCode TEXT)") # set default language
    await bot.db.execute("CREATE TABLE IF NOT EXISTS channels (gid BIGINT PRIMARY KEY,channel BIGINT)") # set channel for talk
    await bot.db.execute("CREATE TABLE IF NOT EXISTS tfs (gid BIGINT PRIMARY KEY, mode INTEGER, vcid BIGINT)")

    await bot.db.execute("CREATE TABLE IF NOT EXISTS settings (gid BIGINT PRIMARY KEY, userMention INTEGER DEFAULT 0,ttsAudioFile INTEGER DEFAULT 0)")
    #await self.bot_db.execute("CREATE TABLE IF NOT EXISTS tfs (gid BIGINT PRIMARY KEY,vcid BIGINT)")
    
    print("Startup Complete")

@bot.command(name='restart',hidden=True)
@commands.is_owner()
async def restart(ctx):
    await ctx.message.add_reaction('<a:tick:911542278781276190>')
    os.system("clear")
    os.execv(sys.executable, ['python'] + sys.argv)

@bot.command(name='load',hidden=True)
@commands.is_owner()
async def load(ctx, extension):
    try:
        await bot.load_extension(f'cogs.{extension}')
        await ctx.message.add_reaction('<a:tick:911542278781276190>')
    except Exception as e:
        await ctx.send(f'```py\n{e}```')

@bot.command(name='unload',hidden=True)
@commands.is_owner()
async def unload(ctx, extension):
    try:
        await bot.unload_extension(f'cogs.{extension}')
        await ctx.message.add_reaction('<a:tick:911542278781276190>')
    except Exception as e:
        await ctx.send(f'```py\n{e}```')

@bot.command(name='reload',hidden=True)
@commands.is_owner()
async def reload(ctx, extension):
    try:
        await bot.reload_extension(f'cogs.{extension}')
        await ctx.message.add_reaction('<a:tick:911542278781276190>')
    except Exception as e:
        await ctx.send(f'```py\n{e}```')

bot.remove_command('ping')


@bot.command('ping',description='Shows latency of bot')
async def ping(ctx):
    current_time = time.time()
    duration = int(round(current_time - start_time))
    if duration > 0:
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{}d'.format(days))
        if hours > 0:
            duration.append('{}h'.format(hours))
        if minutes > 0:
            duration.append('{}m'.format(minutes))
        if seconds > 0:
            duration.append('{}s'.format(seconds))

        value = ' '.join(duration)

    embed = discord.Embed(color=discord.Color.random())
    embed.add_field(
        name="Ping",
        value=":ping_pong: | <@" + str(ctx.author.id) +
        f"> ```elixir\nPong: {round((bot.latency)*1000)}ms \nUptime: {value}```",
        inline=True)
    embed.set_thumbnail(url='https://images-ext-2.discordapp.net/external/R9FD4LtWkz0Tstc6_GN0bp8A-6i5BCtQHsxbhjBeAt4/https/cdn.jeyy.xyz/image/pingpong_8f881f.gif')
    await ctx.send(embed=embed)


@bot.tree.command(name='ping',description="Show the latency of the bot")
async def ping_slash(interaction: discord.Interaction):
    current_time = time.time()
    duration = int(round(current_time - start_time))
    if duration > 0:
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        duration = []
        if days > 0:
            duration.append('{}d'.format(days))
        if hours > 0:
            duration.append('{}h'.format(hours))
        if minutes > 0:
            duration.append('{}m'.format(minutes))
        if seconds > 0:
            duration.append('{}s'.format(seconds))

        value = ' '.join(duration)

    embed = discord.Embed(color=discord.Color.random())
    embed.add_field(
        name="Ping",
        value=":ping_pong: | <@" + str(interaction.user.id) +
        f"> ```elixir\nPong: {round((bot.latency)*1000)}ms \nUptime: {value}```",
        inline=True)
    embed.set_thumbnail(url='https://images-ext-2.discordapp.net/external/R9FD4LtWkz0Tstc6_GN0bp8A-6i5BCtQHsxbhjBeAt4/https/cdn.jeyy.xyz/image/pingpong_8f881f.gif')
    await interaction.response.send_message(embed=embed)
#========================================================================================
@bot.command(name="e", aliases=["eval", 'aval'],description='Evalue code. Only for owner',hidden=True)
@commands.is_owner()
async def _eval(ctx, *, code):
    if code.startswith("```") and code.endswith("```"):
        code = clean_code(code)
        local_variables = {
            "discord": discord,
            "commands": commands,
            "bot": bot,
            "ctx": ctx,
            "channel": ctx.channel,
            "author": ctx.author,
            "guild": ctx.guild,
            "message": ctx.message
        }

        stdout = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout):
                exec(
                    f"async def func():\n{textwrap.indent(code, '    ')}",
                    local_variables,
                )

                obj = await local_variables["func"]()
                result = f"{stdout.getvalue()}"
        except Exception as e:
            result = "".join(format_exception(e, e, e.__traceback__))

        pager = paginator(
            timeout=100,
            entries=[result[i:i + 2000] for i in range(0, len(result), 2000)],
            length=1,
            prefix="```py\n",
            suffix="```")
        try:await pager.start(ctx)
        except:pass

    else:
        try:
            await ctx.send(embed=discord.Embed(description=eval(code),
                                               color=discord.Color.random()))
        except Exception as e:
            await ctx.send(e)

# SLASH

class eval_class(discord.ui.Modal,title='Evaluate'):
    code = discord.ui.TextInput(
        label='Code',
        style=discord.TextStyle.paragraph,
        placeholder='input code here',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)        
        code = '```py\n'+self.code.value+'\n```'
        code = clean_code(code)
        local_variables = {
            "discord": discord,
            "commands": commands,
            "bot": bot,
            "interaction": interaction,
            "channel": interaction.channel,
            "user": interaction.user,
            "guild": interaction.guild,
            "message": interaction.message
        }

        stdout = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout):
                exec(
                    f"async def func():\n{textwrap.indent(code, '    ')}",
                    local_variables,
                )

                obj = await local_variables["func"]()
                result = f"{stdout.getvalue()}"
        except Exception as e:
            result = "".join(format_exception(e, e, e.__traceback__))

        pager = paginator(
            colour=0xff1493, 
            embed=True,
            timeout=100,
            entries=[result[i:i + 2000] for i in range(0, len(result), 2000)],
            length=1,
            prefix="```py\n",
            suffix="```")
        await pager.start_slash(interaction)

@bot.tree.command(name='eval',description="Evaluate code.Only for owner")
async def eval_slash(interaction: discord.Interaction):
    if interaction.user.id in bot.owner_ids:
        await interaction.response.send_modal(eval_class())
    else:
        await interaction.response.defer(ephemeral=True)

@bot.tree.command(name='support',description="Need any help? Reach out to our support server")
async def eval_slash(interaction: discord.Interaction):
    await interaction.response.send_message(embed=discord.Embed(title='Support',description=f'Experiencing any issue? Join our support server by clicking [here](https://discord.gg/FDhd5CXTmJ)',color=discord.Color.random()))

class SlashUseChey(commands.CommandError):pass

@bot.before_invoke
async def use_slash(ctx):
    if not ctx.author.id in bot.owner_ids:
        return 

@bot.command('info',hidden=True)
@commands.is_owner()
async def info(ctx):
    glds= vc = len(bot.guilds)
    vc = len(bot.voice_clients)
    pl = 0
    for i in bot.voice_clients:
        if i.is_playing():
            pl+=1
    mem = len(bot.users)
    await ctx.send(embed=discord.Embed(title='Info',description=f'> vcs: {vc} \n> playing: {pl} \n> guilds: {glds} \n> members: {mem}',color=discord.Color.random()))


@bot.tree.command(name='clear-data',description="Clear any data related to server(if any)")
async def clear_data(interaction:discord.Interaction):
    await bot.db.execute("DELETE FROM language WHERE gid=?",interaction.guild_id)    
    await bot.db.execute("DELETE FROM channels WHERE gid=?",interaction.guild_id)
    await bot.db.execute("DELETE FROM tfs WHERE gid=?",interaction.guild_id)
    await bot.db.execute("DELETE FROM settings WHERE gid=?",interaction.guild_id)
    await interaction.response.send_message("Any data (if stored) of this server has been deleted.")


@bot.command()
@commands.guild_only()
@commands.is_owner()
async def sync(
  ctx: commands.Context, guilds: commands.Greedy[discord.Object], spec: Optional[Literal["~", "*", "^"]] = None
  ) -> None:
    if not guilds:
        if spec == "~":
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "*":
            ctx.bot.tree.copy_global_to(guild=ctx.guild)
            synced = await ctx.bot.tree.sync(guild=ctx.guild)
        elif spec == "^":
            ctx.bot.tree.clear_commands(guild=ctx.guild)
            await ctx.bot.tree.sync(guild=ctx.guild)
            synced = []
        else:
            synced = await ctx.bot.tree.sync()

        await ctx.send(
            f"Synced {len(synced)} commands {'globally' if spec is None else 'to the current guild.'}"
        )
        return
    ret = 0
    for guild in guilds:
        try:
            await ctx.bot.tree.sync(guild=guild)
        except discord.HTTPException:
            pass
        else:
            ret += 1
    await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")



async def starter():
    await bot.start(config.TOKEN,reconnect=True)

asyncio.run(starter())

