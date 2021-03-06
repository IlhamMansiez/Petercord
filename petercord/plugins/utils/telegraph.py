import os

from PIL import Image
from telegraph import upload_file

from petercord.utils import post_to_telegraph
from petercord import petercord, Message, Config, pool
from petercord.utils import progress

_T_LIMIT = 5242880


@petercord.on_cmd("tg m", about={
    'header': "Upload file to Telegra.ph's servers",
    'types': ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webp', '.html', '.txt', '.py'],
    'usage': "reply {tr}tg m to media or text : limit 5MB for media",
    'examples': "reply {tr}tg m to `header|content`\n(You can use html code)"})
async def telegraph_(message: Message):
    replied = message.reply_to_message
    if not replied:
        await message.err("reply to media or text")
        return
    if not ((replied.photo and replied.photo.file_size <= _T_LIMIT)
            or (replied.animation and replied.animation.file_size <= _T_LIMIT)
            or (replied.video and replied.video.file_name.endswith('.mp4')
                and replied.video.file_size <= _T_LIMIT)
            or (replied.sticker and replied.sticker.file_name.endswith('.webp'))
            or replied.text
            or (replied.document
                and replied.document.file_name.endswith(
                    ('.jpg', '.jpeg', '.png', '.gif', '.mp4', '.html', '.txt', '.py'))
                and replied.document.file_size <= _T_LIMIT)):
        await message.err("not supported!")
        return
    await message.edit("`processing...`")
    if (replied.text
        or (replied.document
            and replied.document.file_name.endswith(
            ('.html', '.txt', '.py')))):
        if replied.document:
            dl_loc = await message.client.download_media(
                message=message.reply_to_message,
                file_name=Config.DOWN_PATH,
                progress=progress,
                progress_args=(message, "trying to download")
            )
            with open(dl_loc, "r") as jv:
                text = jv.read()
            header = message.input_str
            if not header:
                header = "Pasted content by @diemmmmmmmmmm"
            os.remove(dl_loc)
        else:
            content = message.reply_to_message.text
            if "|" in content:
                content = content.split("|", maxsplit=1)
                header = content[0]
                text = content[1]
            else:
                text = content
                header = "Pasted content by @diemmmmmmmmmm"
        t_url = await pool.run_in_thread(post_to_telegraph)(header, text)
        jv_text = f"**[DATA TELEGRAPHMU ..KLIK]({t_url})**"
        await message.edit(text=jv_text, disable_web_page_preview=True)
        return
    dl_loc = await message.client.download_media(
        message=message.reply_to_message,
        file_name=Config.DOWN_PATH,
        progress=progress,
        progress_args=(message, "trying to download")
    )
    if replied.sticker:
        img = Image.open(dl_loc).convert('RGB')
        img.save(f'{Config.DOWN_PATH}/petercord.png', 'png')
        os.remove(dl_loc)
        dl_loc = f'{Config.DOWN_PATH}/petercord.png'
    await message.edit("`uploading to telegraph...`")
    try:
        response = upload_file(dl_loc)
    except Exception as t_e:
        await message.err(t_e)
    else:
        await message.edit(f"**[Click Here](https://telegra.ph{response[0]})**")
    finally:
        os.remove(dl_loc)
