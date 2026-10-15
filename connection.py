# One TCP connection to a neighbor peer.
# Uses one socket with two threads like FAQ Q2 says: one reads, one sends.

import queue
import socket
import threading


class ConnectionClosed(Exception):
    pass


class PeerConnection:
    def __init__(self, peer, sock, remote_id, outgoing):
        self.peer = peer  # the local Peer object
        self.sock = sock
        # for incoming connections we don't know who it is until the handshake
        self.remote_id = remote_id
        self.outgoing = outgoing

        self.send_queue = queue.Queue()
        self.closed = False
        self.lock = threading.Lock()

        self.reader = threading.Thread(target=self.read_loop, daemon=True)
        self.writer = threading.Thread(target=self.write_loop, daemon=True)

    def start(self):
        self.writer.start()
        self.reader.start()

    def send(self, data):
        # writer thread actually sends it, this just queues it
        if not self.closed:
            self.send_queue.put(data)

    def recv_exact(self, n):
        # recv() can return less than n bytes so keep reading until we have all of it
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionClosed()
            data += chunk
        return data

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True

        self.send_queue.put(None)  # wakes up the writer so it can stop
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()
        self.peer.connection_closed(self)

    def write_loop(self):
        while not self.closed:
            data = self.send_queue.get()
            if data is None:
                break
            try:
                self.sock.sendall(data)
            except OSError:
                self.close()
                break

    def read_loop(self):
        try:
            self.peer.on_connect(self)  # handshake happens here
            while not self.closed:
                self.peer.handle_message(self)
        except (ConnectionClosed, OSError, ValueError):
            pass
        finally:
            self.close()

    def __repr__(self):
        if self.outgoing:
            return f"Connection(to {self.remote_id})"
        return f"Connection(from {self.remote_id})"
