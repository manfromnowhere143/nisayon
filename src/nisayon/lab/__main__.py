"""python -m nisayon.lab: the same bounded API used by the local workbench."""

import argparse
import json
import signal
import threading
from pathlib import Path

from nisayon.engine.io import decode_json

from . import capabilities, execute, experiment, inspect_packet


def main():
    parser = argparse.ArgumentParser(description="Nisayon local experimental instruments")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    validate = commands.add_parser("validate")
    validate.add_argument("--parameters", type=Path)
    validate.add_argument("--out", type=Path)
    run = commands.add_parser("run")
    run.add_argument("spec", type=Path)
    run.add_argument("--out", type=Path, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("packet", type=Path)
    inspect.add_argument("--sha256")
    serve = commands.add_parser("serve")
    serve.add_argument("--out", type=Path, default=Path("artifacts/lab"))
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--frontend", type=Path)
    serve.add_argument("--allow-origin")
    args = parser.parse_args()
    try:
        if args.command == "capabilities":
            result = capabilities()
        elif args.command == "validate":
            result = experiment(
                decode_json(args.parameters.read_bytes()) if args.parameters else None
            )
            if args.out:
                with args.out.open("x") as stream:
                    stream.write(json.dumps(result, indent=2, allow_nan=False) + "\n")
        elif args.command == "run":
            stop = threading.Event()
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            result = execute(decode_json(args.spec.read_bytes()), args.out, cancel=stop.is_set)
        elif args.command == "inspect":
            result = inspect_packet(args.packet, expected_sha256=args.sha256)
        else:
            from .service import make_server

            server = make_server(
                args.out, port=args.port, frontend=args.frontend, allow_origin=args.allow_origin
            )
            print(
                f"Nisayon local instruments: http://127.0.0.1:{server.server_address[1]}",
                flush=True,
            )
            try:
                server.serve_forever()
            finally:
                for job in server.lab.jobs.values():
                    job["stop"].set()
                server.server_close()
            return
        print(json.dumps(result, indent=2, allow_nan=False))
        if args.command == "run" and result["status"] != "complete":
            raise SystemExit(2)
    except (ValueError, OSError, TypeError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
