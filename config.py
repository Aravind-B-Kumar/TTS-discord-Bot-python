from discord import Color
from discord.ext.commands import Bot

TOKEN:str = ""
SPOTIFY_CLIENT_ID:str = ""
SPOTIFY_CLIENT_SECRET:str = ""
INVITE_URL = ""
SUPPORT_SERVER = ""
TOPGG = ""
DBL = ""

COLOR_RANDOM = Color.random()
COLOR_DARKTHEME = Color.dark_theme()
COLOR_DANGER = COLOR_RED = Color.red()
COLOR_SUCCESS = COLOR_GREEN = Color.green()

FFMPEG_BASE_OPTION:str = (
    "-loglevel panic -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
)

filters:dict[str,str] = {
    "Normal" : "",
    #"Nightcore": ",atempo=1.06,asetrate=44100*1.2",
    "Nightcore": ",atempo=1.06,asetrate=1.15*44.1k,aresample=resampler=soxr:precision=24:osf=s32:tsf=s32p:osr=44.1k",
    "Robot": ",afftfilt=real='hypot(re,im)*sin(0)':imag='hypot(re,im)*cos(0)':win_size=512:overlap=0.75",
    "Earrape": ",acrusher=.1:1:64:0:log",
    "Bass": ",bass=g=16",
    "Backwards": ",areverse",
    "Echo": ",aecho=0.5:0.5:500|50000:1.0|1.0",
    "Muffle": ",lowpass=f=300",
    "Treble": ",treble=g=15",
    "Phaser": ",aphaser=type=t:speed=2:decay=0.6",
    "Tremolo": ",apulsator=mode=sine:hz=3:width=0.1:offset_r=0",
    "Vibrato": ",vibrato=f=10:d=1",
    "Whisper": ",afftfilt=real='hypot(re,im)*cos((random(0)*2-1)*2*3.14)':imag='hypot(re,im)*sin((random(1)*2-1)*2*3.14)':win_size=128:overlap=0.8",
}

async def tfs_connections(bot:Bot) -> None:
    channels = await bot.db.fetchall("SELECT vcid FROM tfs") # [(865459468665487387,)]
    if channels ==[]:return
    for i in channels:
        if i[0] is not None:
            try:
                vc= bot.get_channel(i[0])
                await vc.connect(self_deaf=True,reconnect=True)
            except:pass