import i2plib
from typing import Literal, NotRequired, TypedDict, Dict
from dataclasses import dataclass
import asyncio
import logging
import random
import sys
from urllib.parse import urlparse


from typing import Callable, Awaitable, Any
from asyncio import StreamReader, StreamWriter

StreamHandler = Callable[[bytes, StreamReader, StreamWriter], Awaitable[Any]]

"""
opt = {
    "session_name": "example_name",
    "sam_address": ("127.0.0.1", 7656),
    "private_key": "key.pem",

    "tunnels": {
        "serverTunnel": [("127.0.0.1", 6660)], # только 1
        "clientTunnel": [("kal_lala.i2p",("127.0.0.1", 6660))] # not imp
    }
}
"""
logger = logging.getLogger(__package__)
BUFFER_SIZE = 4096


class i2pTunnelsOpt(TypedDict):
    serverTunnel: list[tuple[str, int]]
    clientTunnel: list[tuple[str, tuple[str, int]]]

    def __repr__(self):
        return f"serverTunnel: {self.serverTunnel}\nclientTunnel: {self.clientTunnel}"

class i2pNodeOpt(TypedDict):
    session_name: str 
    sam_address: tuple
    private_key: str
    # streams: list[str] 
    tunnels: i2pTunnelsOpt


class i2pPubSub:
    topics: list[str] = []

    def __init__(self):
        pass

    def subscribe(topic: str):
        raise "not imp"

    def handle(topic: str, handler):
        raise "not imp"

    def publish(topic: str, msg: str):
        raise "not imp"

class i2pReqests:
    session_name: str
    sam_address: tuple[str, int]
    loop: asyncio.AbstractEventLoop

    def __init__(self, session_name: str,
                 sam_address: tuple[str, int],
                 loop: asyncio.AbstractEventLoop):
        self.session_name = session_name
        self.sam_address = sam_address
        self.loop = loop
        

    async def get(self, url: str)->str:
        url = urlparse(url)
        buflen, resp = 4096, b""

        async with i2plib.StreamConnection(session_name=self.session_name,
                                           destination= url.netloc, 
                                           loop=self.loop, 
                                            sam_address=self.sam_address) as c:
                    reqest_str = f"GET {url.path} HTTP/1.1\n"
                    reqest_str+= f"Host: {url.netloc}\n"

                    c.write(reqest_str.encode())

                    while True:
                        data = await c.read(buflen)
                        if len(data) > 0:
                            resp += data
                        else:
                            break
        try:
            return resp.split(b"\r\n\r\n", 1)[1].decode()
        except IndexError:
            return resp.decode()
        
    
    async def post(self, url:str, body:str=None)->str:
        url = urlparse(url)
        buflen, resp = 4096, b""

        async with i2plib.StreamConnection(session_name=self.session_name,
                                           destination= url.netloc, 
                                           loop=self.loop, 
                                            sam_address=self.sam_address) as c:
                reqest_str = f"POST {url.path} HTTP/1.1\n"
                reqest_str+= f"Host: {url.netloc}\n"

                if body != None:
                    reqest_str+= f"Content-Type: application/json"
                    reqest_str+= f"Content-Length: {len(body)}\r\n\r\n"
                    reqest_str+= body

                c.write(reqest_str.encode())

                while True:
                    data = await c.read(buflen)
                    if len(data) > 0:
                        resp += data
                    else:
                        break
        try:
            return resp.split(b"\r\n\r\n", 1)[1].decode()
        except IndexError:
            return resp.decode()
    


class i2pNode:
    reqests: i2pReqests
    pubsub: i2pPubSub
    opt: i2pNodeOpt
    destination: i2plib.Destination
    loop: asyncio.AbstractEventLoop

    handlers: Dict[str, StreamHandler] = {}
    __stream_loop__: asyncio.Task = None
    __ServerTunnel_tunnels__: list[i2plib.ServerTunnel] = []

    def __init__(self, opt: i2pNodeOpt, loop: asyncio.AbstractEventLoop=None):
        self.opt = opt
        self.loop = loop
        
        pass

    def stop(self):
        self.__stream_loop__.cancel()
        

    async def start(self):
        if self.opt.get("session_name") == None:
            self.opt.update(session_name= f"session_{random.randint(0,99999999999999)}")
    
        logger.debug("start node "+self.opt.get("session_name"))
        
        if self.opt.get("sam_address") == None:
            self.opt.update(sam_address=i2plib.get_sam_address())

        if self.opt.get("private_key") != None:
            self.destination = i2plib.Destination(path=self.opt.get("private_key"), has_private_key=True)
        else:
            self.destination = await i2plib.new_destination(loop=self.loop, sam_address=self.opt.get("sam_address"))

        ######################################################
        await i2plib.create_session(session_name=self.opt.get("session_name"),
                                    sam_address=self.opt.get("sam_address"),
                                    destination=self.destination,
                                    loop=self.loop)
        ######################################################
        self.reqests = i2pReqests(session_name=self.opt.get("session_name"), 
                                  sam_address=self.opt.get("sam_address"),
                                  loop=self.loop)

        # if self.opt.get("streams") != None:
        self.__stream_loop__ = asyncio.ensure_future(self.__run_stream__(), loop=self.loop)
            # pass
        
        if self.opt.get("tunnels") != None:
            if self.opt.get("tunnels").get("serverTunnel") != None:
                for t in self.opt.get("tunnels").get("serverTunnel"):
                    tunnel = i2plib.ServerTunnel(t, destination=self.destination, sam_address=i2plib.get_sam_address(), loop=self.loop)
                    self.__ServerTunnel_tunnels__.append(asyncio.ensure_future(tunnel.run(), loop=self.loop))
                    pass
        
    
    async def __run_stream__(self):
        logger.debug("start node stream "+self.opt.get("session_name"))
        async def __handle_connect__(incoming: bytes, reader: StreamReader, writer: StreamWriter):
            name = await client_reader.read(BUFFER_SIZE)
            if self.handlers.get(name.decode()) == None:
                writer.write(b"no name...")    
                await writer.drain()
                return
            
            writer.write(b"ok")
            await writer.drain()
            # print("incoming from:", i2plib.Destination(incoming.decode().strip()).base32)
            # print("protocol name:", name.decode())
            asyncio.ensure_future(self.handlers[name.decode()](incoming, reader, writer), loop=self.loop)
            pass

        try:
            while True:
                try:
                    client_reader, client_writer = await i2plib.aiosam.stream_accept(session_name=self.opt.get("session_name"),
                                                                                     sam_address=self.opt.get("sam_address"),
                                                                                     )
                    incoming = await client_reader.read(BUFFER_SIZE)
                    asyncio.ensure_future(__handle_connect__(incoming, client_reader, client_writer), loop=self.loop)
                except Exception as error:
                    logger.exception(f"stream stream_accept exception: {error}")        
        except Exception as error:
            logger.exception(f"stream loop exception: {error}")
            

    def handle(self, name: str, handler: StreamHandler):
        logger.debug(f"handle node stream "+name)
        self.handlers[name] = handler
        pass

    async def dialProtocol(self, dest: str, name: str) -> tuple[StreamReader, StreamWriter]:
        reader, writer = await i2plib.stream_connect(session_name= self.opt.get("session_name"), 
                                                     destination= dest, 
                                                     sam_address=self.opt.get("sam_address"), 
                                                     loop=self.loop)
        writer.write(name.encode())
        await writer.drain()
        status = await reader.read(BUFFER_SIZE)

        if status == b"ok":
            return (reader, writer)
        raise "node stream dial err!!!"

    def __repr__(self):
        return f"opt: {self.opt}"
    


async def create_i2pNode(opt: i2pNodeOpt={}, loop: asyncio.AbstractEventLoop=None):
    logger.debug("create_i2pNode")
    return i2pNode(opt, loop=loop)
    




    

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    loop = asyncio.get_event_loop()
    loop.set_debug(True)

    async def main(loop: asyncio.AbstractEventLoop=None):
        node = await create_i2pNode(opt={
            "streams": ["test"],
            # "tunnels": {
            #     "serverTunnel": [
            #         ("127.0.0.1", 6660)
            #     ]
            # }
        }, loop=loop)
        print(node)
        async def th(inc: bytes, r: StreamReader, w: StreamWriter):
            print(inc)
            remote_destination = i2plib.Destination(inc.decode().strip())
            while True:
                msg = await r.read(BUFFER_SIZE)
                print(remote_destination.base32,msg)
                w.write(b"PONG")

        node.handle("test", th)

        print(node.handlers)
        # await node.handlers["test"](None,None,None)
        # node.handlers["test"](b"wwww", None, None)
        
        
        await node.start()
        print("===========================================")
        print("DEST:",node.destination)
        print("===========================================")
        
        if len(sys.argv) == 2:
            r, w = await node.dialProtocol(sys.argv[1], "test")
            while True:
                w.write(b"PING")
                msg = await r.read(BUFFER_SIZE)
                print(sys.argv[1],msg)
            pass




    # loop.run_until_complete(create_i2pNode())
    try:
        loop.create_task(main(loop=loop))
        loop.run_forever()
    finally:

        loop.stop()
        loop.close()

    print("HELL...")