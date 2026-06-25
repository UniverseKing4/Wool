import sys
from wool.utils.markdown import render_markdown
from wool.utils.streaming import StreamPrinter

text = """```python
def foo(bar="baz"):
    # Print the bar
    if True:
        print(bar)
```"""

print("Static render:")
print(render_markdown(text))

print("\nStream render:")
p = StreamPrinter()
p.print_chunk(text)
p.finish()
