# Petercord

from petercord import Message, petercord


@petercord.on_cmd("del", about={"header": "delete replied message"})
async def del_msg(message: Message):
    msg_ids = [message.message_id]
    if message.reply_to_message:
        msg_ids.append(message.reply_to_message.message_id)
    await message.client.delete_messages(message.chat.id, msg_ids)
