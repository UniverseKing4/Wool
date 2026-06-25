"""Pure ANSI escape-sequence helpers — no curses, no TUI libraries.

Every function returns a *styled string*; the ``success/error/warning/info``
helpers print directly to stdout.
"""

from __future__ import annotations

import sys

# ── Escape codes ──────────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

FG_RED = "\033[31m"
FG_GREEN = "\033[32m"
FG_YELLOW = "\033[33m"
FG_BLUE = "\033[34m"
FG_MAGENTA = "\033[35m"
FG_CYAN = "\033[36m"
FG_WHITE = "\033[37m"
FG_GRAY = "\033[90m"

# ── Style helpers ─────────────────────────────────────────────────────────────


def style(text: str, *codes: str) -> str:
    """Wrap *text* in arbitrary ANSI codes and reset afterwards."""
    if not sys.stdout.isatty():
        return text
    return "".join(codes) + text + RESET


def bold(text: str) -> str:
    return style(text, BOLD)


def dim(text: str) -> str:
    return style(text, DIM)


def italic(text: str) -> str:
    return style(text, ITALIC)


def underline(text: str) -> str:
    return style(text, UNDERLINE)


def red(text: str) -> str:
    return style(text, FG_RED)


def green(text: str) -> str:
    return style(text, FG_GREEN)


def yellow(text: str) -> str:
    return style(text, FG_YELLOW)


def blue(text: str) -> str:
    return style(text, FG_BLUE)


def magenta(text: str) -> str:
    return style(text, FG_MAGENTA)


def cyan(text: str) -> str:
    return style(text, FG_CYAN)


def white(text: str) -> str:
    return style(text, FG_WHITE)


def gray(text: str) -> str:
    return style(text, FG_GRAY)


def gray(text: str) -> str:
    return style(text, FG_GRAY)


# ── Message printers (write directly to stdout) ──────────────────────────────


def success(msg: str) -> None:
    print(f"  {green('✓')} {msg}")


def error(msg: str) -> None:
    print(f"  {red('✗')} {msg}")


def warning(msg: str) -> None:
    print(f"  {yellow('⚠')} {msg}")


def info(msg: str) -> None:
    print(f"  {blue('ℹ')} {msg}")
