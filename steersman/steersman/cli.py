import argparse

from steersman.config import Settings
from steersman.server import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steersman")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Start steersman server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", default=None, type=int)
    serve.add_argument("--log-level", default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        settings = Settings(
            host=args.host if args.host is not None else Settings().host,
            port=args.port if args.port is not None else Settings().port,
            log_level=args.log_level if args.log_level is not None else Settings().log_level,
        )
        run(settings)
        return

    parser.error("Unknown command")
