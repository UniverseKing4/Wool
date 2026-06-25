from typing import Iterator


class ThinkTagParser:
    def __init__(self):
        self.in_think = False
        self.buffer = ""

    def process(self, chunk: str) -> Iterator[tuple[str, str]]:
        self.buffer += chunk

        while self.buffer:
            if not self.in_think:
                # Look for <think>
                idx = self.buffer.find("<think>")
                if idx != -1:
                    if idx > 0:
                        yield "text", self.buffer[:idx]
                    self.in_think = True
                    self.buffer = self.buffer[idx + 7 :]
                else:
                    match_len = 0
                    for i in range(min(len(self.buffer), 6), 0, -1):
                        if self.buffer[-i:] == "<think>"[:i]:
                            match_len = i
                            break

                    if match_len > 0:
                        if len(self.buffer) > match_len:
                            yield "text", self.buffer[:-match_len]
                            self.buffer = self.buffer[-match_len:]
                        break  # wait for more data
                    else:
                        yield "text", self.buffer
                        self.buffer = ""
            else:
                # Look for </think>
                idx = self.buffer.find("</think>")
                if idx != -1:
                    if idx > 0:
                        yield "reasoning", self.buffer[:idx]
                    self.in_think = False
                    self.buffer = self.buffer[idx + 8 :]
                else:
                    match_len = 0
                    for i in range(min(len(self.buffer), 7), 0, -1):
                        if self.buffer[-i:] == "</think>"[:i]:
                            match_len = i
                            break

                    if match_len > 0:
                        if len(self.buffer) > match_len:
                            yield "reasoning", self.buffer[:-match_len]
                            self.buffer = self.buffer[-match_len:]
                        break
                    else:
                        yield "reasoning", self.buffer
                        self.buffer = ""

    def flush(self) -> Iterator[tuple[str, str]]:
        if self.buffer:
            if self.in_think:
                yield "reasoning", self.buffer
            else:
                yield "text", self.buffer
            self.buffer = ""
