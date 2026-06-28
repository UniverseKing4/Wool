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
    parser.add_argument(
        "-u",
        "--update",
        "--upgrade",
        dest="update",
        action="store_true",
        help="Update Wool to the latest version",
    )
    args = parser.parse_args()

    if args.update:
        import os
        print("\033[36mℹ Updating Wool to the latest version...\033[0m")
        os.system("curl -fsSL https://universeking4.github.io/Wool/install.sh | bash")
        sys.exit(0)

    from wool.cli import run_repl

    try:
        asyncio.run(run_repl(resume=args.resume))
    except KeyboardInterrupt:
        print("\n\033[2m← Goodbye.\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
