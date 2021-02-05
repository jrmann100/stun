# Cheapest possible STUN server by Jordan Mann

from socket import socket, AF_INET, SOCK_DGRAM
from struct import pack, unpack_from

sock = socket(AF_INET, SOCK_DGRAM) # internet, UDP
sock.bind(('0.0.0.0', 3478))

if __name__ == '__main__':
    while True:
        buf, (address, port) = sock.recvfrom(65535)
        print('<', buf.hex())
        message_type, message_length, transaction_id = unpack_from('!2s h 16s', buf, 0)
        # message = unpack_from('!{}s'.format(message_length), buf, 20)[0]
        if message_type == bytes.fromhex('0001'): # binding request
            resp = pack(
                '!2s H 16s  2s H  x s H 4B',
                bytes.fromhex('0101'), # binding response
                12, # predetermined length
                transaction_id,
                bytes.fromhex('0001'), # mapped address,
                8, # predetermined length
                bytes.fromhex('01'), # IPv4
                port,
                *list(int(octal) for octal in address.split('.'))
            )
            print('>', resp.hex())
            sock.sendto(resp, (address, port))
        else:
            print('Ignoring unsupported request')
