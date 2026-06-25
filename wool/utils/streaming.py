"""Stream-printing utilities for incremental LLM output with markdown support."""

from __future__ import annotations

import sys



class StreamPrinter:
    """Streams and renders markdown live line-by-line.

    This prevents terminal scrollback corruption and copy-paste 
    issues caused by ANSI rewinding.
    """

    def __init__(self, *, render_md: bool = True, base_style: str = "") -> None:
        self._buffer: str = ""
        self._base_style: str = base_style
        self._render_md: bool = render_md
        self._started: bool = False
        
        self._has_text: bool = False
        self._empty_lines: int = 0
        
        self._in_code_block: bool = False
        self._code_lang: str = ""

    def print_chunk(self, chunk: str) -> None:
        """Print *chunk* immediately and accumulate it."""
        if not chunk:
            return
            
        self._buffer += chunk
        self._started = True
        
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._print_line(line)

    def _apply_style(self, text: str) -> str:
        if not self._base_style or not sys.stdout.isatty():
            return text
        from wool.utils.markdown import _RST
        return self._base_style + text.replace(_RST, _RST + self._base_style) + _RST

    def _print_line(self, line: str) -> None:
        line = line.rstrip("\r")
        
        if not self._render_md or not sys.stdout.isatty():
            from wool.utils.markdown import _FENCE_RE
            is_fence = False
            cm = _FENCE_RE.match(line)
            
            if self._in_code_block:
                fence = getattr(self, '_fence_char', '```')
                if line.strip().startswith(fence):
                    self._in_code_block = False
                    is_fence = True
            elif cm:
                self._in_code_block = True
                self._fence_char = cm.group(2)[:3]
                is_fence = True
            
            if not self._in_code_block and not line.strip() and not is_fence:
                if self._has_text and self._empty_lines < 1:
                    sys.stdout.write("\r\n")
                if self._has_text:
                    self._empty_lines += 1
                sys.stdout.flush()
                return
            
            self._has_text = True
            self._empty_lines = 0
            sys.stdout.write(self._apply_style(line) + "\r\n")
            sys.stdout.flush()
            return

        from wool.utils.markdown import (
            _FENCE_RE, _HEADING_RE, _BLOCKQUOTE_RE, 
            _ULIST_RE, _OLIST_RE, _HR_RE, _style_inline, _LIST_BULLETS,
            _a, _DIM, _RST, _BG_GRAY, _FG_CYAN, _FG_GREEN, _ITALIC,
            _HEADING_COLORS
        )
        
        if self._in_code_block:
            fence = getattr(self, '_fence_char', '```')
            if line.strip().startswith(fence):
                self._in_code_block = False
                sys.stdout.write(self._apply_style(f"  {_a(_DIM)}└{'─' * 44}┘{_a(_RST)}") + "\r\n")
            else:
                from wool.utils.syntax import highlight_code
                hl_line = highlight_code(line, self._code_lang)
                styled = f"  {_a(_DIM)}│{_a(_RST)} {_a(_BG_GRAY)}{hl_line}{_a(_RST)}"
                sys.stdout.write(self._apply_style(styled) + "\r\n")
            sys.stdout.flush()
            return
            
        # For non-code blocks, strip excessive newlines
        if not line.strip():
            if self._has_text and self._empty_lines < 1:
                sys.stdout.write("\r\n")
            if self._has_text:
                self._empty_lines += 1
            sys.stdout.flush()
            return
            
        self._has_text = True
        self._empty_lines = 0

        cm = _FENCE_RE.match(line)
        if cm:
            self._in_code_block = True
            lang = cm.group(3).strip()
            self._code_lang = lang
            self._fence_char = cm.group(2)[:3]
            if lang:
                sys.stdout.write(self._apply_style(f"  {_a(_DIM)}┌─ {lang} ─{'─' * max(0, 40 - len(lang))}┐{_a(_RST)}") + "\r\n")
            else:
                sys.stdout.write(self._apply_style(f"  {_a(_DIM)}┌{'─' * 44}┐{_a(_RST)}") + "\r\n")
            sys.stdout.flush()
            return

        if _HR_RE.match(line):
            sys.stdout.write(self._apply_style(f"  {_a(_DIM)}{'─' * 50}{_a(_RST)}") + "\r\n")
            sys.stdout.flush()
            return

        hm = _HEADING_RE.match(line)
        if hm:
            level = len(hm.group(1))
            text_part = hm.group(2)
            color = _HEADING_COLORS[min(level, 6) - 1]
            prefix = "█ " if level == 1 else ("▌ " if level == 2 else "▎ ")
            rendered_text = _style_inline(text_part)
            sys.stdout.write(self._apply_style(f"  {_a(color)}{prefix}{rendered_text}{_a(_RST)}") + "\r\n")
            if level <= 2:
                width = min(len(text_part) + 4, 50)
                sys.stdout.write(self._apply_style(f"  {_a(_DIM)}{'─' * width}{_a(_RST)}") + "\r\n")
            sys.stdout.flush()
            return

        # Simple table support (just style inline, no alignment)
        if "|" in line:
            sys.stdout.write(self._apply_style(f"  {_style_inline(line)}") + "\r\n")
            sys.stdout.flush()
            return

        bm = _BLOCKQUOTE_RE.match(line)
        if bm:
            quote_text = _style_inline(bm.group(2))
            sys.stdout.write(self._apply_style(f"  {_a(_FG_GREEN)}▐{_a(_RST)} {_a(_ITALIC)}{quote_text}{_a(_RST)}") + "\r\n")
            sys.stdout.flush()
            return

        um = _ULIST_RE.match(line)
        if um:
            indent_str = um.group(1)
            depth = len(indent_str) // 2
            bullet = _LIST_BULLETS[min(depth, len(_LIST_BULLETS) - 1)]
            content = _style_inline(um.group(3))
            pad = "  " * depth
            sys.stdout.write(self._apply_style(f"  {pad}{_a(_FG_CYAN)}{bullet}{_a(_RST)} {content}") + "\r\n")
            sys.stdout.flush()
            return

        om = _OLIST_RE.match(line)
        if om:
            indent_str = om.group(1)
            depth = len(indent_str) // 2
            num = om.group(2)
            content = _style_inline(om.group(3))
            pad = "  " * depth
            sys.stdout.write(self._apply_style(f"  {pad}{_a(_FG_CYAN)}{num}.{_a(_RST)} {content}") + "\r\n")
            sys.stdout.flush()
            return

        # Plain paragraph
        styled = _style_inline(line)
        out_line = f"  {styled}" if styled.strip() else ""
        sys.stdout.write(self._apply_style(out_line) + "\r\n")
        sys.stdout.flush()

    def finish(self) -> str:
        """Finalise the stream.

        Returns an empty string as we don't need the full text for replacement anymore.
        """
        if self._buffer:
            self._print_line(self._buffer)
            
        if self._in_code_block:
            from wool.utils.markdown import _a, _DIM, _RST
            sys.stdout.write(self._apply_style(f"  {_a(_DIM)}└{'─' * 44}┘{_a(_RST)}") + "\r\n")
            sys.stdout.flush()
            
        self.reset()
        return ""

    def reset(self) -> None:
        """Reset the printer state."""
        self._buffer = ""
        self._started = False
        self._has_text = False
        self._empty_lines = 0
        self._in_code_block = False
        self._code_lang = ""
