import asyncio
import websockets
import json
from snowball import snowball
from stun import req2res_bytes as create_stun_response
from typing import List, Set, Dict, Tuple, Optional, Callable

import aiohttp
import aiohttp.web as web

HOST = '0.0.0.0'


async def start_http_server():
    print('Starting HTTP...', end=' ')
    app = web.Application()
    app.add_routes(
        [web.get("/", lambda request: web.FileResponse('./app.html'))])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, 5000)
    await site.start()
    print('HTTP ready.', end=' ')
    return runner


class StunProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None

    def connection_made(self, transport: asyncio.BaseTransport):
        print('STUN ready.', end=' ')
        self.transport = transport

    def datagram_received(self, buf: bytes, addr: Tuple[str, int]):
        print('STUN <', *addr, buf.hex())
        res = create_stun_response(buf, *addr)
        print('STUN >', *addr, res.hex())
        self.transport.sendto(res, addr)

    def connection_lost(self, exc):
        print('STUN shut down.')


clients: Dict[str, websockets.WebSocketServerProtocol] = {}


async def websocket_main(websocket: websockets.WebSocketServerProtocol, path):
    # my_id = str(uuid4())
    my_id = snowball()
    clients[my_id] = websocket

    async def send(typ, body, websocket=websocket): await websocket.send(
        json.dumps({'type': typ, 'body': body}))

    async for text in websocket:
        try:
            msg = json.loads(text)
        except json.decoder.JSONDecodeError:
            await send('error', 'Request not JSON.')

        if not 'type' in msg:
            await send('error', 'Expected {type, body}.')
            continue

        typ = msg['type']
        body = msg['body'] if 'body' in msg else None

        print('WS   <', *websocket.remote_address, typ)

        async def reply(body): await send(typ, body)

        if typ == 'get_id':
            await reply(my_id)
        elif typ == 'ping':
            await reply('pong')
        elif typ == 'peer':
            await reply(bool(body['peer'] in clients))
        elif typ in ['offer', 'answer', 'candidate']:
            if body['id'] in clients:
                # Realistically, we should track live calls, so the proxying only works between approved peers.
                await send(typ, {**body, 'id': my_id}, clients[body['id']])
            else:
                await send('signaling_error', 'Signaling error: no client with ID {}.'.format(body['id']))

    del clients[my_id]


async def start_stun_server():
    print('Starting STUN...', end=' ')
    stun_transport, _stun_protocol = await asyncio.get_event_loop().create_datagram_endpoint(
        lambda: StunProtocol(),
        local_addr=(HOST, 3478))
    return stun_transport


async def start_ws_server():
    print('Starting WS...', end=' ')
    ws_server = await websockets.serve(websocket_main, HOST, 8765)
    print('WS ready.', end=' ')
    return ws_server


def main():
    loop = asyncio.get_event_loop()
    stun_transport = loop.run_until_complete(start_stun_server())
    ws_server = loop.run_until_complete(start_ws_server())
    http_server = loop.run_until_complete(start_http_server())
    print('All servers ready.')
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print('Stopping all servers...', end=' ')
        stun_transport.close()
        ws_server.close()
        loop.run_until_complete(http_server.cleanup())
        print('all servers stopped. Goodbye.')
        loop.stop()


if __name__ == '__main__':
    main()
