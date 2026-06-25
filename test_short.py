import sys
from wool.utils.streaming import StreamPrinter
p = StreamPrinter()
p.print_chunk("Hey! How can I help you?")
print("\n--- finish ---")
p.finish()
