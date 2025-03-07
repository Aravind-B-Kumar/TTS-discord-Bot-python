
import asyncio
import config
import re
import shlex
import subprocess
import sys

from database import Database
from discord import app_commands, utils, Interaction, Embed, Emoji, VoiceClient, Message, AudioSource, ClientException, VoiceProtocol, TextChannel, VoiceChannel, SelectOption, ButtonStyle, File, FFmpegPCMAudio, Guild, Attachment
from discord.ext.commands import Bot, Cog
from discord.opus import Encoder
from discord.ui import Select, View, button, Button
from enum import Enum
from gtts import gTTS
from gtts.lang import tts_langs
from io import BytesIO
from loguru import logger
from typing import List,Union
from discord.ext import commands

URL_REGEX = r"(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})"

logger.remove()
logger.add(sys.stdout,format="<yellow>[{time:YYYY-MM-DD HH:mm:ss}]</yellow> | <blue>{function}</blue> <cyan>{line}</cyan> --> <level>{message}</level>")

def postman(interaction:Interaction):
    return interaction.followup.send if interaction.response.is_done() else interaction.response.send_message

async def Languages_Autocomplete(interaction: Interaction,current: str,) -> List[app_commands.Choice[str]]:
    return [ app_commands.Choice(name=lang[1],value=lang[0]) for lang in tts_langs().items() if current.lower() in lang[1].lower()][:25]

allLanguages = tts_langs()
#Language_Codes:list = [lang[0] for lang in tts_langs().items()]

class settingsItems(Enum):
    userMention:str = "@User Mention"
    ttsAudioFile:str= "TTS Audio Files"

class CustomFFmpegPCMAudio(FFmpegPCMAudio):
    def __init__(self,url:str,*args,**kwargs) -> None:
        self._position:float = 0
        self._rate:float = 1
        self._url = url
        super().__init__(url,*args,**kwargs)
    
    def read(self) -> bytes:
        self._position += 0.02 * self._rate
        return super().read()
    
    @property
    def url(self)->str:
        return self._url

    @property
    def position(self)->float:
        return self._position

    @property
    def rate(self)->float:
        return self._rate

    @rate.setter
    def rate(self,rate:float):
        self._rate = rate

class FFmpegPCMAudioGTTS(AudioSource):
    def __init__(self, source, *, executable='ffmpeg', pipe=False, stderr=None, before_options=None, options=None):
        stdin = None if not pipe else source
        args = [executable]
        if isinstance(before_options, str):
            args.extend(shlex.split(before_options))
        args.append('-i')
        args.append('-' if pipe else source)
        args.extend(('-f', 's16le', '-ar', '48000', '-ac', '2', '-loglevel', 'warning'))
        if isinstance(options, str):
            args.extend(shlex.split(options))
        args.append('pipe:1')
        self._process = None
        try:
            self._process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr)
            self._stdout = BytesIO(
                self._process.communicate(input=stdin)[0]
            )
        except FileNotFoundError:
            raise ClientException(executable + ' was not found.') from None
        except subprocess.SubprocessError as exc:
            raise ClientException('Popen failed: {0.__class__.__name__}: {0}'.format(exc)) from exc
    def read(self):
        ret = self._stdout.read(Encoder.FRAME_SIZE)
        if len(ret) != Encoder.FRAME_SIZE:
            return b''
        return ret
    def cleanup(self):
        proc = self._process
        if proc is None:
            return
        proc.kill()
        if proc.poll() is None:
            proc.communicate()
        self._process = None

async def initial_connection(interaction:Interaction,danger:Emoji,success:Emoji, checking=False)->bool:
    sender = postman(interaction)
    if interaction.user.voice is None:
        await sender(embed=Embed(description=f'{danger} | Please join a voice channel',color=config.COLOR_DANGER),ephemeral=True)
        return False

    if not interaction.guild.voice_client:
        vc:VoiceProtocol = await interaction.user.voice.channel.connect(reconnect=True,self_deaf=True)
        #await interaction.guild.change_voice_state(channel=vc.channel,self_deaf=True)
        await sender(embed=Embed(description=f"{success} | Successfully connected to {vc.channel.mention}",color=config.COLOR_SUCCESS))
        return True

    else:
        if interaction.user.voice.channel.id !=interaction.guild.voice_client.channel.id:
            if all([x.bot for x in interaction.guild.voice_client.channel.members]):
                interaction.guild.voice_client.disconnect(force=True)
                await interaction.guild.change_voice_state(channel=interaction.user.voice.channel,self_deaf=True)
                await sender(embed=Embed(description=f"{success} | Successfully moved to {interaction.user.voice.channel.mention}",color=config.COLOR_SUCCESS))
                return True
            else:
                await sender(embed=Embed(description=f'{danger} | You are connected to a different voice channel!',color=config.COLOR_DANGER),ephemeral=True)
                return False
        else:
            if not checking:
                await sender(embed=Embed(description=f'{danger} | Already connected to a voice channel!',color=config.COLOR_DANGER),ephemeral=True)
            return True

async def runtime_connection(interaction:Interaction,danger:Emoji,success:Emoji)-> bool:
    sender = postman(interaction)
    if interaction.user.voice is None:
        await sender(embed=Embed(description=f"{danger} | Please join a voice channel",color=config.COLOR_DANGER),ephemeral=True)
        return False

    if not interaction.guild.voice_client:
        await sender(embed=Embed(description=f'{danger} | Not connected to any voice channel',color=config.COLOR_DANGER),ephemeral=True)
        return False

    if interaction.user.voice.channel.id !=interaction.guild.voice_client.channel.id:
        await sender(embed=Embed(description=f'{danger} | You are connected to a different voice channel!',color=config.COLOR_DANGER),ephemeral=True)
        return False
    
    return True


#async def has_permissions(interaction:Interaction)->bool:
#    perms = interaction.channel.permissions_for(interaction.guild.me) 
#    missing_perms:list = []
#    if not perms.connect:
#       missing_perms.append("`Connect`")
#    if not perms.speak:
#        missing_perms.append("`Speak`")
#    if missing_perms:
#        await interaction.response.send_message(embed=Embed(description=f"I don\'t have the required permissions - `{','.join(missing_perms)}`"))
#        return False
#    return True

def get_lang(language:str):
    for code,lang in tts_langs().items():
        if lang == language.capitalize():
            return code
    return None

class TTS(Cog):
    def __init__(self,bot:Bot) -> None:
        self.bot:Bot = bot
        self.bot_db:Database = bot.db        

        self.green_tick= "✅"
        self.red_check = "❌"

        self.messageQueue = asyncio.Queue(maxsize=5)

        #task = bot.loop.create_task(self.get_set_channels())
        self.filter_channels:list = []
        self.cd_mapping = commands.CooldownMapping.from_cooldown(1, 5, commands.BucketType.member) # on message coldown 

        bot.tree.add_command(app_commands.ContextMenu(name="Play attachments", callback=self.play_audio_from_file))
        
        bot.loop.create_task(config.tfs_connections(bot))
        bot.loop.create_task(self.speak_Messages())

    async def play_audio_from_file(self, interaction: Interaction, message:Message):
        if not await initial_connection(interaction,self.red_check,self.green_tick):
            return
        sender = postman(interaction)
        if isinstance(message,Message):
            if message.attachments==[]:
                match = re.search(URL_REGEX, message.content)
                if match is None:
                    return await sender("Couldn\'t find any suitable url!",ephemeral=True)
                else:
                    url = match.group(0)
            else:
                url:str = message.attachments[0].url 
        else:
            url:str = message
        
        vc:VoiceClient = interaction.guild.voice_client

        if not vc.is_playing():
            try:
                vc.play( CustomFFmpegPCMAudio(url), after=vc.stop())
                await sender("Done")                
            except:
                await sender(embed=Embed(description=f"{self.red_check} | An error occured!",color=config.COLOR_DANGER))
        else:
            await sender(embed=Embed(description=f"{self.red_check} | Currently playing another audio",color=config.COLOR_DANGER),ephemeral=True)

    def empty_queue(self)->None:
        def end_task(q:asyncio.Queue):
            while not q.empty():
                q.get_nowait()
                q.task_done()

        q1 = self.messageQueue
        end_task(q1)


    async def get_set_channels(self)->list:
        return [i[0] for i in await self.bot_db.fetchall("SELECT channel FROM channels")]

    async def get_langCode_from_db(self,gid:int)->Union[str,None]:
        return await self.bot_db.fetchone("SELECT langCode FROM language WHERE gid=?",gid) or "en"

    async def source_from_text(self, text:str,language:str)->BytesIO:
        sound = gTTS(text=text, lang=language, slow=True) 
        sound_fp = BytesIO()
        sound.write_to_fp(sound_fp)
        sound_fp.seek(0)
        return sound_fp

#----------------------------------------------------------------------------------------------------------------

    class FilterDropdown(Select):
        def __init__(self,userId:int,vc:VoiceClient):
            options:list = [SelectOption(label= name, description=f"Apply {name.capitalize()} filter" ) for name in config.filters]
            self.userId:int = userId
            self.vc:VoiceClient = vc
            super().__init__(placeholder='Choose filter', min_values=1, max_values=3, options=options)

        async def callback(self, interaction: Interaction):
            if interaction.user.id != self.userId:
                return await interaction.response.send_message("This is not for you", ephemeral=True)

            if not isinstance(interaction.guild.voice_client.source, CustomFFmpegPCMAudio):
                return await interaction.response.send_message(embed=Embed(description=f"Filter is only supported for attachments.",color=config.COLOR_DANGER),ephemeral=True)

            if not self.vc.is_playing():
                return await interaction.response.send_message("Currently not playing audio", ephemeral=True)
            
            filtersV = "".join([config.filters[i] for i in self.values]) 
            source:CustomFFmpegPCMAudio = self.vc.source
            url:str = source.url

            base = "atempo=1"
            ffmpeg_options = {
                "before_options": config.FFMPEG_BASE_OPTION + f" -ss {source.position}",
                "options": f'-vn -af:a "{base+filtersV}"',
            }
            try:
                self.vc.stop()
                self.vc.play(CustomFFmpegPCMAudio(url,**ffmpeg_options)) 
                await interaction.response.send_message("Filter has been applied.",ephemeral=True) 
            except Exception as e:
                print(e)
                await interaction.response.send_message("An error occured",ephemeral=True)



    @app_commands.command(name="filters",description='Add filters to playing attachments')
    async def set_filter_(self, interaction: Interaction) -> None:
        if not await runtime_connection(interaction,self.red_check,self.green_tick):
           return
        sender = postman(interaction)
        vc:VoiceProtocol = interaction.guild.voice_client
        if not isinstance(vc.source, CustomFFmpegPCMAudio):
           return await sender(embed=Embed(description=f"{self.red_check} | Filter is only supported for attachments.",color=config.COLOR_RANDOM),ephemeral=True)

        if vc is None:return await sender(embed=Embed(description=f"{self.red_check} | Couldn\'t find any voice channels.Use </join:1080033055659544625>"))

        view = View()
        view.add_item( self.FilterDropdown(interaction.user.id,vc))
        await sender("Appy filter ....",view=view)



#----------------------------------------------------------------------------------------------------------------

    @app_commands.command(name="play",description='Play attachments/files via ints url. Also available in context menu')
    @app_commands.describe(attachment="File to be played.")
    async def play_attachment_(self, interaction: Interaction,attachment:Attachment) -> None:
        
        await self.play_audio_from_file(interaction,attachment.url)

    @app_commands.command(name="tts-audio",description='Send tts audio file')
    @app_commands.describe(text="text",language="Select language")
    @app_commands.autocomplete(language = Languages_Autocomplete)
    async def tts_audio_(self, interaction: Interaction,text:str,language:str) -> None:
        await interaction.response.defer(thinking=True)
        sound_fp :BytesIO = await self.source_from_text(text[:400],language)
        await postman(interaction)(file=File(fp=sound_fp, filename="message.mp3" )) 


    @app_commands.command(name="say",description='Speaks a text')
    @app_commands.describe(text="text",language="Select language")
    @app_commands.autocomplete(language = Languages_Autocomplete)
    async def say_slash(self, interaction: Interaction,text:str,language:str=None) -> None:
        if not await initial_connection(interaction,self.red_check,self.green_tick,checking=True):
            return 
        
        vc: VoiceClient = interaction.guild.voice_client
        sender = postman(interaction)

        if vc.is_playing():
            return await sender(embed=Embed(description=f"{self.red_check} | Currently playing another text! Your text\n `{text}`",color=config.COLOR_DANGER),ephemeral=True)

        language:str = language or await self.get_langCode_from_db(interaction.guild_id)

        q1 = f"SELECT {settingsItems.userMention.name} FROM settings WHERE gid={interaction.guild_id}"
        q2 = f"SELECT {settingsItems.ttsAudioFile.name} FROM settings WHERE gid={interaction.guild_id}"
        
        mention = await self.bot_db.fetchone(q1) if await self.bot_db.fetchone("SELECT EXISTS(SELECT * FROM settings WHERE gid=?)",interaction.guild_id) else 0
        ttsFile = await self.bot_db.fetchone(q2) if await self.bot_db.fetchone("SELECT EXISTS(SELECT * FROM settings WHERE gid=?)",interaction.guild_id) else 0

        if text is None:return
        speakText:str = f"{interaction.user.display_name} said {text[:300]}" if mention else text[:300]
        sound_fp :BytesIO = await self.source_from_text(speakText,language)

        try:
            vc.play(FFmpegPCMAudioGTTS(sound_fp.read(), pipe=True))
            sound_fp.seek(0)
            return await sender(content="Done") if not ttsFile else await sender(file=File(fp=sound_fp, filename="message.mp3" ))  #embed=Embed(description="Text has been played"),ephemeral=True
        except Exception as e:
            logger.error(e)
            return await sender(embed=Embed(description=f"{self.red_check} |  An unexpected error occured!",color=config.COLOR_DANGER),ephemeral=True)


    @app_commands.command(name="pause",description="Pause currently playing audio")
    async def pause_(self,interaction:Interaction)->None:
        if not await runtime_connection(interaction,self.red_check,self.green_tick):
            return
        vc:VoiceClient = interaction.guild.voice_client
        sender = postman(interaction)
        if vc.is_playing():
            vc.pause()
            return await sender(embed=Embed(description=f"{self.green_tick} | Audio paused!",color=config.COLOR_SUCCESS))
        else:
            return await sender(embed=Embed(description=f"{self.red_check} | Nothing playing at the moment!",color=config.COLOR_DANGER),ephemeral=True)

    @app_commands.command(name="resume",description="Resume audio")
    async def resume_(self,interaction:Interaction)->None:
        if not await runtime_connection(interaction,self.red_check,self.green_tick):
            return
        vc:VoiceClient = interaction.guild.voice_client
        sender = postman(interaction)
        if vc.is_paused():
            vc.resume()
            return await sender(embed=Embed(description=f"{self.green_tick} | Audio resumed!",color=config.COLOR_SUCCESS))
        else:
            return await sender(embed=Embed(description=f"{self.red_check} | Nothing to resume",color=config.COLOR_SUCCESS),ephemeral=True)

    @app_commands.command(name="stop",description="Stop currently playing audio")
    async def stop_(self,interaction:Interaction)->None:
        if not await runtime_connection(interaction,self.red_check,self.green_tick):
            return
        vc:VoiceClient = interaction.guild.voice_client
        sender = postman(interaction)
        if vc.is_playing():
            self.empty_queue()
            vc.stop()
            return await sender(embed=Embed(description=f"{self.green_tick} | Stopped!",color=config.COLOR_SUCCESS))
        else:
            return await sender(embed=Embed(description=f"{self.red_check} | Nothing playing at the moment!",color=config.COLOR_SUCCESS),ephemeral=True)

    @app_commands.command(name="disconnect",description="Disconnect bot from voice channel")
    async def disconnect_(self,interaction:Interaction):
        if not await runtime_connection(interaction,self.red_check,self.green_tick):
           return
        vc:VoiceClient = interaction.guild.voice_client
        try:
            await vc.disconnect(force=True)
            await interaction.response.send_message(embed=Embed(description=f"{self.green_tick} | Disconnected Successfully",color=config.COLOR_SUCCESS))
        except Exception as e:
            logger.error(e)
            await interaction.response.send_message(embed=Embed(description=f"{self.red_check} | An error occured!",color=config.COLOR_DANGER))

    @app_commands.command(name="join",description="Joins a voice channel")
    async def join_(self,interaction:Interaction):
        #if not await has_permissions(interaction):
        #    return 
        await initial_connection(interaction,self.red_check,self.green_tick)
        

    @app_commands.command(name="default-language",description="Set a default language")
    @app_commands.describe(language="Select default language")
    @app_commands.autocomplete(language = Languages_Autocomplete)
    async def default_channel_(self,interaction:Interaction,language:str)->None:
        if await self.bot_db.fetchone("SELECT EXISTS(SELECT langCode FROM language WHERE gid=?)",interaction.guild_id):
            await self.bot_db.execute("UPDATE language SET langCode=? WHERE gid=?",language,interaction.guild_id)
        else:
            await self.bot_db.execute("INSERT INTO language values(?,?)",interaction.guild_id,language)
        return await interaction.response.send_message(embed=Embed(description=f"{self.green_tick} | Default language set to `{allLanguages[language]}`",color=config.COLOR_SUCCESS))

    @app_commands.command(name="set-channel",description="Set a channel for me to let me read out all message from that channel")
    @app_commands.describe(channel = "Channel to be set")
    async def set_channel_(self,interaction:Interaction,channel:TextChannel):
        #return await interaction.response.send_message("This command is currently disabled as the bot is requesting for required intents",ephemeral=True)
        if await self.bot_db.fetchone("SELECT EXISTS(SELECT channel FROM channels WHERE gid=?)",interaction.guild_id):
            await self.bot_db.execute("UPDATE channels SET channel=? WHERE gid=?",channel.id,interaction.guild_id)
        else:
            await self.bot_db.execute("INSERT INTO channels values(?,?)",interaction.guild_id,channel.id)
        
        self.filter_channels = await self.get_set_channels()
        return await interaction.response.send_message(embed=Embed(description=f"{self.green_tick} | Channel {channel.mention} set successfully",color=config.COLOR_SUCCESS))

    @app_commands.command(name='247',description='Toggle 24/7 mode for your server')
    @app_commands.describe(channel="Set a voice channel",mode="Enable or Disable 247")
    @app_commands.choices(mode=[
        app_commands.Choice(name='Disable', value=0),
        app_commands.Choice(name='Enable', value=1)               
    ])      
    async def tfs_(self,interaction:Interaction,mode:app_commands.Choice[int],channel:VoiceChannel=None):
        #if await self.bot_db.fetchone("SELECT EXISTS(SELECT vcid FROM tfs WHERE gid=?)",interaction.guild_id):
        #    await self.bot_db.execute("UPDATE tfs SET vcid=? WHERE gid=?",channel.id,interaction.guild_id)
        #else:
        #    await self.bot_db.execute("INSERT INTO tfs values(?,?)",interaction.guild_id,channel.id)
        #
        #return await interaction.response.send_message(embed=Embed(description=f"{self.green_tick} | Channel {channel.mention} set successfully",color=config.COLOR_SUCCESS))
        await interaction.response.defer(thinking=True)
        vc = interaction.guild.voice_client
        exists = await self.bot_db.fetchone("SELECT EXISTS(SELECT * FROM tfs WHERE gid=?)",interaction.guild_id)
        if mode.value == 0: #DISABLE
            if exists:
                await self.bot_db.execute("UPDATE tfs SET mode=? WHERE gid=?",mode.value,interaction.guild_id)
                return await interaction.followup.send(embed=Embed(description=f"{self.green_tick} | 24/7 mode has been `Disabled`",color=config.COLOR_SUCCESS))
            else:
                return await interaction.followup.send(embed=Embed(description=f"{self.red_check} | 24/7 mode was already `Disabled`",color=config.COLOR_DANGER))
        else: # ENABLE
            #if await self.bot_db.fetchone("SELECT vcid FROM tfs WHERE gid=?",interaction.guild_id) is None and channel is None:
            #    return await interaction.followup.send(embed=Embed(description=f"{self.red_check} | Please select a Voice channel!",color=config.COLOR_DANGER))
            if not exists:
                if channel is not None: 
                    await self.bot_db.execute("INSERT INTO tfs VALUES(?,?,?)",interaction.guild_id,mode.value,channel.id)
                    await channel.connect(self_deaf=True,reconnect=True)
                    return await interaction.followup.send(embed=Embed(description=f"{self.green_tick} | 24/7 has been `Enabled` - {channel.mention}",color=config.COLOR_SUCCESS))
                else:
                    return await interaction.followup.send(embed=Embed(description=f"{self.red_check} | Please select a Voice channel!",color=config.COLOR_DANGER))

            # DATA EXISTS
            if channel is not None:
                await self.bot_db.execute("UPDATE tfs SET mode=?,vcid=? WHERE gid=?",mode.value,channel.id,interaction.guild_id) 
                if vc is not None:
                    if vc.channel.id != channel.id:
                        await vc.disconnect(force=True)
                        channel.connect(self_deaf=True,reconnect=True)
                return await interaction.followup.send(embed=Embed(description=f"{self.green_tick} | 24/7 mode has been `Enabled` - {channel.mention}",color=config.COLOR_SUCCESS))
            else: #channel is None
                vcid = await self.bot_db.fetchone("SELECT vcid FROM tfs WHERE gid=?",interaction.guild_id) 
                if vcid is None:
                    return await interaction.followup.send(embed=Embed(description=f"{self.red_check} | Please select a Voice channel!",color=config.COLOR_DANGER))
                else:
                    await self.bot_db.execute("UPDATE tfs SET mode=? WHERE gid=?",mode.value,interaction.guild_id)
                    return await interaction.followup.send(embed=Embed(description=f"{self.green_tick} | 24/7 mode has been `Enabled` - <#{vcid}>",color=config.COLOR_SUCCESS))

#--------------------------------------------------------------------------------------------------------------
    class settingsButton(View):
        def __init__(self,db:Database, item:str, user,initial_value:int):
            super().__init__(timeout=None)
            self.db:Database = db
            self.item:str = item
            self.user = user
            self.initial_value = initial_value
            self.setup_()

        def setup_(self):
            if self.initial_value == 0: # 0 -> disabled
                self.enable_button.disabled = False
                self.disable_button.disabled = True
            else: # 1 -> enabled
                self.enable_button.disabled = True
                self.disable_button.disabled = False

        async def interaction_check(self, interaction: Interaction) -> bool:
            if interaction.user.id != self.user.id:
                await interaction.response.send_message(embed=Embed(description=f'This is only for {self.user.mention}'),ephemeral=True)
                return False
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(embed=Embed(description=f'You do not have required permissions!'),ephemeral=True)
                return False
            return True

        @button(label="Disable",style=ButtonStyle.red,custom_id="0")
        async def disable_button(self,interaction:Interaction,button:Button):
            if await self.db.fetchone("SELECT EXISTS(SELECT * FROM settings WHERE gid=?)",interaction.guild_id):
                q = f"UPDATE settings SET {self.item} = 0 WHERE gid = {interaction.guild_id}"
                await self.db.execute(q) 
            else:
                q = f"INSERT INTO settings(gid,{self.item}) VALUES({interaction.guild_id},0)"
                await self.db.execute(q)
            button.disabled = True
            self.enable_button.disabled = False
            await interaction.response.edit_message(view=self)
            
        @button(label="Enable",style=ButtonStyle.green,custom_id="1")
        async def enable_button(self,interaction:Interaction,button:Button):
            if await self.db.fetchone("SELECT EXISTS(SELECT * FROM settings WHERE gid=?)",interaction.guild_id):
                q = f"UPDATE settings SET {self.item} = 1 WHERE gid = {interaction.guild_id}"
                await self.db.execute(q) 
            else:
                q = f"INSERT INTO settings(gid,{self.item}) VALUES({interaction.guild_id},1)"
                await self.db.execute(q) 
            button.disabled = True
            self.disable_button.disabled = False
            await interaction.response.edit_message(view=self)


    class settingsDropdown(Select):
        def __init__(self,options, Embedoption,item:str,user,buttons,db:Database):
            super().__init__(placeholder='Choose setting', min_values=1, max_values=1, options=options)
            self.Embedoption = Embedoption
            self.item:settingsItems = item
            self.user = user
            self.buttons = buttons
            self.db=db
        
        async def callback(self, interaction: Interaction):
            value = int(self.values[0])
            q = f"SELECT {tuple(settingsItems)[value].name} FROM settings WHERE gid={interaction.guild_id}"
            initial_value = await self.db.fetchone(q) if await self.db.fetchone("SELECT EXISTS(SELECT * FROM settings WHERE gid=?)",interaction.guild_id) else 0            

            view :View= self.buttons(self.db,tuple(settingsItems)[value].name,interaction.user,initial_value)
            view.add_item(self)
            await interaction.response.edit_message(embed=self.Embedoption[value],view=view)



    #TODO
    # @user said option
    # send audio file to channel
    # queue limit
    # role
    #settings

    @app_commands.command(name="settings",description="Settings of your server")
    async def settings_(self,interaction:Interaction):
        options:list[tuple] =[
            # label , value , description , emoji , default
            (settingsItems.userMention.value , 0, None,"<:mention:1076170717973975075>"),
            (settingsItems.ttsAudioFile.value, 1, None,"<:audioFile:1076171005711614133>")
            #("role", 3, None)
        ]

        Embedoption:list[Embed] = [
            Embed(title=settingsItems.userMention.value ,description="Whether name of the user must be mention while speaking text",color=config.COLOR_DARKTHEME),
            Embed(title=settingsItems.ttsAudioFile.value,description="Whether TTS audio files must be sent to channel(for </say:1080033055659544620>)",color=config.COLOR_DARKTHEME)
        ]
        soptions:list = [SelectOption(label=i[0], value= i[1], description=i[2] , emoji=i[3]) for i in options]

        q = f"SELECT {settingsItems.userMention.name} FROM settings WHERE gid={interaction.guild_id}"
        initial_value = await self.bot_db.fetchone(q) if await self.bot_db.fetchone("SELECT EXISTS(SELECT * FROM settings WHERE gid=?)",interaction.guild_id) else 0

        view = self.settingsButton(self.bot_db,settingsItems.userMention.name,interaction.user, initial_value)
        view.add_item(self.settingsDropdown(soptions,Embedoption,settingsItems,interaction.user,self.settingsButton,self.bot_db))
        #view.add_item(config.settingsButton(self.bot_db,settingsItems.userMention.name,interaction.user));print(390)
        #view.add_item(config.settingsButton(interaction.user));print(390)
        await interaction.response.send_message(embed=Embedoption[0],view=view) 

#--------------------------------------------------------------------------------------------------------------
    
    def is_tts_message(self,message:Message):
        if not message.channel.id in self.filter_channels:
            return False
        if message.guild.voice_client is None: 
            return False
        text:str = message.content.replace("\n", "").replace("\r", "")
        if text is None:return False
        if len(text)>0 and not text.isspace() :
            return True
        return True

    async def speak_Messages(self): #NOTE only work with intents.all()
        while True:
            if not self.messageQueue.empty():
                message:Message = self.messageQueue.get_nowait()
            else:
                await asyncio.sleep(0.5)
                continue
            
            vc:VoiceClient = message.guild.voice_client
            if vc.is_playing() or vc.is_paused():
                await asyncio.sleep(0.5)
                continue

            language:str = await self.get_langCode_from_db(message.guild.id)
            q1 = f"SELECT {settingsItems.userMention.name} FROM settings WHERE gid={message.guild.id}"
            mention = await self.bot_db.fetchone(q1) if await self.bot_db.fetchone("SELECT EXISTS(SELECT * FROM settings WHERE gid=?)",message.guild.id) else 0
            speakText:str = f"{message.author.display_name} said {message.content[:300]}" if mention else message.content[:300]

            sound_fp :BytesIO = await self.source_from_text(text=speakText,language=language)

            try:
                if not vc.is_playing():
                    vc.play(FFmpegPCMAudioGTTS(sound_fp.read(), pipe=True))
                else:await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(e)


    @Cog.listener()
    async def on_message(self,message:Message):

        if f'<@!{self.bot.user.id}>' in message.content and len(message.content.split(
                )) == 1 or f'<@{self.bot.user.id}>' in message.content and len(
                    message.content.split()) == 1:        
            bucket = self.cd_mapping.get_bucket(message)
            retry_after = bucket.update_rate_limit()
            if retry_after:
                return
            return await message.channel.send(f'**Hi {message.author.mention}**',embed=Embed(description=f'➼ I am {self.bot.user.mention} <:peek:945670103037517834> , an easy to use TextToSpeech bot! \n\n➼ I work on ***Slash Commands*** 😄\n\n➼ **`Support:`**  https://discord.gg/FDhd5CXTmJ',color=config.COLOR_DARKTHEME).set_thumbnail(url=self.bot.user.avatar.url))

        if self.filter_channels == []:
            self.filter_channels = await self.get_set_channels()

        if message.author.bot :return
        vc:VoiceClient = message.guild.voice_client
        if vc is None:return
        if len(vc.channel.members)==1 or all([i.bot for i in vc.channel.members]):return
        if not self.is_tts_message(message):return

        try:
            if self.messageQueue.full():
                self.messageQueue.get_nowait()
            await self.messageQueue.put(message) 
        except asyncio.QueueFull :
            #await message.add_reaction()
            ...


async def setup(bot:Bot):
    await bot.add_cog(TTS(bot)) 