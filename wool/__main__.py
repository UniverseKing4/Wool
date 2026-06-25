"""Entry point for ``python -m wool`` and the ``wool`` CLI command."""

import asyncio
import sys


def main() -> None:
    from wool.cli import run_repl

    try:
        asyncio.run(run_repl())
    except KeyboardInterrupt:
        print("\n\033[2m← Goodbye.\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
