# cheapest possible functioning STUN server

import socket
from struct import pack, unpack

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # internet, UDP
sock.bind(('0.0.0.0', 3478))

def compose_binding_response(parsed_stun, t_id):
    return pack('!2s H 16s  2s H  x s H 4B',
            # ! represents network byte order.
            # H is an unsigned short - two bytes.
            # B is an unsigned char - one byte.

            # header
            bytes.fromhex('0101'), # type: binding response.
            12, # length
            # length is dynamic, but we're only sending
            # the mapped response to cut corners
            bytes.fromhex(t_id),

            # message header
            bytes.fromhex('0001'), # type: mapped address
            8,

            # message
            bytes.fromhex('01'), # address family = IPv4 = 0x01
            addr[1], # port
            *list(int(oct) for oct in addr[0].split('.')))
            # IP address, in 2-byte chunks

if __name__ == '__main__':
    while True:
        buf, addr = sock.recvfrom(65535)
        print('buf!', buf.hex())
        message_type, payload_length, transaction_id = unpack('!2s h 16s', buf)
        if parsed_stun['type'] == '0001': # binding request
            sock.sendto(compose_binding_response(parsed_stun, addr), addr)
        else: print('Did not recognize type, not sending response.')
