import re
import sys
from wool.utils.markdown import _a, _DIM, _RST, _FG_WHITE, _BG_GRAY, _FG_CYAN, _FG_GREEN, _ITALIC, _HEADING_COLORS, _style_inline

class LiveMarkdownPrinter:
    def __init__(self, base_style=""):
        self.buffer = ""
        self.in_code_block = False
        self.code_lang = ""
        self.base_style = base_style

    def print_chunk(self, chunk: str):
        if not chunk: return
        self.buffer += chunk
        
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self._print_line(line)
            
    def _apply_style(self, text: str) -> str:
        if not self.base_style:
            return text
        return self.base_style + text.replace(_RST, _RST + self.base_style) + _RST

    def _print_line(self, line: str):
        # We strip trailing \r in case it's CRLF
        line = line.rstrip("\r")
        
        if self.in_code_block:
            if line.strip().startswith("```"):
                self.in_code_block = False
                sys.stdout.write(self._apply_style(f"  {_a(_DIM)}└{'─' * 44}┘{_a(_RST)}") + "\r\n")
            else:
                styled = f"  {_a(_DIM)}│{_a(_RST)} {_a(_BG_GRAY, _FG_WHITE)}{line}{_a(_RST)}"
                sys.stdout.write(self._apply_style(styled) + "\r\n")
            sys.stdout.flush()
            return
            
        if line.strip().startswith("```"):
            self.in_code_block = True
            lang = line.strip()[3:].strip()
            if lang:
                sys.stdout.write(self._apply_style(f"  {_a(_DIM)}┌─ {lang} ─{'─' * max(0, 40 - len(lang))}┐{_a(_RST)}") + "\r\n")
            else:
                sys.stdout.write(self._apply_style(f"  {_a(_DIM)}┌{'─' * 44}┐{_a(_RST)}") + "\r\n")
            sys.stdout.flush()
            return

        # Heading
        hm = re.match(r"^(#{1,6})\s+(.+)$", line)
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

        # Blockquote
        bm = re.match(r"^>\s+(.+)$", line)
        if bm:
            quote_text = _style_inline(bm.group(1))
            sys.stdout.write(self._apply_style(f"  {_a(_FG_GREEN)}▐{_a(_RST)} {_a(_ITALIC)}{quote_text}{_a(_RST)}") + "\r\n")
            sys.stdout.flush()
            return

        # Lists
        um = re.match(r"^(\s*)([-*+])\s+(.+)$", line)
        if um:
            indent_str = um.group(1)
            depth = len(indent_str) // 2
            bullet = ["•", "◦", "▪"][min(depth, 2)]
            content = _style_inline(um.group(3))
            pad = "  " * depth
            sys.stdout.write(self._apply_style(f"  {pad}{_a(_FG_CYAN)}{bullet}{_a(_RST)} {content}") + "\r\n")
            sys.stdout.flush()
            return

        om = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
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

    def finish(self):
        if self.buffer:
            self._print_line(self.buffer)
            self.buffer = ""
        # If left in code block (stream cut off), close it.
        if self.in_code_block:
            sys.stdout.write(self._apply_style(f"  {_a(_DIM)}└{'─' * 44}┘{_a(_RST)}") + "\r\n")
            self.in_code_block = False

p = LiveMarkdownPrinter()
p.print_chunk("Here is an algorithm that is a classic in computer science: solving the **N-Queens Problem** using **Backtracking**.\n\n### The Problem\nPlace $N$ chess queens on an $N \\times N$ chessboard so that no two queens threaten each other. This means no two queens can share the same row, column, or diagonal.\n\n### The Code (Python)\n```python\ndef solve_n_queens(n):\n    cols = set()\n    return True\n```\n")
p.finish()
