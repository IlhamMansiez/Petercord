import asyncio
from datetime import datetime

from petercord import Message, petercord


@petercord.on_cmd(
    "ping",
    about={
        "header": "check how long it takes to ping your userbot",
        "flags": {"-a": "average ping"},
    },
    group=-1,
)
async def pingme(message: Message):
    start = datetime.now()
    if "-a" in message.flags:
        await message.edit("`!....`")
        await asyncio.sleep(0.3)
        await message.edit("`..!..`")
        await asyncio.sleep(0.3)
        await message.edit("`....!`")
        end = datetime.now()
        t_m_s = (end - start).microseconds / 1000
        m_s = round((t_m_s - 0.6) / 3, 3)
        await message.edit(f"**🎖PETERCORD🎖 PONG **\n`{m_s} ms`")
    else:
        await message.edit("`Pong!`")
        end = datetime.now()
        m_s = (end - start).microseconds / 1000
        await message.edit(f"**🎖PETERCORD🎖 PING**\n`{m_s} ms`")
