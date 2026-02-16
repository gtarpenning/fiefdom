import argparse
import json
from urllib.error import URLError
from urllib.request import urlopen

from steersman.config import Settings
from steersman.launchd import install_launch_agent
from steersman.launchd import launch_agent_status
from steersman.launchd import stop_launch_agent
from steersman.server import is_loopback_host
from steersman.server import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="steersman")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Start steersman server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", default=None, type=int)
    serve.add_argument("--log-level", default=None)

    start = sub.add_parser("start", help="Start steersman server")
    start.add_argument("--host", default=None)
    start.add_argument("--port", default=None, type=int)
    start.add_argument("--log-level", default=None)
    start.add_argument("--launchd", action="store_true")
    start.add_argument("--launchd-no-load", action="store_true")
    start.add_argument("--launchd-label", default="local.steersman")
    start.add_argument("--launchd-plist-path", default=None)

    status = sub.add_parser("status", help="Check running steersman status")
    status.add_argument("--host", default=None)
    status.add_argument("--port", default=None, type=int)
    status.add_argument("--timeout", default=1.0, type=float)
    status.add_argument("--launchd", action="store_true")
    status.add_argument("--launchd-label", default="local.steersman")
    status.add_argument("--launchd-plist-path", default=None)

    stop = sub.add_parser("stop", help="Stop steersman server")
    stop.add_argument("--launchd", action="store_true")
    stop.add_argument("--launchd-label", default="local.steersman")
    stop.add_argument("--launchd-plist-path", default=None)
    stop.add_argument("--remove-plist", action="store_true")

    doctor = sub.add_parser("doctor", help="Run local configuration checks")
    doctor.add_argument("--host", default=None)
    doctor.add_argument("--port", default=None, type=int)

    return parser


def resolve_settings(args: argparse.Namespace) -> Settings:
    defaults = Settings()
    return Settings(
        host=args.host if args.host is not None else defaults.host,
        port=args.port if args.port is not None else defaults.port,
        log_level=(
            args.log_level if hasattr(args, "log_level") and args.log_level is not None else defaults.log_level
        ),
    )


def cmd_status(args: argparse.Namespace) -> int:
    settings = resolve_settings(args)
    if hasattr(args, "launchd") and args.launchd:
        launchd = launch_agent_status(
            settings=settings,
            label=args.launchd_label,
            plist_path=args.launchd_plist_path,
            timeout_s=args.timeout,
        )
        print(f"launchd installed: {'yes' if launchd['installed'] else 'no'}")
        print(f"launchd loaded: {'yes' if launchd['loaded'] else 'no'}")
        print(f"health: {'ok' if launchd['health'] else 'unavailable'}")
        return 0 if launchd["installed"] and launchd["loaded"] and launchd["health"] else 1

    url = f"http://{settings.host}:{settings.port}/healthz"
    try:
        with urlopen(url, timeout=args.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") == "ok":
            print("status: ok")
            return 0
        print("status: unhealthy")
        return 1
    except (URLError, TimeoutError, json.JSONDecodeError):
        print("status: unavailable")
        return 1


def cmd_doctor(args: argparse.Namespace) -> int:
    settings = resolve_settings(args)
    if not is_loopback_host(settings.host):
        print(f"doctor: fail - non-loopback host {settings.host}")
        return 1
    print("doctor: pass - loopback host and valid port")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    settings = resolve_settings(args)
    if not args.launchd:
        run(settings)
        return 0

    try:
        path = install_launch_agent(
            settings=settings,
            label=args.launchd_label,
            plist_path=args.launchd_plist_path,
            load=not args.launchd_no_load,
        )
    except Exception as exc:
        print(f"launchd install failed: {exc}")
        return 1

    print(f"launchd plist: {path}")
    print(f"launchd loaded: {'no' if args.launchd_no_load else 'yes'}")
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    if not args.launchd:
        print("stop currently supports only --launchd")
        return 1
    try:
        stop_launch_agent(
            label=args.launchd_label,
            remove_plist=args.remove_plist,
            plist_path=args.launchd_plist_path,
        )
    except Exception as exc:
        print(f"launchd stop failed: {exc}")
        return 1
    print("launchd loaded: no")
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        settings = resolve_settings(args)
        run(settings)
        return
    if args.command == "start":
        raise SystemExit(cmd_start(args))
    if args.command == "status":
        raise SystemExit(cmd_status(args))
    if args.command == "stop":
        raise SystemExit(cmd_stop(args))
    if args.command == "doctor":
        raise SystemExit(cmd_doctor(args))

    parser.error("Unknown command")
