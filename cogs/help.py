import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button,View
import config


#=========================================
class MyHelp(commands.MinimalHelpCommand):
    async def send_pages(self):
        destination = self.get_destination()
        for page in self.paginator.pages:
            emby = discord.Embed(title='__HELP MENU__',description=page)
            await destination.send(embed=emby)
#=========================================
class help(commands.Cog):
    def __init__(self, bot):
        self.bot:commands.Bot = bot
        self.info = '<:info:964824278149238785>'
        
        self.help_message = """
***__TEXT TO SPEECH__ [8]*** 
 **`join`** |**`say`** | **`pause`** | **`resume`** | **`disconnect`** | **`tts-audio`** | **`play`** | **`filters`** |

***__SERVER__ [5]*** 
 **`247`** | **`default-language`** | **`set-channel`** |  **`settings`** | **`clear-data`** |

***__MISCELLANEOUS__ [3]*** 
 **`ping`** |  **`support`** |  **`clear-data`** | 
"""

    @app_commands.command(name="help",description='Shows the list of all available commands')
    async def help_slash(self, interaction: discord.Interaction) -> None:
        support = Button(label='Support',url=config.SUPPORT_SERVER, emoji='<:support:966372388654690354>')
        addbot = Button(label='Invite Bot',url=config.INVITE_URL,emoji='<:invite:966372015663620147>')

        view= View(timeout=None)
        view.add_item(addbot)
        view.add_item(support)     
        embed=discord.Embed(title=f'Help Menu',description=self.help_message, color=discord.Color.random())
        return await interaction.response.send_message(embed=embed,view=view)  
#=============================================================================================================

    @app_commands.command(name='vote',description="Upvote for our bot")
    async def vote_slash_(self,interaction:discord.Interaction):
        dbl = Button(label='dbl',url=config.DBL,emoji='<:dbl:961667394416295946>')
        topgg= Button(label='topgg', url=config.TOPGG,emoji = '<:topgg:963802430452158504>')

        view= View(timeout=None)
        view.add_item(dbl)
        view.add_item(topgg)
        embed=discord.Embed(title='Upvote Our Bot',description=f'> Please show your love and support by upvoting {self.bot.user.mention}.\n > It will give us a lot of happiness 😊',color=discord.Color.random()).set_footer(text='Thank you')
        await interaction.response.send_message(embed=embed,view=view)


async def setup(bot):
    await bot.add_cog(help(bot))