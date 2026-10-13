"""``python -m kinetickit.conformance``: run the shared suites and the budget report."""

from __future__ import annotations

import argparse
import json
import sys

from kinetickit.conformance import budgets, run_suite


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m kinetickit.conformance")
    ap.add_argument("--json", help="write the budget measurements to this file")
    ap.add_argument(
        "--scale", type=float, default=1.0, help="multiply every budget (slow machines)"
    )
    ap.add_argument("--no-suites", action="store_true")
    args = ap.parse_args(argv)
    failed = False
    if not args.no_suites:
        for fmt in ("svg", "gif", "html"):
            try:
                rep = run_suite(fmt)
            except ImportError as exc:
                print(f"{fmt}: skipped ({exc})")
                continue
            print(rep.summary())
            failed |= not rep.passed
    values = budgets.measure()
    print(budgets.report(values, args.scale))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"values": values, "scale": args.scale}, fh, indent=2, sort_keys=True)
    over = budgets.check(values, args.scale)
    if over:
        print("budgets exceeded: " + ", ".join(over), file=sys.stderr)
    return 1 if failed or over else 0


if __name__ == "__main__":
    raise SystemExit(main())
