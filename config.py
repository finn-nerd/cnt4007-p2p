# Reads Common.cfg and PeerInfo.cfg

import math
import os


class ConfigError(Exception):
    pass


class CommonConfig:
    def __init__(self, num_preferred, unchoke_interval, optimistic_interval,
                 file_name, file_size, piece_size):
        self.num_preferred = num_preferred
        self.unchoke_interval = unchoke_interval
        self.optimistic_interval = optimistic_interval
        self.file_name = file_name
        self.file_size = file_size
        self.piece_size = piece_size

        # number of pieces, the last one can be smaller than piece_size
        self.num_pieces = math.ceil(file_size / piece_size)
        self.last_piece_size = file_size - (self.num_pieces - 1) * piece_size

        # 1 bit per piece, rounded up to whole bytes
        self.bitfield_bytes = math.ceil(self.num_pieces / 8)

    def get_piece_size(self, index):
        if index == self.num_pieces - 1:
            return self.last_piece_size
        return self.piece_size


class PeerInfo:
    def __init__(self, peer_id, host, port, has_file):
        self.peer_id = peer_id
        self.host = host
        self.port = port
        self.has_file = has_file

    def __repr__(self):
        return f"PeerInfo({self.peer_id}, {self.host}:{self.port}, has_file={self.has_file})"


def read_lines(path):
    if not os.path.exists(path):
        raise ConfigError(f"could not find {path}")

    lines = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            # skip blank lines and comments
            if line == "" or line.startswith("#"):
                continue
            lines.append(line)
    return lines


def load_common_config(path="Common.cfg"):
    settings = {}
    for line in read_lines(path):
        parts = line.split()
        if len(parts) != 2:
            raise ConfigError(f"bad line in {path}: {line}")
        settings[parts[0]] = parts[1]

    needed = ["NumberOfPreferredNeighbors", "UnchokingInterval",
              "OptimisticUnchokingInterval", "FileName", "FileSize", "PieceSize"]
    for key in needed:
        if key not in settings:
            raise ConfigError(f"{path} is missing {key}")

    try:
        config = CommonConfig(
            int(settings["NumberOfPreferredNeighbors"]),
            int(settings["UnchokingInterval"]),
            int(settings["OptimisticUnchokingInterval"]),
            settings["FileName"],
            int(settings["FileSize"]),
            int(settings["PieceSize"]),
        )
    except ValueError:
        raise ConfigError(f"{path} has a non-number where a number should be")

    if config.file_size <= 0 or config.piece_size <= 0:
        raise ConfigError("FileSize and PieceSize have to be positive")
    if config.num_preferred <= 0:
        raise ConfigError("NumberOfPreferredNeighbors has to be at least 1")
    if config.unchoke_interval <= 0 or config.optimistic_interval <= 0:
        raise ConfigError("unchoking intervals have to be positive")

    return config


def load_peer_info(path="PeerInfo.cfg"):
    # order matters here, each peer connects to the ones listed above it
    peers = []
    for line in read_lines(path):
        parts = line.split()
        if len(parts) != 4:
            raise ConfigError(f"bad line in {path}: {line}")

        try:
            peer_id = int(parts[0])
            port = int(parts[2])
        except ValueError:
            raise ConfigError(f"peer id and port should be numbers: {line}")

        if parts[3] not in ("0", "1"):
            raise ConfigError(f"last column should be 0 or 1: {line}")

        for p in peers:
            if p.peer_id == peer_id:
                raise ConfigError(f"peer {peer_id} is listed twice in {path}")

        peers.append(PeerInfo(peer_id, parts[1], port, parts[3] == "1"))

    if len(peers) == 0:
        raise ConfigError(f"no peers in {path}")
    return peers
