import asyncio
from typing import Literal, NotRequired, TypedDict, Dict
from asyncio import StreamReader, StreamWriter
import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Awaitable, Any

import random
import logging
import sys



import i2plib
import utilsi2p
from config import ChatUserConfig, Friend, Room



BUFFER_SIZE = 4096
logger = logging.getLogger(__package__)



class ChatEvent(Enum):
    message = 1
    add_friend = 2
    create_room = 3

@dataclass
class ChatMessage:
    room: str
    nickname: str
    message: str

ChatMessageHandler = Callable[[ChatMessage], Awaitable[Any]]
AddFriendHandler = Callable[[Friend], Awaitable[Any]]
CreateRoomHandler = Callable[[Room], Awaitable[Any]]

class ChatUser:
    node: utilsi2p.i2pNode
    config: ChatUserConfig
    loop: asyncio.AbstractEventLoop
    messages_streams: dict[str, tuple[StreamReader, StreamWriter]] = {}
    eventListeners: dict[int, list[ChatMessageHandler|AddFriendHandler|CreateRoomHandler|any]] = {}

    def __init__(self, config: ChatUserConfig, loop: asyncio.AbstractEventLoop = None):
        self.config = config
        self.loop = loop
        pass

    async def start(self):
        opt: utilsi2p.i2pNodeOpt = {
            "private_key": None if self.config.private_key == "" else self.config.private_key,
            "sam_address": self.config.sam_address  
        }
        self.node = await utilsi2p.create_i2pNode(opt, loop=self.loop)
        await self.node.start()

        self.__handlers__()

    def __handlers__(self):
        async def add_friend_stream(inc: bytes, reader: StreamReader, writer: StreamWriter):
            remote_destination = i2plib.Destination(inc.decode().strip())
            # print("ssssssssssssssssssssssssssssssssssssssssssssssssss")

            nick = (await reader.read(BUFFER_SIZE)).decode()
            # print("eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee")
            # print("nick:",nick)
            writer.write(self.config.nickname.encode())
            await writer.drain()
            writer.write(b"ok")
            await writer.drain()

            sa = await reader.read(BUFFER_SIZE)
            # print("pppppppppppppppppppppppppppppppppppppppppppp")
            if sa != b"ok":
                raise "add_friend_stream err"
            
            self.config.friends.append(Friend(nickname=nick, destination=remote_destination.base32))
            
            # await asyncio.sleep(10)
            writer.close()
            self.__emite_event__(ChatEvent.add_friend, Friend(nickname=nick, destination=remote_destination.base32))            

        async def create_room_stream(inc: bytes, reader: StreamReader, writer: StreamWriter):
            rd = i2plib.Destination(inc.decode().strip())
            room = Room(**json.loads((await reader.read(BUFFER_SIZE)).decode()))

            writer.write(b"ok")
            await writer.drain()
            sa = await reader.read(BUFFER_SIZE)
            if sa != b"ok":
                raise "create_room_stream err"
            
            self.config.rooms.append(room)

            # await asyncio.sleep(10)
            writer.close()         
            self.__emite_event__(ChatEvent.create_room, room)

        async def messages_stream(inc: bytes, reader: StreamReader, writer: StreamWriter):
            while True:
                msg: ChatMessage = ChatMessage(**json.loads((await reader.read(BUFFER_SIZE)).decode()))
                writer.write(b"ok")
                await writer.drain()
                self.__emite_event__(ChatEvent.message, msg)


        self.node.handle("add_friend", add_friend_stream)
        self.node.handle("create_room", create_room_stream)
        self.node.handle("messages_stream", messages_stream)
        pass

    def add_event_listener(self, event: ChatEvent, handler: ChatMessageHandler | any):
        if self.eventListeners.get(event) == None:
            self.eventListeners[event] = []
        self.eventListeners[event].append(handler)
        
    def __emite_event__(self, event: ChatEvent, *args):
        if self.eventListeners.get(event) == None: return
        for h in self.eventListeners.get(event):
            asyncio.ensure_future(h(*args), loop=self.loop)
        

    async def add_friend(self, dest: str):
        try:
            logger.debug("попытка добавить друга")

            r, w = await self.node.dialProtocol(dest=dest+".b32.i2p", name="add_friend")
            w.write(self.config.nickname.encode())
            await w.drain()
            # print("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
            nick = (await r.read(BUFFER_SIZE)).decode()
            # print("nick:",nick)
            # print("-------------------")
            sa = await r.read(BUFFER_SIZE)
            # print("WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW")
            if sa != b"ok":
                raise "add_friend err"
            w.write(b"ok")
            await w.drain()
            self.config.friends.append(Friend(nickname=nick, destination=dest))
            
            # await asyncio.sleep(10)
            w.close()

            self.__emite_event__(ChatEvent.add_friend, Friend(nickname=nick, destination=dest))
            logger.debug("заканчиваю добавить друга")
        except Exception as e:
            print(f"не смог друга найти: {e}")
            logger.error("я вахуе где друзья")

    async def create_room(self, name: str, friends: list[str]):
        try:
            async def create_room_friend(friend: str):
                logger.debug("создаю комнату")
                r, w = await self.node.dialProtocol(friend+".b32.i2p", "create_room")
                req = {
                    "name": name,
                    "friends": friends
                }
                w.write(json.dumps(req).encode())
                await w.drain()
                sa = await r.read(BUFFER_SIZE)
                if sa != b"ok":
                    raise "create_room err"
                w.write(b"ok")
                await w.drain()

                # await asyncio.sleep(10)
                w.close()
                logger.debug("закончил создовать комнату")
                self.__emite_event__(ChatEvent.create_room, Room(name, friends))

            for f in friends:
                if f == self.node.destination.base32: continue
                asyncio.ensure_future(create_room_friend(f), loop=self.loop)

            self.config.rooms.append(Room(name, friends))
        except Exception as e:
            print(f"не создал комнату ты в общаге: {e}")
            logger.error("каловая комната")


    async def send(self, room: str, msg: str):
        try:
            async def msg2friend(friend: str):
                logger.debug("отправляю сообщение")
                r: StreamReader = None
                w: StreamWriter = None
                if self.messages_streams.get(friend) == None:
                    # print("messages_streams add friend stream:", friend)
                    r,w = await self.node.dialProtocol(friend+".b32.i2p", "messages_stream")
                    self.messages_streams[friend] = (r,w)
                r,w = self.messages_streams.get(friend)

                req = {
                    "room": room,
                    "nickname": self.config.nickname,
                    "message": msg
                }
                w.write(json.dumps(req).encode())
                await w.drain()
                sa = await r.read(BUFFER_SIZE)
                if sa != b"ok":
                    raise f"{friend} игнорит"
                
                logger.debug("кал отправлен")

            for r in self.config.rooms:
                if r.name == room:
                    for f in r.friends:
                        if f == self.node.destination.base32: 
                            # print("AAAAAAAAAAAAAAAAAAA", f)
                            continue
                        # print("connect to:",f)
                        asyncio.ensure_future(msg2friend(f), loop=self.loop)

                    break
        
        except Exception as e:
            print(f"не смог отправить твой словестный понос: {e}")
            logger.debug("я не отправил вафиге")
        


if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG, filename="./logs.log")
    # logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    # loop.set_debug(True)

    async def main(loop):
        print("init test chat")
        test_config: ChatUserConfig = ChatUserConfig(nickname=f"tester_{random.randint(0,99999999)}",
                                                    private_key="",
                                                    sam_address=i2plib.get_sam_address(),
                                                    friends=[],
                                                    rooms=[])
        chat_user = ChatUser(test_config, loop)
        await chat_user.start()
        print("======================================")
        print("ID:",chat_user.node.destination.base32)
        print("nickname:", test_config.nickname)
        print("======================================")

            

        reader = asyncio.StreamReader(loop=loop)
        protocol = asyncio.streams.FlowControlMixin(loop=loop)
        transport, _ = await loop.connect_write_pipe(
            lambda: protocol, sys.stdout
        )
        writer = asyncio.StreamWriter(transport, protocol, reader, loop)
        r_protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: r_protocol, sys.stdin)


        async def handle_msg(cm: ChatMessage):
            msg = f"{cm.nickname}@{cm.room}: {cm.message}\n>" 
            writer.write(msg.encode())
            await writer.drain()
        chat_user.add_event_listener(ChatEvent.message, handle_msg)




        if len(sys.argv) == 2:
            # print("friend_dest:")
            # friend_dest = await reader.read(BUFFER_SIZE) #input("friend_dest: ")
            # friend_dest = friend_dest.decode()[:-1]
            friend_dest = sys.argv[1] 
            print("friend_dest:",friend_dest)
            await chat_user.add_friend(friend_dest)
            print("======================================")
            print(test_config.friends)
            print("======================================")

            # ".b32.i2p"
            await chat_user.create_room("test_room", [friend_dest, chat_user.node.destination.base32])

            print("======================================")
            print(test_config.rooms)
            print("======================================")
    

        while True:
            # print(">",end="")
            
            writer.write(">".encode())
            await writer.drain()
            # await 
            friend_dest = await reader.readline() #input("friend_dest: ")
            friend_dest = friend_dest.decode()[:-1]

            await chat_user.send("test_room", friend_dest)

            
    try:
        loop.create_task(main(loop=loop))
        loop.run_forever()
    finally:

        loop.stop()
        loop.close()

    print("HELL...")