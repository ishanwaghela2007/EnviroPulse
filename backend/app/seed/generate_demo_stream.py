"""Drive the SIMULATED DEMO STREAM from the command line.

  python -m app.seed.generate_demo_stream --ticks 12 --interval 3     # play the golden scenario
  python -m app.seed.generate_demo_stream --ticks 1                   # advance one window
  python -m app.seed.generate_demo_stream --outage sim_air            # simulate a source outage
  python -m app.seed.generate_demo_stream --restore sim_air"""
import argparse
import json
import time

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging import configure_logging
from app.services import demo_stream


def main() -> None:
    ap = argparse.ArgumentParser(description="EnviroPulse simulated demo stream")
    ap.add_argument("--ticks", type=int, default=0, help="number of windows to generate")
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between ticks")
    ap.add_argument("--outage", help="simulate an outage of a simulated source")
    ap.add_argument("--restore", help="end a simulated outage")
    args = ap.parse_args()
    configure_logging(get_settings().log_level)
    with session_scope() as db:
        if args.outage:
            print(demo_stream.set_outage(db, args.outage, True))
        if args.restore:
            print(demo_stream.set_outage(db, args.restore, False))
    for i in range(args.ticks):
        with session_scope() as db:
            result = demo_stream.tick(db)
        print(json.dumps({k: result[k] for k in ("tick", "window", "story", "pipeline")}, default=str))
        if i < args.ticks - 1:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
