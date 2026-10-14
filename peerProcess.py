# Run with: python3 peerProcess.py <peerID>

import sys

from config import ConfigError, load_common_config, load_peer_info
from peer import Peer


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 peerProcess.py <peerID>")
        sys.exit(1)

    try:
        peer_id = int(sys.argv[1])
    except ValueError:
        print(f"Invalid peer ID: {sys.argv[1]}")
        sys.exit(1)

    try:
        common = load_common_config()
        peers = load_peer_info()
    except ConfigError as e:
        print(f"Config error: {e}")
        sys.exit(1)

    peer = None
    try:
        peer = Peer(peer_id, common, peers)
        peer.start()
    except (ValueError, OSError) as e:
        print(f"Failed to start peer {peer_id}: {e}")
        if peer:
            peer.stop()
        sys.exit(1)
    except KeyboardInterrupt:
        # ctrl-c while still connecting to the other peers
        print(f"\nPeer {peer_id} interrupted during startup")
        if peer:
            peer.stop()
        sys.exit(1)

    print(f"Peer {peer_id} started with {common.num_pieces} pieces, has file: {peer.info.has_file}")
    print(f"Connecting to {len(peer.peers_before_me())} peers, waiting on {len(peer.peers_after_me())}")
    peer.run()


if __name__ == "__main__":
    main()
