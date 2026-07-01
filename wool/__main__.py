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
    parser.add_argument(
        "-e",
        "--export",
        dest="export_data",
        action="store_true",
        help="Export all configuration and sessions to a local ./wool-export directory",
    )
    parser.add_argument(
        "-i",
        "--import",
        dest="import_data",
        action="store_true",
        help="Import configuration and sessions from a local ./wool-export directory",
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

        print("\n\033[32m────────────────────────────────────────\033[0m")
        print("\033[32m  ✓ Wool has been completely uninstalled! 🐑\033[0m")
        print("\033[32m────────────────────────────────────────\033[0m\n")
        print("\033[36mIf you ever want to reinstall, just run:\033[0m")
        print("\033[1m  curl -fsSL https://universeking4.github.io/Wool/install.sh | bash\033[0m\n")
        print("\033[2mGoodbye!\033[0m")
        sys.exit(0)

    if args.export_data:
        import json
        import shutil
        from pathlib import Path
        
        config_dir = Path.home() / ".config" / "wool"
        export_dir = Path.cwd() / "wool-export"
        
        if not config_dir.exists():
            print("\033[33m⚠ No global Wool configuration found to export.\033[0m")
            sys.exit(0)
            
        print(f"\033[36mℹ Exporting Wool data to {export_dir}...\033[0m")
        if export_dir.exists():
            shutil.rmtree(export_dir, ignore_errors=True)
            
        shutil.copytree(config_dir, export_dir)
        
        config_file = export_dir / "config.json"
        num_providers = 0
        num_mcps = 0
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    num_providers = len(data.get("providers", {}))
                    num_mcps = len(data.get("mcp_servers", {}))
            except Exception:
                pass
                
        sessions_dir = export_dir / "sessions"
        num_sessions = len(list(sessions_dir.glob("*.json"))) if sessions_dir.exists() else 0
        
        print("\n\033[32m────────────────────────────────────────\033[0m")
        print("\033[32m  ✓ Wool data successfully exported! 🐑\033[0m")
        print("\033[32m────────────────────────────────────────\033[0m\n")
        print(f"\033[1m  Providers Exported:\033[0m {num_providers}")
        print(f"\033[1m  MCP Servers Exported:\033[0m {num_mcps}")
        print(f"\033[1m  Sessions Exported:\033[0m {num_sessions}\n")
        sys.exit(0)

    if args.import_data:
        import json
        import shutil
        from pathlib import Path
        
        config_dir = Path.home() / ".config" / "wool"
        import_dir = Path.cwd() / "wool-export"
        
        if not import_dir.exists():
            print(f"\033[31m✗ Import directory not found at {import_dir}\033[0m")
            sys.exit(1)
            
        if config_dir.exists():
            has_meaningful_data = False
            config_file = config_dir / "config.json"
            if config_file.exists():
                try:
                    with open(config_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if data.get("providers") or data.get("mcp_servers"):
                            has_meaningful_data = True
                except Exception:
                    pass
            sessions_dir = config_dir / "sessions"
            if sessions_dir.exists() and len(list(sessions_dir.glob("*.json"))) > 0:
                has_meaningful_data = True
                
            if has_meaningful_data:
                print("\033[33m⚠ WARNING: You already have Wool data in your global configuration.\033[0m")
                print("\033[33mImporting will OVERWRITE your current global providers, MCPs, and sessions.\033[0m")
                try:
                    confirm = input("Are you sure you want to proceed with import? [y/N]: ").strip().lower()
                except KeyboardInterrupt:
                    print("\nImport cancelled.")
                    sys.exit(0)
                
                if confirm != "y":
                    print("Import cancelled.")
                    sys.exit(0)
                    
        print(f"\033[36mℹ Importing Wool data from {import_dir}...\033[0m")
        if config_dir.exists():
            shutil.rmtree(config_dir, ignore_errors=True)
            
        shutil.copytree(import_dir, config_dir)
        
        config_file = config_dir / "config.json"
        num_providers = 0
        num_mcps = 0
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    num_providers = len(data.get("providers", {}))
                    num_mcps = len(data.get("mcp_servers", {}))
            except Exception:
                pass
                
        sessions_dir = config_dir / "sessions"
        num_sessions = len(list(sessions_dir.glob("*.json"))) if sessions_dir.exists() else 0
        
        print("\n\033[32m────────────────────────────────────────\033[0m")
        print("\033[32m  ✓ Wool data successfully imported! 🐑\033[0m")
        print("\033[32m────────────────────────────────────────\033[0m\n")
        print(f"\033[1m  Providers Imported:\033[0m {num_providers}")
        print(f"\033[1m  MCP Servers Imported:\033[0m {num_mcps}")
        print(f"\033[1m  Sessions Imported:\033[0m {num_sessions}\n")
        sys.exit(0)

    from wool.cli import run_repl

    try:
        asyncio.run(run_repl(resume=args.resume))
    except KeyboardInterrupt:
        print("\n\033[2m← Goodbye.\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
