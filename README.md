# CNT4007 P2P File Sharing

A BitTorrent-like P2P file sharing program written in Python 3.

## Team
- Sivan Pushpagiri
- Sara Lin
- TODO: add other team members

## Running

1. Edit `Common.cfg` and `PeerInfo.cfg`. Peers are started in the order listed in
   `PeerInfo.cfg`; each peer connects to every peer listed before it.
2. For each peer with `hasFile = 1`, place the file named in `Common.cfg` at
   `peer_<peerID>/<FileName>`.
3. Start each peer in its own terminal (or on its own machine):

```
python3 peerProcess.py 1001
python3 peerProcess.py 1002
...
```

Each peer writes its log to `log_peer_<peerID>.log`.

## Layout

| File | Purpose |
| --- | --- |
| `peerProcess.py` | Entry point; parses the peer ID and starts the peer |
| `config.py` | Parses and validates `Common.cfg` and `PeerInfo.cfg` |
| `peer.py` | Peer process: server socket, outgoing connections, shared state |
| `connection.py` | One TCP connection to a neighbor (reader + writer threads) |
