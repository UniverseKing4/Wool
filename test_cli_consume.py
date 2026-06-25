import asyncio
from wool.cli import _prompt
from wool.utils.streaming import StreamPrinter
import sys

async def _consume():
    printer = StreamPrinter()
    reasoning_printer = StreamPrinter(base_style="\033[2m\033[90m")
    has_reasoned = False
    transitioned = False
    
    chunks = [
        ("reasoning", "Thinking..."),
        ("reasoning", " more thinking.\n"),
        ("text", "Here is the final response!\n"),
        ("text", "It supports **markdown**.")
    ]
    
    for chunk_type, chunk in chunks:
        if chunk_type == "text":
            if has_reasoned and not transitioned:
                reasoning_printer.finish()
                sys.stdout.write("\n\n")
                sys.stdout.flush()
                transitioned = True
            printer.print_chunk(chunk)
        elif chunk_type == "reasoning":
            has_reasoned = True
            reasoning_printer.print_chunk(chunk)
            
    # Finally block
    if has_reasoned and not transitioned:
        reasoning_printer.finish()
        sys.stdout.write("\n\n")
        sys.stdout.flush()
    printer.finish()
    
asyncio.run(_consume())
