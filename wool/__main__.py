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
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Uninstall Wool completely",
    )
    args = parser.parse_args()

    if args.update:
        import os
        print("\033[36mℹ Updating Wool to the latest version...\033[0m")
        os.system("curl -fsSL https://universeking4.github.io/Wool/install.sh | bash")
        sys.exit(0)

    if args.uninstall:
        import os
        import shutil
        from pathlib import Path

        print("\033[31m⚠ WARNING: This will completely remove Wool, including all your settings, sessions, and history.\033[0m")
        try:
            confirm = input("Are you sure you want to proceed? [y/N]: ").strip().lower()
        except KeyboardInterrupt:
            print("\nUninstall cancelled.")
            sys.exit(0)
        
        if confirm != "y":
            print("Uninstall cancelled.")
            sys.exit(0)

        print("\033[36mℹ Uninstalling Wool package...\033[0m")
        os.system("pipx uninstall wool >/dev/null 2>&1 || python3 -m pip uninstall -y wool >/dev/null 2>&1 || pip uninstall -y wool >/dev/null 2>&1")

        wool_bin = Path.home() / ".local" / "bin" / "wool"
        if wool_bin.exists():
            try:
                wool_bin.unlink(missing_ok=True)
            except OSError:
                pass

        print("\033[36mℹ Removing configuration and sessions...\033[0m")
        config_dir = Path.home() / ".config" / "wool"
        if config_dir.exists():
            shutil.rmtree(config_dir, ignore_errors=True)

        print("\033[32m✓ Wool has been completely removed. Goodbye! 🐑\033[0m")
        sys.exit(0)

    from wool.cli import run_repl

    try:
        asyncio.run(run_repl(resume=args.resume))
    except KeyboardInterrupt:
        print("\n\033[2m← Goodbye.\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
