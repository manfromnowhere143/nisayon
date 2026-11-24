import argparse
import json
from pathlib import Path

from .episode import run
from .replay import replay


def main():
    parser = argparse.ArgumentParser(description="Local CPU reference-embodiment experiment")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("nominal")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--payload", type=float, default=0.15)
    p.add_argument("--latency", type=float, default=0.004)
    p.add_argument("--noise-scale", type=float, default=1)
    p.add_argument("--timestep", type=float, default=0.002)
    p.add_argument("--iterations", type=int, default=80)
    p.add_argument("--friction", type=float, default=0.6)
    p.add_argument("--duration", type=float, default=13)
    p = sub.add_parser("replay")
    p.add_argument("episode", type=Path)
    p = sub.add_parser("experiment")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("analyze")
    p.add_argument("campaign", type=Path)
    a = parser.parse_args()
    if a.command == "replay":
        result = replay(a.episode)
    elif a.command == "experiment":
        from .campaign import experiment

        result = experiment(a.out)
    elif a.command == "analyze":
        from .analysis import analyze

        result = analyze(a.campaign)
    else:
        result = run(
            a.out,
            sensor_seed=a.seed,
            payload_mass=a.payload,
            latency_s=a.latency,
            noise_scale=a.noise_scale,
            timestep=a.timestep,
            iterations=a.iterations,
            friction=a.friction,
            duration=a.duration,
        )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
