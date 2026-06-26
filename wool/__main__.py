"""Entry point for ``python -m wool`` and the ``wool`` CLI command."""

import argparse
import asyncio
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="wool",
        description="Ultra-lightweight CLI AI Agent",
    )
    parser.add_argument(
        "-c",
        "--continue",
        "--resume",
        dest="resume",
        action="store_true",
        help="Continue/resume the last session instead of starting fresh",
    )
    parser.add_argument(
        "-r",
        dest="resume",
        action="store_true",
        help=argparse.SUPPRESS,  # hidden alias for -c
    )
    args = parser.parse_args()

    from wool.cli import run_repl

    try:
        asyncio.run(run_repl(resume=args.resume))
    except KeyboardInterrupt:
        print("\n\033[2m← Goodbye.\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
