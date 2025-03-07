import asyncio
import discord
import inspect

from database import Database
from discord import Interaction
from discord.ext import commands
from discord.ui import View, Button
from enum import Enum
from functools import partial
from math import ceil
from typing import Union

__all__ = ('Session', 'Paginator', 'button', 'inverse_button',)

_first = '<:first:959014001264705576>'
_prev = '<:prev:959013753217773591>'
_next = _play = '<:next:959013883778056192>'
_last = _skip = '<:last:959014162518904852>'
_stop = _pause ='<:stop:959015026226790441>'

_queue = "<:queue_iconremovebgpreview:1057204665349062716>"
_pause_new = "<:pauseremovebgpreview:1057204660437532742>"
_play_new = "<:resumeremovebgpreview:1057204646273359923>"
_skip_new = "<:next_skip_icon:1057205854719451156>"
_clear = "<:clear:1057207037622231101>"
_replay = "<:replayremovebgpreview:1057204642846609530>"

_loop_disp = "<:loopremovebgpreview:1057209113668505680>"
_no_loop = "<:no_loopremovebgpreview:1057204656843006023>"
_loop_current = "<:loop_currentremovebgpreview:1057204649465233518>"
_loop_queue = "<:loop_queueremovebgpreview:1057204652980056065>"

class Button:
    __slots__ = ('_callback', '_inverse_callback', 'emoji', 'position', 'try_remove')

    def __init__(self, **kwargs):
        self._callback = kwargs.get('callback')
        self._inverse_callback = kwargs.get('inverse_callback')

        self.emoji = kwargs.get('emoji')
        self.position = kwargs.get('position')
        self.try_remove = kwargs.get('try_remove', True)


class Session:
    """Interactive session class, which uses reactions as buttons.

    timeout: int
        The timeout in seconds to wait for reaction responses.
    try_remove: bool
        A bool indicating whether or not the session should try to remove reactions after they have been pressed.
    """

    def __init__(self, *, timeout: int = 180, try_remove: bool = True):
        self._buttons = {}
        self._gather_buttons()

        self.page: discord.Message = None
        self._session_task = None
        self._cancelled = False
        self._try_remove = try_remove

        self.timeout = timeout
        self.buttons = self._buttons

        self._defaults = {}
        self._default_stop = {}

    def __init_subclass__(cls, **kwargs):
        pass

    def _gather_buttons(self):
        for _, member in inspect.getmembers(self):
            if hasattr(member, '__button__'):
                button = member.__button__

                sorted_ = self.sort_buttons(buttons=self._buttons)
                try:
                    button_ = sorted_[button.emoji]
                except KeyError:
                    self._buttons[button.position, button.emoji] = button
                    continue

                if button._inverse_callback:
                    button_._inverse_callback = button._inverse_callback
                else:
                    button_._callback = button._callback

                self._buttons[button.position, button.emoji] = button_

    def sort_buttons(self, *, buttons: dict = None):
        if buttons is None:
            buttons = self._buttons

        return {k[1]: v for k, v in sorted(buttons.items(), key=lambda t: t[0])}

    async def start(self, ctx, page=None):
        """Start the session with the given page.

        Parameters
        -----------
        page: Optional[str, discord.Embed, discord.Message]
            If no page is given, the message used to invoke the command will be used. Otherwise if
            an embed or str is passed, a new message will be created.
        """
        if not page:
            page = ctx.message

        if isinstance(page, discord.Embed):
            self.page = await ctx.send(embed=page)
        elif isinstance(page, discord.Message):
            self.page = page
        else:
            self.page = await ctx.send(page)

        self._session_task = ctx.bot.loop.create_task(self._session(ctx))

    async def _session(self, ctx):
        self.buttons = self.sort_buttons()

        ctx.bot.loop.create_task(self._add_reactions(self.buttons.keys()))

        await self._session_loop(ctx)

    async def _session_loop(self, ctx):
        while True:
            _add = asyncio.ensure_future(ctx.bot.wait_for('raw_reaction_add', check=lambda _: self.check(_)(ctx)))
            _remove = asyncio.ensure_future(ctx.bot.wait_for('raw_reaction_remove', check=lambda _: self.check(_)(ctx)))

            done, pending = await asyncio.wait(
                (_add, _remove),
                return_when=asyncio.FIRST_COMPLETED,
                timeout=self.timeout
            )

            for future in pending:
                future.cancel()

            if not done:
                return ctx.bot.loop.create_task(self.cancel())

            try:
                result = done.pop()
                payload = result.result()

                if result == _add:
                    action = True
                else:
                    action = False
            except Exception:
                return ctx.bot.loop.create_task(self.cancel())

            emoji = self.get_emoji_as_string(payload.emoji)
            button = self.buttons[emoji]

            if self._try_remove and button.try_remove:
                try:
                    await self.page.remove_reaction(payload.emoji, ctx.guild.get_member(payload.user_id))
                except discord.HTTPException:
                    pass

            member = ctx.guild.get_member(payload.user_id)

            if action and button in self._defaults.values() or button in self._default_stop.values():
                await button._callback(ctx, member)
            elif action and button._callback:
                await button._callback(self, ctx, member)
            elif not action and button._inverse_callback:
                await button._inverse_callback(self, ctx, member)

    @property
    def is_cancelled(self):
        """Return True if the session has been cancelled."""
        return self._cancelled

    async def cancel(self):
        """Cancel the session."""
        self._cancelled = True
        await self.teardown()

    async def teardown(self):
        """Clean the session up."""
        self._session_task.cancel()

        try:
            await self.page.delete()
        except discord.NotFound:
            pass

    async def _add_reactions(self, reactions):
        for reaction in reactions:
            try:
                await self.page.add_reaction(reaction)
            except discord.NotFound:
                pass

    def get_emoji_as_string(self, emoji):
        return f'{emoji.name}{":" + str(emoji.id) if emoji.is_custom_emoji() else ""}'

    def check(self, payload):
        """Check which takes in a raw_reaction payload. This may be overwritten."""
        emoji = self.get_emoji_as_string(payload.emoji)

        def inner(ctx):
            if emoji not in self.buttons.keys():
                return False
            elif payload.user_id == ctx.bot.user.id or payload.message_id != self.page.id:
                return False
            elif payload.user_id != ctx.author.id:
                return False
            return True

        return inner


class Paginator(Session):
    """Paginator class, that used an interactive session to display buttons.

    title: str
        Only available when embed=True. The title of the embeded pages.
    length: int
        The number of entries per page.
    entries: list
        The entries to paginate.
    extra_pages: list
        Extra pages to append to our entries.
    prefix: Optional[str]
        The formatting prefix to apply to our entries.
    suffix: Optional[str]
        The formatting suffix to apply to our entries.
    format: Optional[str]
        The format string to wrap around our entries. This should be the first half of the format only,
        E.g to wrap **Entry**, we would only provide **.
    colour: discord.Colour
        Only available when embed=True. The colour of the embeded pages.
    use_defaults: bool
        Option which determines whether we should use default buttons as well. This is True by default.
    embed: bool
        Option that indicates that entries should embeded.
    joiner: str
        Option which allows us to specify the entries joiner. E.g self.joiner.join(self.entries)
    timeout: int
        The timeout in seconds to wait for reaction responses.
    thumbnail:
        Only available when embed=True. The thumbnail URL to set for the embeded pages.
    """

    def __init__(self, *, title: str = '', length: int = 10, entries: list = None,
                 extra_pages: list = None, prefix: str = '', suffix: str = '', format: str = '',
                 colour: Union[int, discord.Colour] = None,
                 color: Union[int, discord.Colour] = None, use_defaults: bool = True, embed: bool = True,
                 joiner: str = '\n', timeout: int = 180, thumbnail: str = None):
        super().__init__()
        self._defaults = {(0, '⏮'): Button(emoji='⏮', position=0, callback=partial(self._default_indexer, 'start')),
                          (1, '◀'): Button(emoji='◀', position=1, callback=partial(self._default_indexer, -1)),
                          (2, '⏹'): Button(emoji='⏹', position=2, callback=partial(self._default_indexer, 'stop')),
                          (3, '▶'): Button(emoji='▶', position=3, callback=partial(self._default_indexer, +1)),
                          (4, '⏭'): Button(emoji='⏭', position=4, callback=partial(self._default_indexer, 'end'))}
        self._default_stop = {(0, '⏹'): Button(emoji='⏹', position=0, callback=partial(self._default_indexer, 'stop'))}

        self.buttons = {}

        self.page: discord.Message = None
        self._pages = []
        self._session_task = None
        self._cancelled = False
        self._index = 0

        self.title = title
        self.colour = colour or color
        self.thumbnail = thumbnail
        self.length = length
        self.timeout = timeout
        self.entries = entries
        self.extra_pages = extra_pages or []

        self.prefix = prefix
        self.suffix = suffix
        self.format = format
        self.joiner = joiner
        self.use_defaults = use_defaults
        self.use_embed = embed

    def chunker(self):
        """Create chunks of our entries for pagination."""
        for x in range(0, len(self.entries), self.length):
            yield self.entries[x:x + self.length]

    def formatting(self, entry: str):
        """Format our entries, with the given options."""
        return f'{self.prefix}{self.format}{entry}{self.format[::-1]}{self.suffix}'
#########################################################################
    async def start(self, ctx: commands.Context, page=None):
        """Start our Paginator session."""
        if not self.use_defaults:
            if not self._buttons:
                raise AttributeError('Session has no buttons.')  # Raise a custom exception at some point.

        await self._paginate(ctx)

    async def _paginate(self, ctx: commands.Context):
        if not self.entries and not self.extra_pages:
            raise AttributeError('You must provide atleast one entry or page for pagination.')  # ^^

        if self.entries:
            self.entries = [self.formatting(entry) for entry in self.entries]
            entries = list(self.chunker())
        else:
            entries = []

        for chunk in entries:
            if not self.use_embed:
                self._pages.append(self.joiner.join(chunk))
            else:
                embed = discord.Embed(title=self.title, description=self.joiner.join(chunk), colour=self.colour)

                if self.thumbnail:
                    embed.set_thumbnail(url=self.thumbnail)

                self._pages.append(embed)

        self._pages = self._pages + self.extra_pages

        if isinstance(self._pages[0], discord.Embed):
            self.page = await ctx.send(embed=self._pages[0])
        else:
            self.page = await ctx.send(self._pages[0])

        self._session_task = ctx.bot.loop.create_task(self._session(ctx))

    async def _session(self, ctx):
        if self.use_defaults:
            if len(self._pages) == 1:
                self._buttons = {**self._default_stop, **self._buttons}
            else:
                self._buttons = {**self._defaults, **self._buttons}

        self.buttons = self.sort_buttons()

        ctx.bot.loop.create_task(self._add_reactions(self.buttons))

        await self._session_loop(ctx)

#####==================EDIT============================================================================
    class eval_butoons(discord.ui.View):
        def __init__(self,task):
            super().__init__(timeout=120)
            self.task=task
            self.previous = task._index


        @discord.ui.button(style=discord.ButtonStyle.primary,custom_id='first',emoji=_first)
        async def button_first(self,interaction:discord.Interaction,button):
            self.task._index = 0
            if isinstance(self.task._pages[self.task._index], discord.Embed):
                await interaction.response.edit_message(embed=self.task._pages[self.task._index])
            else:
                await interaction.response.edit_message(content=self.task._pages[self.task._index]) 

        @discord.ui.button(style=discord.ButtonStyle.primary,custom_id='prev',emoji=_prev)
        async def button_prev(self,interaction:discord.Interaction,button):
            self.task._index += -1
            if self.task._index < 0:
                self.task._index = len(self.task._pages) - 1 # self.task.previous         
                   
            if isinstance(self.task._pages[self.task._index], discord.Embed):
                await interaction.response.edit_message(embed=self.task._pages[self.task._index])
            else:
                await interaction.response.edit_message(content=self.task._pages[self.task._index])  

        @discord.ui.button(style=discord.ButtonStyle.primary,custom_id='clear',emoji=_stop)
        async def button_clear(self,interaction:discord.Interaction,button):
            self.clear_items      
            await interaction.response.edit_message(view=None)            

        @discord.ui.button(style=discord.ButtonStyle.primary,custom_id='next',emoji=_next)
        async def button_next(self,interaction:discord.Interaction,button):
            self.task._index += 1
            if self.task._index > len(self.task._pages) - 1 :
                self.task._index = 0 #self.previous   
            if isinstance(self.task._pages[self.task._index], discord.Embed):
                await interaction.response.edit_message(embed=self.task._pages[self.task._index])
            else:
                await interaction.response.edit_message(content=self.task._pages[self.task._index]) 

        @discord.ui.button(style=discord.ButtonStyle.primary,custom_id='last',emoji=_last)
        async def button_last(self,interaction:discord.Interaction,button):
            self.task._index = len(self.task._pages) - 1
            if isinstance(self.task._pages[self.task._index], discord.Embed):
                await interaction.response.edit_message(embed=self.task._pages[self.task._index])
            else:
                await interaction.response.edit_message(content=self.task._pages[self.task._index]) 

        async def on_timeout(self):
            self.clear_items      
            await self.task.page.edit(view=self)

#
    async def start_slash(self, interaction:discord.Interaction, page=None):
        """Start our Paginator session."""
        if not self.use_defaults:
            if not self._buttons:
                raise AttributeError('Session has no buttons.')  # Raise a custom exception at some point.

        await self._paginate_slash(interaction)

    async def _paginate_slash(self,interaction:discord.Interaction):
        if not self.entries and not self.extra_pages:
            #raise AttributeError('You must provide atleast one entry or page for pagination.')  # ^^
            print('Paginator failed to start coz of 0 pages')
            return 

        if self.entries:
            self.entries = [self.formatting(entry) for entry in self.entries]
            entries = list(self.chunker())
        else:
            entries = []

        for chunk in entries:
            if not self.use_embed:
                self._pages.append(self.joiner.join(chunk))
            else:
                embed = discord.Embed(title=self.title, description=self.joiner.join(chunk), colour=self.colour)

                if self.thumbnail:
                    embed.set_thumbnail(url=self.thumbnail)

                self._pages.append(embed)

        self._pages = self._pages + self.extra_pages

        view = self.eval_butoons(task=self)
        if isinstance(self._pages[0], discord.Embed):
            if self.use_defaults:
                if len(self._pages) > 1:
                    self.page = await interaction.followup.send(embed=self._pages[0],ephemeral=True,view=view)
                else:
                    self.page = await interaction.followup.send(embed=self._pages[0],ephemeral=True)
        else:
            self.page = await interaction.followup.send(self._pages[0],ephemeral=True,view=view)

        #self._session_task = interaction.bot.loop.create_task(self._session(interaction))

###################################################################################################
    async def _default_indexer(self, control, ctx, member):
        previous = self._index

        if control == 'stop':
            return await self.cancel()

        if control == 'end':
            self._index = len(self._pages) - 1
        elif control == 'start':
            self._index = 0
        else:
            self._index += control

        if self._index > len(self._pages) - 1 or self._index < 0:
            self._index = previous

        if self._index == previous:
            return

        if isinstance(self._pages[self._index], discord.Embed):
            await self.page.edit(embed=self._pages[self._index])
        else:
            await self.page.edit(content=self._pages[self._index])


def button(emoji: str, *, try_remove=True, position: int = 666):
    """A decorator that adds a button to your interactive session class.

    Parameters
    -----------
    emoji: str
        The emoji to use as a button. This could be a unicode endpoint or in name:id format,
        for custom emojis.
    position: int
        The position to inject the button into.

    Raises
    -------
    TypeError
        The button callback is not a coroutine.
    """

    def deco(func):
        if not asyncio.iscoroutinefunction(func):
            raise TypeError('Button callback must be a coroutine.')

        if hasattr(func, '__button__'):
            button = func.__button__
            button._callback = func

            return func

        func.__button__ = Button(emoji=emoji, callback=func, position=position, try_remove=try_remove)
        return func

    return deco


def inverse_button(emoji: str = None, *, try_remove=False, position: int = 666):
    """A decorator that adds an inverted button to your interactive session class.

    The inverse button will work when a reaction is unpressed.

    Parameters
    -----------
    emoji: str
        The emoji to use as a button. This could be a unicode endpoint or in name:id format,
        for custom emojis.
    position: int
        The position to inject the button into.

    Raises
    -------
    TypeError
        The button callback is not a coroutine.
    """

    def deco(func):
        if not asyncio.iscoroutinefunction(func):
            raise TypeError('Button callback must be a coroutine.')

        if hasattr(func, '__button__'):
            button = func.__button__
            button._inverse_callback = func

            return func

        func.__button__ = Button(emoji=emoji, inverse_callback=func, position=position, try_remove=try_remove)
        return func

    return deco

#===============================================================================================

class LoopMode(Enum):
    off: int = 0    
    song: int = 1
    queue: int = 2

    def __str__(self) -> str:
        return self.value

# class Player(wavelink.Player):
#     #__slots__ = ("loop", "delmsg", "_ctx", "autoplay","count", "lofi")

#     def __init__(self, *args ):
#         super().__init__(*args)
#         self.loop: LoopMode = LoopMode.off
#         self.delmsg=None
#         self.interaction_channel = None
#         self.autoplay = False  
#         #self.count = 0
#         #self.lofi = False

#     async def on_voice_state_update(self, data) -> None:
#         self._voice_state.update({"sessionId": data["session_id"]})
#         channel_id = data["channel_id"]
#         if not channel_id: 
#             self._voice_state.clear()
#             return
#         self.channel = self.guild.get_channel(int(channel_id)) 
#         if data.get("token"):
#             await self._dispatch_voice_update({**self._voice_state, "event": data})

#     def set_values(self,interaction:Interaction):
#         self.interaction_channel = interaction.channel


# async def disconnect_all(vc:Player)->None:
#         await vc.set_filter(wavelink.filters.Filter(equalizer=wavelink.Equalizer.flat()))
#         await vc.stop()
#         vc.queue.reset()
#         vc.loop = LoopMode.off 
#         await vc.disconnect(force=True) 
#         vc.autoplay=False
#         try:
#             await vc.delmsg.delete()
#         except:
#             pass

# def createEmbed(description:str=None,title:str=None,color:discord.Colour=discord.Color.random()):
#     return discord.Embed(title=title,description=description,color=color)

# async def is_privilaged(interaction:discord.Interaction,database:Database,vc:Player):
#     if interaction.user.guild_permissions.administrator:
#         return True    
#     check = await database.fetchone("SELECT roleid FROM djdb WHERE gid=?",interaction.guild_id)
#     if check is None:
#         return True
#     elif len(vc.channel.members)<=2 or [x.bot for x in vc.channel.members].count(False)==1:
#         return True
#     elif not check in [role.id for role in interaction.user.roles]:
#         return False
#     return True

# #===============================================================================================
# class queue_view(View):
#     def __init__(self,ctx,vc,page):
#         super().__init__(timeout=60)
#         self.ctx=ctx
#         self.page = page
#         self.vc=vc
    
#     async def update(self,interaction:Interaction, songs:str,vc:Player,page:int,pages:int):
#         embed1=discord.Embed(title=f'Queue {len(vc.queue)} songs',description = songs,color=discord.Color.random())
#         embed1=embed1.set_footer(text='Viewing page {}/{}'.format(page, pages))
#         await interaction.response.edit_message(embed=embed1)
        
        
#     @discord.ui.button(label = 'First',style=discord.ButtonStyle.primary,custom_id='first',emoji='⏮')
#     async def button_first(self,interaction:discord.Interaction,button):
#         self.page = 1
#         items_per_page = 10 
#         pages = ceil(len(list(self.vc.queue)) / items_per_page)
#         start = (self.page - 1) * items_per_page
#         end = start + items_per_page
#         if self.page>pages or self.page<=0:
#             await interaction.response.defer()
#         else:  
#             songs='```ml\n'
#             for no,track in enumerate(list(self.vc.queue)[start:end],start=1):
#                 songs+=f'{no}. {track.title} \n\n'
#             songs+='```'
#             await self.update(interaction,songs,self.vc,self.page,pages)

#     @discord.ui.button(label = 'Previous',style=discord.ButtonStyle.primary,custom_id='prev',emoji='⬅')
#     async def button_prev(self,interaction:discord.Interaction,button):
#         self.page -= 1
#         items_per_page = 10 
#         pages = ceil(len(list(self.vc.queue)) / items_per_page)
#         if self.page<=0:
#             self.page=pages                    
#         start = (self.page - 1) * items_per_page
#         end = start + items_per_page                          
#         songs='```ml\n'
#         for no,track in enumerate(list(self.vc.queue)[start:end],start=1):
#             songs+=f'{no+(self.page-1)*10}. {track.title} \n\n'
#         songs+='```'
#         await self.update(interaction,songs,self.vc,self.page,pages)

#     @discord.ui.button(label = 'Clear',style=discord.ButtonStyle.red,custom_id='clear',emoji='🗑')
#     async def button_clear(self,interaction:discord.Interaction,button):
#         self.vc.queue.clear()
#         await interaction.response.edit_message(embed=discord.Embed(description=f'🟩 | Queue cleared',color=discord.Color.random()),view=None)

#     @discord.ui.button(label = 'Next',style=discord.ButtonStyle.primary,custom_id='next',emoji='➡')
#     async def button_next(self,interaction:discord.Interaction,button):
#         self.page += 1
#         items_per_page = 10 
#         pages = ceil(len(list(self.vc.queue)) / items_per_page)
#         if self.page>pages:
#             self.page = 1                    
#         start = (self.page - 1) * items_per_page
#         end = start + items_per_page
#         songs='```ml\n'
#         for no,track in enumerate(list(self.vc.queue)[start:end],start=1):
#             songs+=f'{no+(self.page-1)*10}. {track.title} \n\n'
#         songs+='```'
#         await self.update(interaction,songs,self.vc,self.page,pages)

#     @discord.ui.button(label = 'Last',style=discord.ButtonStyle.primary,custom_id='last',emoji='⏭')
#     async def button_last(self,interaction:discord.Interaction,button):
#         items_per_page = 10 
#         pages = ceil(len(list(self.vc.queue)) / items_per_page)
#         self.page = pages
#         start = (self.page - 1) * items_per_page
#         end = start + items_per_page
#         if self.page>pages or self.page<=0:
#             await interaction.response.defer()
#         else:  
#             songs='```ml\n'
#             for no,track in enumerate(list(self.vc.queue)[start:end],start=1):
#                 songs+=f'{no+(self.page-1)*10}. {track.title} \n\n'
#             songs+='```'
#             await self.update(interaction,songs,self.vc,self.page,pages)

#     async def on_timeout(self):
#         for btn in self.children:
#             btn.disabled = True     
#         try:   
#             await self.ctx.edit_original_message(view=self)
#         except:pass
        
# #===============================================================================================

# # class Dropdown(discord.ui.Select):
# #     def __init__(self,vc:Player,interaction:Interaction):
# #         options1 = [
# #            discord.SelectOption(label='Red', description='Your favourite colour is red', emoji='🟥'),
# #            discord.SelectOption(label='Green', description='Your favourite colour is green', emoji='🟩'),
# #            discord.SelectOption(label='Blue', description='Your favourite colour is blue', emoji='🟦'),
# #         ]
# #         options = [discord.SelectOption(label=song) for song in vc.queue]        
# #         super().__init__(placeholder='Choose your favourite colour...', min_values=1, max_values=1, options=options)

# #     async def callback(self, interaction: discord.Interaction):
# #         await interaction.response.send_message(f'Your favourite colour is {self.values[0]}')


# class Now_playing_buttons(View):
#     def __init__(self, bot:commands.Bot,vc:Player):
#         super().__init__(timeout=None)
#         self.bot = bot
#         self.database:Database = bot.db
#         self.vc = vc

#     async def interaction_check(self, interaction: Interaction) -> bool:
#         if interaction.user.voice is None:
#             await interaction.response.send_message(embed=createEmbed("You are not connected to any voice channel!"),ephemeral=True)
#             return False

#         elif not await is_privilaged(interaction,self.database,self.vc):
#             await interaction.response.send_message(embed=createEmbed("You do not have permissions to perform this action!"),ephemeral=True)
#             return False

#         elif interaction.guild.voice_client is None or self.vc is None or not self.vc.is_connected():
#             await interaction.response.send_message(embed=createEmbed("I am not connected to any voice channel!"),ephemeral=True)
#             return False

#         elif not interaction.guild.voice_client.is_connected():
#             await interaction.response.send_message(embed=createEmbed("Currently I am not playing anything "),ephemeral=True)
#             return False

#         return True

#     #@discord.ui.button(label='▶',custom_id='resume',style=discord.ButtonStyle.primary)
#     #async def resume(self,interaction:Interaction,button:Button):
#     #    vc:Player = interaction.guild.voice_client

#     @discord.ui.button(label=None,emoji=_pause_new,custom_id='resume_pause',style=discord.ButtonStyle.gray)
#     async def resume_pause(self,interaction:Interaction,button:Button):
#         vc:Player = interaction.guild.voice_client
#         if not vc.is_paused():
#             await vc.pause()
#             #button.label = 'Resume'
#             button.emoji = _play_new
#             #button.style = discord.ButtonStyle.green
#             await interaction.response.edit_message(view=self)
#         else:
#             await vc.resume()
#             #button.label = f'Pause'
#             button.emoji = _pause_new
#             #button.style = discord.ButtonStyle.red
#             await interaction.response.edit_message(view=self)


#     @discord.ui.button(label=None,emoji=_skip_new,custom_id='skip',style=discord.ButtonStyle.gray)
#     async def next(self,interaction:Interaction,button:Button):
#         vc:Player = interaction.guild.voice_client
#         if vc.is_playing():
#             vc.inter = interaction
#             await vc.stop()
#             await interaction.response.defer(ephemeral=True)

#     @discord.ui.button(label=None,emoji=_queue,custom_id='queue',style=discord.ButtonStyle.gray)
#     async def queue(self,interaction:Interaction,button:Button):
#         vc:Player = interaction.guild.voice_client
#         if not vc.queue.is_empty:
#             page = 1
#             items_per_page = 10 
#             pages = ceil(len(list(vc.queue)) / items_per_page)
#             start = (page - 1) * items_per_page
#             end = start + items_per_page
#             songs='```ml\n'
#             for no,track in enumerate(list(vc.queue)[start:end],start=1):
#                 songs+=f'{no}. {track.title} \n\n'
#             songs+='```'

#             embed1=discord.Embed(title=f'Queue {len(vc.queue)} songs',description = songs,color=discord.Color.random())
#             embed1=embed1.set_footer(text='Viewing page {}/{}'.format(page, pages))
# # buttons   
#             np = '' ; 
#             if vc.is_playing():
#                 track = vc.source.title
#                 np = f'Now playing **{track}**'        
#             if len(vc.queue)>10:             
#                 view= queue_view(interaction,vc,page)
#                 await interaction.response.send_message(np,embed=embed1,view = view)
#             else:
#                 await interaction.response.send_message(np,embed=embed1)
#         else:
#             await interaction.response.send_message(embed=discord.Embed(description=f'Queue is empty!',color=discord.Color.red()))


#     @discord.ui.button(label=None,emoji=_clear,custom_id='clear',style=discord.ButtonStyle.gray)
#     async def stop(self,interaction:Interaction,button:Button):
#         vc:Player = interaction.guild.voice_client
#         vc.queue.clear()
#         await interaction.response.edit_message(view=self)

#     @discord.ui.button(label=None,emoji="👋",custom_id='leave',style=discord.ButtonStyle.danger)
#     async def disconnect(self,interaction:Interaction,button:Button):
#         vc:Player = interaction.guild.voice_client
#         await interaction.response.defer(ephemeral=True)
#         vc.inter = interaction
#         await disconnect_all(vc)

#     # @discord.ui.button(label=None,emoji=_loop_disp,custom_id='loop',style=discord.ButtonStyle.gray)
#     # async def _loop(self,interaction:Interaction,button:Button):
#     #     vc:Player = interaction.guild.voice_client
        
#     #     if vc.loop==LoopMode.off:
#     #         vc.loop=LoopMode.song
#     #         button.emoji = _loop_current
#     #         await interaction.response.edit_message(view=self)
#     #         await interaction.followup.send(embed=discord.Embed(description = "Looping `Current Track`"))

#     #     elif vc.loop==LoopMode.song:
#     #         vc.loop=LoopMode.queue
#     #         button.emoji = _loop_queue
#     #         await interaction.response.edit_message(view=self)
#     #         await interaction.followup.send(embed=discord.Embed(description = "Looping `Queue`"))

#     #     elif vc.loop==LoopMode.queue:
#     #         vc.loop=LoopMode.off
#     #         button.emoji = _no_loop
#     #         await interaction.response.edit_message(view=self)
#     #         await interaction.followup.send(embed=discord.Embed(description = "Looping `Disabled`"))

#     # @discord.ui.button(label=None,emoji=_replay,custom_id='replay',style=discord.ButtonStyle.gray)
#     # async def _loop(self,interaction:Interaction,button:Button):
#     #     await interaction.response.defer(ephemeral=True)
#     #     vc:Player = interaction.guild.voice_client
#     #     if vc.is_playing():
#     #         await vc.seek(0)
#     #         await vc.set_pause(False)