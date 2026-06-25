import sys
import re

def render_markdown(text):
    return "  " + text

class StreamPrinter:
    def __init__(self):
        self._buffer = []
        self._line_count = 0
        self._col = 0
        self._started = False
        self._columns = 80
        self._rows = 24

    def print_chunk(self, chunk):
        self._buffer.append(chunk)
        plain = re.sub(r'\033\[[0-9;]*[mK]', '', chunk)
        for char in plain:
            if char == '\n':
                self._line_count += 1
                self._col = 0
            else:
                self._col += 1
                if self._col >= self._columns:
                    self._line_count += 1
                    self._col = 0
        sys.stdout.write(chunk)
        sys.stdout.flush()
        self._started = True

    def finish(self):
        full = "".join(self._buffer)
        if full and not full.endswith("\n"):
            sys.stdout.write("\n")
            self._line_count += 1
        
        sys.stdout.write(f"\r\033[{self._line_count}A")
        sys.stdout.write("\033[0J")
        
        rendered = render_markdown(full.strip())
        sys.stdout.write(rendered + "\n")
        sys.stdout.flush()

p = StreamPrinter()
p.print_chunk("Here is the raw HTML content from https://example.com:\n\n```html\n<!doctype html>\n<html lang=\"en\">\n```")
p.finish()
