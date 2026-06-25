"""Stream-printing utilities for incremental LLM output with markdown support."""

from __future__ import annotations

import sys

from wool.utils.markdown import render_markdown


class StreamPrinter:
    """Accumulates streamed text and renders it as markdown on finish.

    During streaming, raw chunks are printed immediately so the user
    sees output in real-time.  When :meth:`finish` is called the full
    accumulated text is re-rendered through the markdown engine and
    the raw output is replaced with the styled version.

    The approach uses ANSI cursor-control to overwrite the raw output
    with the rendered version — this keeps the streaming feel while
    delivering polished final output.
    """

    def __init__(self, *, render_md: bool = True) -> None:
        self._buffer: list[str] = []
        self._line_count: int = 0
        self._started: bool = False
        self._render_md = render_md

    def print_chunk(self, chunk: str) -> None:
        """Print *chunk* immediately and accumulate it."""
        if not chunk:
            return
        self._buffer.append(chunk)
        # Count newlines for later cursor rewind.
        self._line_count += chunk.count("\n")
        sys.stdout.write(chunk)
        sys.stdout.flush()
        self._started = True

    def finish(self) -> str:
        """Finalise the stream.

        If markdown rendering is enabled, rewinds and replaces the raw
        streamed output with a properly styled version.  Returns the
        full raw text.
        """
        full = "".join(self._buffer)

        if self._started and full.strip() and self._render_md and sys.stdout.isatty():
            # Ensure we're on a new line before rewriting.
            if full and not full.endswith("\n"):
                sys.stdout.write("\n")
                self._line_count += 1

            # Move cursor up to the start of the streamed output and clear.
            if self._line_count > 0:
                sys.stdout.write(f"\033[{self._line_count}A")  # move up
                sys.stdout.write(f"\033[0J")  # clear from cursor to end

            # Render markdown and print.
            rendered = render_markdown(full.strip())
            sys.stdout.write(rendered + "\n")
            sys.stdout.flush()

        elif self._started and full:
            # Non-TTY or no markdown: just ensure trailing newline.
            if not full.endswith("\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()

        self.reset()
        return full

    def reset(self) -> None:
        """Clear the internal buffer."""
        self._buffer.clear()
        self._line_count = 0
        self._started = False
