"""Command-line entry point for ``python -m server``."""

import argparse
import asyncio
import logging

from .matchmaking_server import MatchmakingServer


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the TCP matchmaking and input relay server.")
    parser.add_argument("--host", default="0.0.0.0", help="interface to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="TCP port to bind (default: 8765)")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = MatchmakingServer()
    try:
        asyncio.run(server.serve_forever(args.host, args.port))
    except KeyboardInterrupt:
        logging.info("server stopped")


if __name__ == "__main__":
    main()
