import re

_KEYWORD = "\033[38;5;203m"  # Pink/Red
_STRING = "\033[38;5;114m"   # Green
_NUMBER = "\033[38;5;220m"   # Yellow
_COMMENT = "\033[38;5;245m\033[3m" # Gray Italic
_FUNCTION = "\033[38;5;111m" # Blue
_RST = "\033[0m"

_LANG_KEYWORDS = {
    "python": {"def", "class", "return", "if", "else", "elif", "for", "while", "import", "from", "as", "try", "except", "finally", "with", "yield", "pass", "True", "False", "None", "and", "or", "not", "in", "is", "async", "await"},
}

pattern = re.compile(
    r'(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)'
    r'|(?P<comment>#.*|//.*)'
    r'|(?P<word>[A-Za-z_][A-Za-z0-9_]*)'
    r'|(?P<number>\b\d+\b)'
    r'|(?P<other>\s+|.)'
)

def highlight(line, lang="python"):
    keywords = _LANG_KEYWORDS.get(lang, set())
    out = []
    prev_word = None
    for m in pattern.finditer(line):
        kind = m.lastgroup
        text = m.group()
        if kind == "string":
            out.append(f"{_STRING}{text}{_RST}")
        elif kind == "comment":
            out.append(f"{_COMMENT}{text}{_RST}")
        elif kind == "number":
            out.append(f"{_NUMBER}{text}{_RST}")
        elif kind == "word":
            if text in keywords:
                out.append(f"{_KEYWORD}{text}{_RST}")
            elif prev_word in {"def", "class", "function"}:
                out.append(f"{_FUNCTION}{text}{_RST}")
            else:
                out.append(text)
            prev_word = text
        else:
            if text.strip() and kind == "other":
                prev_word = None # Reset on punctuation
            out.append(text)
    return "".join(out)

print(highlight('def hello_world(name="User"):'))
print(highlight('    # This is a comment'))
print(highlight('    return f"Hello {name}!" + str(123)'))
