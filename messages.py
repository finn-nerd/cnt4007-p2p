# All message classes, including functions to translate to/from bytes.

import struct

HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"  # 18 bytes
HANDSHAKE_LENGTH = 32 # 18 header + 10 zeros + 4 peer id

# message type values
CHOKE = 0
UNCHOKE = 1
INTERESTED = 2
NOT_INTERESTED = 3
HAVE = 4
BITFIELD = 5
REQUEST = 6
PIECE = 7


# Translates payload bytes into usable Message class
def parse_message(msg_type, payload, num_pieces):
    if msg_type == CHOKE:
        return Choke()
    elif msg_type == UNCHOKE:
        return Unchoke()
    elif msg_type == INTERESTED:
        return Interested()
    elif msg_type == NOT_INTERESTED:
        return NotInterested()
    if msg_type == HAVE:
        return Have.from_payload(payload)
    if msg_type == BITFIELD:
        return Bitfield.from_payload(payload, num_pieces)
    if msg_type == REQUEST:
        return Request.from_payload(payload)
    if msg_type == PIECE:
        return Piece.from_payload(payload)
    raise ValueError(f"unknown message type {msg_type}")


class Handshake:
    def __init__(self, peer_id):
        self.peer_id = peer_id

    def to_bytes(self):
        # 18-byte header + 10 zero bytes + 4-byte peer id = 32 bytes
        return HANDSHAKE_HEADER + b"\x00" * 10 + struct.pack(">I", self.peer_id)

    @staticmethod
    def from_bytes(data):
        if len(data) != HANDSHAKE_LENGTH:
            raise ValueError(f"handshake should be {HANDSHAKE_LENGTH} bytes, got {len(data)}")
        if data[:18] != HANDSHAKE_HEADER:
            raise ValueError("bad handshake header")
        peer_id = struct.unpack(">I", data[28:32])[0]
        return Handshake(peer_id)

    def __repr__(self):
        return f"Handshake({self.peer_id})"


class Message:
    # base class. subclasses set msg_type and override payload() if they have one
    msg_type = None

    def payload(self):
        # no payload by default
        return b""

    # convert message to bytes for TCP sending
    def to_bytes(self):
        payload = self.payload()
        length = 1 + len(payload) # 1 type + n payload
        return struct.pack(">IB", length, self.msg_type) + payload

    def __repr__(self):
        return f"{self.__class__.__name__}()"


# --- messages with no payload ---

class Choke(Message):
    msg_type = CHOKE


class Unchoke(Message):
    msg_type = UNCHOKE


class Interested(Message):
    msg_type = INTERESTED


class NotInterested(Message):
    msg_type = NOT_INTERESTED


# --- messages with a payload ---

class Have(Message):
    msg_type = HAVE

    def __init__(self, piece_index):
        self.piece_index = piece_index

    def payload(self):
        return struct.pack(">I", self.piece_index)

    @staticmethod
    def from_payload(data):
        if len(data) != 4:
            raise ValueError(f"have payload should be 4 bytes, got {len(data)}")
        piece_index = struct.unpack(">I", data)[0] # interpret raw payload
        return Have(piece_index) # return packaged Message

    def __repr__(self):
        return f"Have({self.piece_index})"


class Bitfield(Message):
    msg_type = BITFIELD

    def __init__(self, bitfield):
        # list of bools, one per piece (same as Peer.bitfield)
        self.bitfield = bitfield

    def payload(self):
        data = bytearray((len(self.bitfield) + 7) // 8) # round up to whole bytes
        for i, has_piece in enumerate(self.bitfield):
            if has_piece: # translate bools -> bits
                data[i // 8] |= 1 << (7 - i % 8)
        return bytes(data)

    @staticmethod
    def from_payload(data, num_pieces):
        # note: num_pieces needed to ignore spare bits at end
        expected = (num_pieces + 7) // 8
        if len(data) != expected:
            raise ValueError(f"bitfield payload is {len(data)} bytes, expected {expected}")
        bitfield = []
        for i in range(num_pieces):
            bitfield.append(bool((data[i // 8] >> (7 - i % 8)) & 1))
        return Bitfield(bitfield)

    def __repr__(self):
        return f"Bitfield({sum(self.bitfield)} pieces)"


class Request(Message):
    msg_type = REQUEST

    def __init__(self, piece_index):
        self.piece_index = piece_index

    def payload(self):
        return struct.pack(">I", self.piece_index)

    @staticmethod
    def from_payload(data):
        if len(data) != 4:
            raise ValueError(f"request payload should be 4 bytes, got {len(data)}")
        piece_index = struct.unpack(">I", data)[0] # interpret raw payload
        return Request(piece_index) # return packaged Message

    def __repr__(self):
        return f"Request({self.piece_index})"


class Piece(Message):
    msg_type = PIECE

    def __init__(self, piece_index, data):
        self.piece_index = piece_index
        self.data = data  # raw bytes of the piece

    def payload(self):
        return struct.pack(">I", self.piece_index) + self.data

    @staticmethod
    def from_payload(data):
        if len(data) <= 4: # require index + non-empty file piece
            raise ValueError(f"piece payload should be at least 5 bytes, got {len(data)}")
        piece_index = struct.unpack(">I", data[:4])[0] # first 4 bytes = index
        return Piece(piece_index, data[4:]) # data[4:] is file piece bytes

    def __repr__(self):
        return f"Piece({self.piece_index}, {len(self.data)} bytes)"
