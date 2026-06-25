from wool.utils.streaming import StreamPrinter

text = "\n\n\nHello\n\n\n\n\nWorld!\n\n\n```\n\n\nprint()\n\n\n```\n\n\n"
p = StreamPrinter()
p.print_chunk(text)
p.finish()
