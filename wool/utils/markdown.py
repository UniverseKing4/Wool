"""Markdown → ANSI renderer for terminal output.

Converts markdown text to ANSI-styled terminal output.  Supports:

  - **Headings** (# through ####)
  - **Bold** / *italic* / ~~strikethrough~~ / `inline code`
  - Fenced code blocks (``` … ```) with language label
  - Block quotes (>)
  - Ordered and unordered lists (nested)
  - Horizontal rules (---, ***, ___)
  - Links [text](url) and images ![alt](url)
  - Tables (GFM pipe tables)

No external dependencies — pure stdlib + ANSI escapes.
"""

from __future__ import annotations

import re
import sys
from typing import TextIO

# ── ANSI codes ────────────────────────────────────────────────────────────────

_RST = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_ITALIC = "\033[3m"
_ULINE = "\033[4m"
_STRIKE = "\033[9m"

_FG_RED = "\033[31m"
_FG_GREEN = "\033[32m"
_FG_YELLOW = "\033[33m"
_FG_BLUE = "\033[34m"
_FG_MAGENTA = "\033[35m"
_FG_CYAN = "\033[36m"
_FG_WHITE = "\033[37m"
_FG_GRAY = "\033[90m"

_BG_GRAY = "\033[48;5;236m"  # dark-gray background for code blocks

_is_tty: bool | None = None


def _tty() -> bool:
    global _is_tty
    if _is_tty is None:
        _is_tty = sys.stdout.isatty()
    return _is_tty


def _a(*codes: str) -> str:
    """Return joined ANSI codes if stdout is a TTY, else empty."""
    return "".join(codes) if _tty() else ""


# ── inline styling ────────────────────────────────────────────────────────────

# Order matters — process longer/greedier patterns first.
_INLINE_RULES: list[tuple[re.Pattern[str], str]] = [
    # Bold + italic  ***text***  or ___text___
    (re.compile(r"(\*{3}|_{3})(?!\s)(.+?)(?<!\s)\1"), rf"{_BOLD}{_ITALIC}\2{_RST}"),
    # Bold  **text**  or __text__
    (re.compile(r"(\*{2}|_{2})(?!\s)(.+?)(?<!\s)\1"), rf"{_BOLD}\2{_RST}"),
    # Italic  *text*  or _text_  (but not mid-word underscores)
    (re.compile(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)"), rf"{_ITALIC}\1{_RST}"),
    (re.compile(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)"), rf"{_ITALIC}\1{_RST}"),
    # Strikethrough  ~~text~~
    (re.compile(r"~~(?!\s)(.+?)(?<!\s)~~"), rf"{_STRIKE}\1{_RST}"),
    # Inline code  `code`
    (re.compile(r"`([^`\n]+)`"), rf"{_BG_GRAY}{_FG_CYAN}\1{_RST}"),
    # Links  [text](url)
    (re.compile(r"\[([^\]]+)\]\(([^)]+)\)"), rf"{_ULINE}{_FG_BLUE}\1{_RST} {_DIM}(\2){_RST}"),
    # Images  ![alt](url)
    (re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"), rf"{_FG_MAGENTA}🖼  \1{_RST} {_DIM}(\2){_RST}"),
]


def _style_inline(line: str) -> str:
    """Apply inline markdown styling to a single line."""
    if not _tty():
        return line
    for pat, repl in _INLINE_RULES:
        line = pat.sub(repl, line)
    return line


# ── block-level rendering ────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_ULIST_RE = re.compile(r"^(\s*)([-*+])\s+(.*)")
_OLIST_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)")
_BLOCKQUOTE_RE = re.compile(r"^(\s*>\s?)(.*)")
_HR_RE = re.compile(r"^(\s*)([-*_])\s*\2\s*\2[\s\2]*$")
_FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)")
_TABLE_SEP_RE = re.compile(r"^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")

_HEADING_COLORS = [
    _FG_CYAN + _BOLD,      # h1
    _FG_GREEN + _BOLD,     # h2
    _FG_YELLOW + _BOLD,    # h3
    _FG_BLUE + _BOLD,      # h4
    _FG_MAGENTA + _BOLD,   # h5
    _FG_WHITE + _BOLD,     # h6
]

_LIST_BULLETS = ["●", "○", "◦", "·"]


def render_markdown(text: str, *, stream: TextIO | None = None) -> str:
    """Render *text* (markdown) to ANSI-styled terminal output.

    If *stream* is given the rendered output is also written there.
    Returns the rendered string.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── fenced code block ─────────────────────────────────────────
        fence_m = _FENCE_RE.match(line)
        if fence_m:
            indent = fence_m.group(1)
            fence_char = fence_m.group(2)
            lang = fence_m.group(3).strip()
            i += 1
            code_lines: list[str] = []
            while i < len(lines):
                if _FENCE_RE.match(lines[i]) and lines[i].strip().startswith(fence_char[:3]):
                    i += 1
                    break
                code_lines.append(lines[i])
                i += 1
            # Render code block
            if lang:
                out.append(f"  {_a(_DIM)}┌─ {lang} ─{'─' * max(0, 40 - len(lang))}┐{_a(_RST)}")
            else:
                out.append(f"  {_a(_DIM)}┌{'─' * 44}┐{_a(_RST)}")
            for cl in code_lines:
                styled = f"  {_a(_DIM)}│{_a(_RST)} {_a(_BG_GRAY, _FG_WHITE)}{cl}{_a(_RST)}"
                out.append(styled)
            out.append(f"  {_a(_DIM)}└{'─' * 44}┘{_a(_RST)}")
            continue

        # ── horizontal rule ───────────────────────────────────────────
        if _HR_RE.match(line):
            out.append(f"  {_a(_DIM)}{'─' * 50}{_a(_RST)}")
            i += 1
            continue

        # ── heading ───────────────────────────────────────────────────
        hm = _HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1))  # 1–6
            text_part = hm.group(2)
            color = _HEADING_COLORS[min(level, 6) - 1]
            prefix = "█ " if level == 1 else ("▌ " if level == 2 else "▎ ")
            rendered_text = _style_inline(text_part)
            out.append(f"  {_a(color)}{prefix}{rendered_text}{_a(_RST)}")
            if level <= 2:
                width = min(len(text_part) + 4, 50)
                out.append(f"  {_a(_DIM)}{'─' * width}{_a(_RST)}")
            i += 1
            continue

        # ── table ─────────────────────────────────────────────────────
        if "|" in line and i + 1 < len(lines) and _TABLE_SEP_RE.match(lines[i + 1]):
            table_lines: list[str] = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            out.extend(_render_table(table_lines))
            continue

        # ── blockquote ────────────────────────────────────────────────
        bm = _BLOCKQUOTE_RE.match(line)
        if bm:
            quote_text = _style_inline(bm.group(2))
            out.append(f"  {_a(_FG_GREEN)}▐{_a(_RST)} {_a(_ITALIC)}{quote_text}{_a(_RST)}")
            i += 1
            continue

        # ── unordered list ────────────────────────────────────────────
        um = _ULIST_RE.match(line)
        if um:
            indent_str = um.group(1)
            depth = len(indent_str) // 2
            bullet = _LIST_BULLETS[min(depth, len(_LIST_BULLETS) - 1)]
            content = _style_inline(um.group(3))
            pad = "  " * depth
            out.append(f"  {pad}{_a(_FG_CYAN)}{bullet}{_a(_RST)} {content}")
            i += 1
            continue

        # ── ordered list ──────────────────────────────────────────────
        om = _OLIST_RE.match(line)
        if om:
            indent_str = om.group(1)
            depth = len(indent_str) // 2
            num = om.group(2)
            content = _style_inline(om.group(3))
            pad = "  " * depth
            out.append(f"  {pad}{_a(_FG_CYAN)}{num}.{_a(_RST)} {content}")
            i += 1
            continue

        # ── plain paragraph ───────────────────────────────────────────
        styled = _style_inline(line)
        out.append(f"  {styled}" if styled.strip() else "")
        i += 1

    result = "\n".join(out)
    if stream is not None:
        stream.write(result)
        stream.flush()
    return result


# ── table rendering ───────────────────────────────────────────────────────────


def _render_table(lines: list[str]) -> list[str]:
    """Render a GFM pipe table with aligned columns."""
    rows: list[list[str]] = []
    separator_idx: int | None = None

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if _TABLE_SEP_RE.match(stripped):
            separator_idx = idx
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return []

    # Compute column widths.
    n_cols = max(len(r) for r in rows)
    col_widths = [0] * n_cols
    for r in rows:
        for j, cell in enumerate(r):
            # Strip ANSI for width calc
            plain = re.sub(r"\033\[[^m]*m", "", _style_inline(cell))
            col_widths[j] = max(col_widths[j], len(plain))

    out: list[str] = []
    for ri, row in enumerate(rows):
        cells_out: list[str] = []
        for j in range(n_cols):
            cell = row[j] if j < len(row) else ""
            styled = _style_inline(cell)
            plain_len = len(re.sub(r"\033\[[^m]*m", "", styled))
            pad = col_widths[j] - plain_len
            cells_out.append(styled + " " * max(pad, 0))

        line_str = f"  {_a(_DIM)}│{_a(_RST)} " + f" {_a(_DIM)}│{_a(_RST)} ".join(cells_out) + f" {_a(_DIM)}│{_a(_RST)}"

        if ri == 0:
            # Top border
            border = f"  {_a(_DIM)}┌─" + f"─┬─".join("─" * w for w in col_widths) + f"─┐{_a(_RST)}"
            out.append(border)
            out.append(line_str)
            # Header separator
            sep = f"  {_a(_DIM)}├─" + f"─┼─".join("─" * w for w in col_widths) + f"─┤{_a(_RST)}"
            out.append(sep)
        else:
            out.append(line_str)

    # Bottom border
    border = f"  {_a(_DIM)}└─" + f"─┴─".join("─" * w for w in col_widths) + f"─┘{_a(_RST)}"
    out.append(border)
    return out


# ── convenience ───────────────────────────────────────────────────────────────


def print_markdown(text: str) -> None:
    """Render markdown and print to stdout."""
    rendered = render_markdown(text)
    print(rendered)
