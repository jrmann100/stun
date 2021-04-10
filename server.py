import asyncio
import json
from snowball import snowball
from stun import req2res_bytes as create_stun_response
from typing import List, Set, Dict, Tuple, Optional, Callable

import aiohttp
import aiohttp.web as web

HOST = '0.0.0.0'

async def start_http_server():
    print('HTTP/WS...', end=' ')
    app = web.Application()
    app.add_routes(
        [web.get("/", lambda request: web.FileResponse('./static/chat.html'))])
    app.add_routes([web.static('/static', 'static')])
    app.router.add_route('GET', '/ws', ws_main)
    app.on_shutdown.append(http_shutdown)
    app['websockets']: Dict[str, aiohttp.web.WebSocketResponse] = {}
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, 5000)
    await site.start()
    print('ready.', end=' ')
    return runner


class StunProtocol(asyncio.DatagramProtocol):
    def __init__(self):
        self.transport = None

    def connection_made(self, transport: asyncio.BaseTransport):
        print('ready.', end=' ')
        self.transport = transport

    def datagram_received(self, buf: bytes, addr: Tuple[str, int]):
        print('STUN <', *addr, buf.hex())
        res = create_stun_response(buf, *addr)
        print('STUN >', *addr, res.hex())
        self.transport.sendto(res, addr)

    def connection_lost(self, exc):
        print('STUN shut down.', end=' ')


async def ws_main(request: web.Request):
    clients = request.app['websockets']
    address = request.transport.get_extra_info('peername')
    print('\nWS  <>', *address, end=' ')
    ws = aiohttp.web.WebSocketResponse()
    await ws.prepare(request)
    print('ready')

    my_id = snowball()
    clients[my_id] = ws

    async def send(typ, body={}, error=None, client=ws):
        await client.send_str(json.dumps(
            {'type': typ, **({'error': error} if error !=
                             None else {'body': body})}
        ))
        # Probably should log this, but it gets so chaotic.
        # Ideally we'd append to end of lines, but sometimes we send
        # two responses to one request and newlines get messy.
        # print('WS   >', *client._req.transport.get_extra_info('peername'), typ)

    await send('id', {'id': my_id})

    async for ws_msg in ws:
        if ws_msg.type != aiohttp.WSMsgType.TEXT:
            print('Warning: got unsupported WS frame type', msg.type)
            return

        try:
            msg = json.loads(ws_msg.data)
        except json.decoder.JSONDecodeError:
            await send('error', error='Request not JSON.')

        if not 'type' in msg:
            await send('error', error='Expected {type, body}.')
            continue

        typ = msg['type']
        body = msg['body'] if 'body' in msg else None

        print('WS   <', *address, typ)

        async def reply(body={}, error=None):
            await send(typ, body, error)

        if typ == 'id':
            await reply({'id': my_id})
        if typ == 'change_id':
            # should probably validate
            if body['id'] in clients:
                await reply(error='ID {} already taken.'.format(body['id']))
            else:
                # This may break ICE!
                # Todo: need to check and update your_id by tracking live calls.
                # Alternately, have an index of changed ids.
                del clients[my_id]
                my_id = body['id']
                clients[my_id] = ws
                await reply({'id': my_id})
        elif typ == 'ping':
            await reply({'ping': 'pong'})
        elif typ == 'your_id':
            await reply(bool(body['id'] in clients))
        elif typ in ['offer', 'answer', 'candidate']:
            if body['id'] in clients:
                # Realistically, we should track live calls, so the proxying only works between approved peers.
                await send(typ + '_from', {**body, 'id': my_id}, client=clients[body['id']])
                await reply({'id': body['id']})
            else:
                # This shouldn't happen.
                await send(typ, error='Signaling error: no client with ID {}.'.format(body['id']))
    del clients[my_id]
    print('WS   x', *address)
    return ws


async def http_shutdown(app):
    print('HTTP/WS...')  # , end=' ')
    while len(app['websockets']) > 0:
        await list(app['websockets'].values())[0].close(aiohttp.WSCloseCode.SERVICE_RESTART, 'Server going down for maintenance.')
    print('shut down.', end=' ')


async def start_stun_server():
    print('STUN...', end=' ')
    stun_transport, _stun_protocol = await asyncio.get_event_loop().create_datagram_endpoint(
        lambda: StunProtocol(),
        local_addr=(HOST, 3478))
    return stun_transport


def main():
    loop = asyncio.get_event_loop()
    print('Booting', end=' ')
    stun_transport = loop.run_until_complete(start_stun_server())
    http_server = loop.run_until_complete(start_http_server())
    print('Booted.')
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        stun_transport.close()
        loop.run_until_complete(http_server.cleanup())
        print('Goodbye.')
        loop.stop()


if __name__ == '__main__':
    main()
