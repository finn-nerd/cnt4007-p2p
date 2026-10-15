# The Peer class: sets up the server socket, connects to the other peers,
# and keeps track of all the connections and which pieces we have.

import logging
import os
import socket
import threading
import time

from connection import PeerConnection
from messages import Handshake, HANDSHAKE_LENGTH

RETRIES = 10       # how many times to try connecting to a peer
RETRY_DELAY = 1    # seconds between tries


def make_logger(peer_id):
    # writes to log_peer_[peerID].log in the current directory
    logger = logging.getLogger(f"peer_{peer_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(f"log_peer_{peer_id}.log", mode="w")
        handler.setFormatter(logging.Formatter("[%(asctime)s]: %(message)s",
                                               "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    return logger


class Peer:
    def __init__(self, peer_id, common, peers):
        self.peer_id = peer_id
        self.common = common
        self.peers = peers

        # find our own line in PeerInfo.cfg
        self.info = None
        for p in peers:
            if p.peer_id == peer_id:
                self.info = p
        if self.info is None:
            raise ValueError(f"peer {peer_id} is not in PeerInfo.cfg")

        self.folder = f"peer_{peer_id}"
        self.logger = make_logger(peer_id)

        # True/False for each piece. if we start with the file we have all of them
        self.bitfield = [self.info.has_file] * common.num_pieces
        self.bitfield_lock = threading.Lock()

        # bitfields the other peers send us, peer_id -> list of bools
        self.neighbor_bitfields = {}

        # connections where we know the other peer's id
        self.connections = {}
        # incoming connections that haven't finished the handshake yet
        self.pending = []
        self.conn_lock = threading.Lock()

        self.server = None
        self.done = threading.Event()

    def peers_before_me(self):
        # we connect to everyone listed above us
        result = []
        for p in self.peers:
            if p.peer_id == self.peer_id:
                break
            result.append(p)
        return result

    def peers_after_me(self):
        # everyone listed below us will connect to us
        index = self.peers.index(self.info)
        return self.peers[index + 1:]

    def has_whole_file(self):
        with self.bitfield_lock:
            return all(self.bitfield)

    def start(self):
        self.setup_folder()
        self.start_server()
        self.connect_to_peers()

    def setup_folder(self):
        os.makedirs(self.folder, exist_ok=True)

        if self.info.has_file:
            # make sure the file is actually there before we start
            path = os.path.join(self.folder, self.common.file_name)
            if not os.path.exists(path):
                raise ValueError(f"peer {self.peer_id} should have the file but {path} doesn't exist")
            size = os.path.getsize(path)
            if size != self.common.file_size:
                raise ValueError(f"{path} is {size} bytes but Common.cfg says {self.common.file_size}")

    def start_server(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # lets us restart right away without "address already in use"
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("", self.info.port))
        self.server.listen(len(self.peers))

        t = threading.Thread(target=self.accept_loop, daemon=True)
        t.start()
        print(f"Peer {self.peer_id} listening on port {self.info.port}")

    def accept_loop(self):
        while not self.done.is_set():
            try:
                sock, addr = self.server.accept()
            except OSError:
                break  # server got closed, we're shutting down

            conn = PeerConnection(self, sock, None, False)
            with self.conn_lock:
                self.pending.append(conn)
            conn.start()

    def connect_to_peers(self):
        for p in self.peers_before_me():
            sock = self.try_connect(p)
            if sock is None:
                print(f"Peer {self.peer_id} couldn't connect to peer {p.peer_id} at {p.host}:{p.port}")
                continue

            conn = PeerConnection(self, sock, p.peer_id, True)
            self.add_connection(conn)
            self.logger.info(f"Peer {self.peer_id} makes a connection to Peer {p.peer_id}.")
            conn.start()

    def try_connect(self, p):
        # the other peer might not be listening yet so retry a few times
        for i in range(RETRIES):
            if self.done.is_set():
                return None
            try:
                return socket.create_connection((p.host, p.port), timeout=5)
            except OSError:
                time.sleep(RETRY_DELAY)
        return None

    def add_connection(self, conn):
        # call this once we know conn.remote_id
        with self.conn_lock:
            if conn in self.pending:
                self.pending.remove(conn)
            self.connections[conn.remote_id] = conn
        conn.sock.settimeout(None)  # create_connection set a timeout, we don't want it after connecting

    def run(self):
        # main thread just waits here until we're told to stop
        try:
            while not self.done.is_set():
                self.done.wait(1)
        except KeyboardInterrupt:
            print(f"\nPeer {self.peer_id} interrupted")
        finally:
            self.stop()

    def stop(self):
        if self.done.is_set() and self.server is None:
            return  # already stopped
        self.done.set()

        if self.server:
            try:
                self.server.close()
            except OSError:
                pass
            self.server = None

        with self.conn_lock:
            all_conns = list(self.connections.values()) + self.pending
        for conn in all_conns:
            conn.close()
        print(f"Peer {self.peer_id} stopped")

    # these get called by the connection's reader thread

    def on_connect(self, conn):
        # handshake: send/receive the handshake message between peers

        # initialize handshake message with peer's id
        handshake = Handshake(self.peer_id)

        # if peer connection is outgoing, send the handshake message and wait to recieve the handshake ack from other peer
        if conn.outgoing:
            conn.send(handshake.to_bytes())

            ack_msg = conn.recv_exact(HANDSHAKE_LENGTH)

            # get other peer's id from the ack message
            other_id = handshake.from_bytes(ack_msg).peer_id

            # verify whether other_id from ack_msg is the same id as the id of the peer in the connection
            if other_id != conn.remote_id:
                raise ValueError(f"Expected neighbor id ({conn.remote_id}) does not match received neighbor id ({other_id}).")

            return
        # otherwise, wait for a handshake message and send an ack message to other peer
        else:
            recieved_msg = conn.recv_exact(HANDSHAKE_LENGTH)

            other_id = handshake.from_bytes(recieved_msg).peer_id

            # verify that other_id from received_msg is the same id as the id of the peer in the connection
            if other_id not in [p.peer_id for p in self.peers_after_me()]:
                raise ValueError(f"Unexpected peer ID: {other_id}")

            # set the connection's remote_id and add connection to this peer's connections
            conn.remote_id = other_id
            self.add_connection(conn)

            conn.send(handshake.to_bytes())

            self.logger.info(
                f"Peer {self.peer_id} is connected from Peer {other_id}."
            )

            return

    def handle_message(self, conn):
        # read one message and handle it based on its type

        msg_len = int.from_bytes(conn.recv_exact(4), byteorder="big")

        # verify message length is non-zero/negative
        if msg_len < 1:
            raise ValueError("Invalid message length.")
        
        msg_type = conn.recv_exact(1)[0]

        payload = conn.recv_exact(msg_len - 1)

        message = parse_message(msg_type, payload)

        # TODO: handle message after parsing

    def connection_closed(self, conn):
        with self.conn_lock:
            if conn in self.pending:
                self.pending.remove(conn)
            if self.connections.get(conn.remote_id) is conn:
                del self.connections[conn.remote_id]
