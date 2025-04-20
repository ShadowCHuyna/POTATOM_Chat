#!/usr/bin/env python3


from asyncio import StreamReader, StreamWriter
import asyncio
import sys

from ChatUser import ChatUser, ChatMessage, ChatEvent
from config import Friend, ChatUserConfig, Room, load_config_from_json

reader: StreamReader = None
writer: StreamWriter = None
active_room = ""

async def sys_msg(*args):
    msg = "potato: "
    for i in args:
        msg+=i+" "
    msg+='\n'
    writer.write(msg.encode())
    await writer.drain()

async def handle_msg(cm: ChatMessage):
    msg = f"{cm.nickname}@{cm.room}: {cm.message}\n>" 
    writer.write(msg.encode())
    await writer.drain()
    pass

async def handle_add_friend(f: Friend):
    await sys_msg(f"Добавлен ШизоДруг: {f.nickname}@{f.destination}\n>")
    pass

async def handle_create_room(r: Room):
    await sys_msg(f"Новая палату ура-ура бЮдЖжет освоен как надо: {r.name}\nпациенты: {r.friends}\n>")
    pass

async def cmd_help():
    msg = """
/help - чмырят офлайн
/add_friend {dest} - добавляет шиза
/friends - список шизов
/create_room {name} {f1} {f2} {fn} - создает палату 
/rooms - список палат
/set_room {name} - переводят в палату
"""
    await sys_msg(msg)

async def cmd_add_friend(chat_user: ChatUser, dest: str):
    await chat_user.add_friend(dest)

async def cmd_friends(chat_user: ChatUser):
    msg = "шизы:\n"
    for f in chat_user.config.friends:
        msg+=f"{f.nickname}@{f.destination}\n>"
    await sys_msg(msg)

async def cmd_create_room(chat_user: ChatUser, name: str, friends: list[str]):
    friends_clr = []
    for f in friends:
        if f != "" and f != " ":
            friends_clr.append(f)

    await chat_user.create_room(name, friends)

async def cmd_rooms(chat_user: ChatUser):
    msg = "палаты:\n"
    for r in chat_user.config.rooms:
        msg += f"{r.name}\n>"
    await sys_msg(msg)

async def cmd_set_room(name: str):
    global active_room
    active_room = name
    await sys_msg(f"ты в палате: {name}\n>")

async def input_loop(chat_user: ChatUser):
    while True:
        writer.write(">".encode())
        await writer.drain()

        msg = await reader.readline() 
        msg = msg.decode()[:-1]

        if msg == "": continue
        if msg[0] == '/':
            cmd = msg.split(' ')
            if cmd[0] == "/help":
                await cmd_help()
            elif cmd[0] == "/add_friend":
                await cmd_add_friend(chat_user,cmd[1])
            elif cmd[0] == "/friends":
                await cmd_friends(chat_user)
            elif cmd[0] == "/create_room":
                await cmd_create_room(chat_user, cmd[1], cmd[2:])
            elif cmd[0] == "/rooms":
                await cmd_rooms(chat_user)
            elif cmd[0] == "/set_room":
                await cmd_set_room(cmd[1])
        elif active_room != "":
            await chat_user.send(active_room, msg)
            

def draw_logo():
    print("""
 _____                                                                   _____ 
( ___ )                                                                 ( ___ )
 |   |~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|   | 
 |   |  ____   ___ _____  _  _____ ___  __  __     ____ _           _    |   | 
 |   | |  _ \ / _ \_   _|/ \|_   _/ _ \|  \/  |   / ___| |__   __ _| |_  |   | 
 |   | | |_) | | | || | / _ \ | || | | | |\/| |  | |   | '_ \ / _` | __| |   | 
 |   | |  __/| |_| || |/ ___ \| || |_| | |  | |  | |___| | | | (_| | |_  |   | 
 |   | |_|    \___/ |_/_/___\_\_| \___/|_|  |_|___\____|_| |_|\__,_|\__| |   | 
 |   | __   __/ _ \ |___ /___ /              |_____|                     |   | 
 |   | \ \ / / | | |  |_ \ |_ \                                          |   | 
 |   |  \ V /| |_| | ___) |__) |                                         |   | 
 |   |   \_/  \___(_)____/____/                                          |   | 
 |___|~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~|___| 
(_____)                                                                 (_____)""")

async def main(loop: asyncio.AbstractEventLoop):
    global reader
    global writer

#####################################################################################################
    reader = asyncio.StreamReader(loop=loop)
    protocol = asyncio.streams.FlowControlMixin(loop=loop)
    transport, _ = await loop.connect_write_pipe(lambda: protocol, sys.stdout)
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    r_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: r_protocol, sys.stdin)
#####################################################################################################

    draw_logo()
    await sys_msg("Кидаю удава в i2p (где интернеты?)...")
    chat_user = ChatUser(load_config_from_json(), loop)
    await chat_user.start()
    await sys_msg(f"о ты в потоке XXX\n"+"="*64+
                  f"\nID: {chat_user.node.destination.base32}\nnickname: {chat_user.config.nickname}\nВсе удав в деле\n"+
                  "="*64)
    await cmd_help()

    chat_user.add_event_listener(ChatEvent.message, handle_msg)
    chat_user.add_event_listener(ChatEvent.add_friend, handle_add_friend)
    chat_user.add_event_listener(ChatEvent.create_room, handle_create_room)
    

    asyncio.ensure_future(input_loop(chat_user), loop=loop)

import logging
import random

if __name__ == "__main__":
    # loop = asyncio.get_event_loop()
    logging.basicConfig(level=logging.DEBUG, filename=f"./logs_{random.randint(0,99999999)}.log")
    # logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    try:
        loop.create_task(main(loop=loop))
        loop.run_forever()
    finally:

        loop.stop()
        loop.close()

    print("HELL...")