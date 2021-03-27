# Poor but somewhat well-formatted STUN implementation by Jordan Mann
# keep in mind that it doesn't error-trap or form error responses.
from struct import pack, unpack_from, calcsize
from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Optional
# from warnings import warn # Don't think this works how I expect it to.


@dataclass
class StunPacket:
    """Dataclass representing STUN packet.
    """
    type_class: str  # bits as '00'
    type_method: str  # bits as '000000000000'
    magic_cookie: bytes  # 4 bytes; should be 0x2112A442
    transaction_id: bytes  # 12 bytes
    message: Dict[bytes, bytes]  # attr [type: length]


# Type is numeric so it can be easily converted to bits.
HEADER_FORMAT = '!H H 4s 12s'
ATTRIBUTE_HEADER_FORMAT = '!2s H'
ADDRESS_FORMAT = '!x s H 4B'


def bytes2obj(buf: bytes) -> StunPacket:
    """Unpack STUN packet into StunPacket object.

    Args:
        buf (bytes): STUN request packet, in bytes.

    Raises:
        Exception: Various malformed packet issues. Designed to be RFC 3489/8489 compliant.

    Returns:
        StunPacket: The packet data, unpacked.
    """

    type_raw, length, magic_cookie, transaction_id = unpack_from(
        HEADER_FORMAT, buf, 0)

    # Convert message type into bits, to parse it as a class and method.
    type_bits: str = bin(type_raw)[2:].zfill(16)
    if type_bits[:2] != "00":
        raise Exception(
            "STUN packet invalid - most signifigant 2 bits must be zeroes.")
    type_class = type_bits[7] + type_bits[11]
    type_method = type_bits[2:7] + type_bits[8:11] + type_bits[12:]

    message_bytes = unpack_from('!{}s'.format(
        length), buf, calcsize(HEADER_FORMAT))[0]
    # if magic_cookie != bytes.fromhex("2112A442"):
    #     print("Warning: Request not RFC 8489 compilant.")

    message_read = 0
    message: Dict[bytes, bytes] = {}
    while message_read < length:
        attribute_type, attribute_length = unpack_from(
            ATTRIBUTE_HEADER_FORMAT, message_bytes, message_read
        )
        attribute_val = unpack_from(
            "!{}s".format(attribute_length), message_bytes, message_read +
            calcsize(ATTRIBUTE_HEADER_FORMAT)
        )[0]
        message[attribute_type] = attribute_val

        message_read += calcsize(ATTRIBUTE_HEADER_FORMAT)
        message_read += attribute_length

    return StunPacket(type_class, type_method, magic_cookie, transaction_id, message)


def obj2bytes(obj: StunPacket) -> bytes:
    """Pack StunPacket object into STUN packet.

    Args:
        obj (StunPacket): The packet data, unpacked.

    Returns:
        bytes: The packet, packed.
    """

    message = bytes()
    for [attribute_type, attribute_val] in obj.message.items():
        message += pack(
            '{}{}s'.format(ATTRIBUTE_HEADER_FORMAT, len(attribute_val)),
            attribute_type,
            len(attribute_val),
            attribute_val,
        )

    type_bits = (
        '00'
        + obj.type_method[0:5]
        + obj.type_class[0]
        + obj.type_method[5:8]
        + obj.type_class[1]
        + obj.type_method[8:]
    )
    return pack(
        '{}{}s'.format(HEADER_FORMAT, len(message)),
        int(type_bits, 2),
        len(message),
        obj.magic_cookie,
        obj.transaction_id,
        message,
    )


def req2res_obj(req: StunPacket, address: str, port: int) -> StunPacket:
    """Create STUN binding response from binding request.

    Args:
        req (StunPacket): The request object.
        address (str): Client's IPv4 address.
        port (int): Client's port.

    Returns:
        StunPacket: The binding response object.
    """

    if req.type_method != '000000000001':
        raise Exception('STUN request method not of type binding')
    if req.type_class != '00':
        raise Exception('STUN request class not of type request.')
    message: Dict[bytes, bytes] = {}
    # mapped address
    message[pack(ATTRIBUTE_HEADER_FORMAT, bytes.fromhex('0001'), calcsize(ADDRESS_FORMAT))] = pack(
        ADDRESS_FORMAT,
        bytes.fromhex('01'),  # IPv4
        port,  # port
        *list(int(octal) for octal in address.split('.')))

    # for [attr_type, attr_value] in req.message.items(): # need to handle request args!
    # if attr_type.hex() == "0003":  # change request
    # unpack the last byte into tuple of bytes, take the byte, read bits 1 and 2
    #   change_port, change_address = list(bool(bit) for bit in bin(
    #       unpack_from("!s", attribute, 3)[0][0])[1:3])

    return StunPacket('10', req.type_method, req.magic_cookie, req.transaction_id, message)


def req2res_bytes(buf: bytes, address: str, port: int) -> bytes:
    return obj2bytes(req2res_obj(bytes2obj(buf), address, port))


# Can be used for testing.
if __name__ == '__main__':
    from socket import socket, AF_INET, SOCK_DGRAM
    server = socket(AF_INET, SOCK_DGRAM)  # use internet, with UDP
    server.bind(('0.0.0.0', 3478))
    while True:
        buf, (address, port) = server.recvfrom(65535)
        server.sendto(req2res_bytes(buf, address, port), (address, port))
