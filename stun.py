# Messy, cheap, somewhat more RFC 8489-compliant STUN server by Jordan Mann

from socket import socket, AF_INET, SOCK_DGRAM
from struct import pack, unpack_from, calcsize


if __name__ == '__main__':
    # Setup server
    server = socket(AF_INET, SOCK_DGRAM) # use internet with UDP
    server.bind(('0.0.0.0', 3478))

    while True:
        buf, (address, port) = server.recvfrom(65535)
        print('<', buf.hex())
        # message_type is interpreted as an integer so we can convert it to bits
        message_header_format = '!H H 4s 12s'
        message_type_num, message_length, magic_cookie, transaction_id = unpack_from(message_header_format, buf, 0)
        message_type_bits = bin(message_type_num)[2:].zfill(16)
        if message_type_bits[:2] != '00':
            print('Warning: request not STUN - most signifigant 2 bits must be zeroes.')
        message_type_class = message_type_bits[7] + message_type_bits[11]
        message_type_method = message_type_bits[2:7] + message_type_bits[8:11] + message_type_bits[12:]
        if message_type_method != '000000000001':
            print('Warning: method not of type Binding')
        if message_type_class != '00':
            print('Error: class not of type request.')
            continue
        message = unpack_from('!{}s'.format(message_length), buf, calcsize(message_header_format))[0]
        if magic_cookie != bytes.fromhex('2112A442'):
            print('Warning: request not RFC 8489 compilant.')
        message_read = 0
        change_port = False
        change_address = False
        while message_read < message_length:
            attribute_header_format = '!2s H'
            attribute_type, attribute_length = unpack_from('!2s H', message, message_read)
            message_read += calcsize(attribute_header_format)
            attribute = unpack_from('!{}s'.format(attribute_length), message, message_read)[0]
            message_read += attribute_length
            if attribute_type.hex() == '0003': # change request
                change_port, change_address = list(bool(bit) for
                        bit in bin(unpack_from('!s', attribute, 3)[0][0])[1:3])
                # unpack the last byte into tuple of bytes, take the byte, read bits 1 and 2
            print('attr type {} val {}'.format(attribute_type.hex(), attribute.hex()))


        resp = pack(
            '!2s H 4s 12s  2s H  x s H 4B',
            bytes.fromhex('0101'),
            12, # predetermined length
            magic_cookie,
            transaction_id,
            bytes.fromhex('0001'), # mapped address,
            8, # predetermined length
            bytes.fromhex('01'), # IPv4
            port,
            *list(int(octal) for octal in address.split('.'))
        )
        print('>', resp.hex())
        server.sendto(resp, (address, port))
