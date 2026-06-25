import re

_KEYWORD = "\033[38;5;203m"  # Pink/Red
_STRING = "\033[38;5;114m"   # Green
_NUMBER = "\033[38;5;220m"   # Yellow
_COMMENT = "\033[38;5;245m\033[3m" # Gray Italic
_FUNCTION = "\033[38;5;111m" # Blue
_RST = "\033[0m"

_LANG_KEYWORDS = {
    "python": {"def", "class", "return", "if", "else", "elif", "for", "while", "import", "from", "as", "try", "except", "finally", "with", "yield", "pass", "True", "False", "None", "and", "or", "not", "in", "is", "async", "await", "lambda", "global", "nonlocal", "del"},
    "javascript": {"function", "const", "let", "var", "return", "if", "else", "for", "while", "import", "export", "from", "class", "try", "catch", "finally", "true", "false", "null", "undefined", "new", "this", "await", "async", "typeof", "instanceof", "in", "of", "switch", "case", "default", "break", "continue", "throw", "delete", "yield", "super"},
    "typescript": {"function", "const", "let", "var", "return", "if", "else", "for", "while", "import", "export", "from", "class", "try", "catch", "finally", "true", "false", "null", "undefined", "new", "this", "await", "async", "interface", "type", "implements", "extends", "public", "private", "protected", "readonly", "enum", "any", "void", "never", "unknown", "typeof", "instanceof", "in", "of", "switch", "case", "default", "break", "continue", "throw", "delete", "yield", "super", "as"},
    "bash": {"if", "then", "else", "elif", "fi", "for", "while", "in", "do", "done", "case", "esac", "function", "return", "echo", "local", "export", "readonly", "shift", "break", "continue", "exit", "read"},
    "sh": {"if", "then", "else", "elif", "fi", "for", "while", "in", "do", "done", "case", "esac", "function", "return", "echo", "local", "export", "readonly", "shift", "break", "continue", "exit", "read"},
    "json": {"true", "false", "null"},
    "html": {"class", "id", "style", "href", "src", "alt", "type", "name", "value", "placeholder"},
    "css": {"!important", "rgb", "rgba", "hsl", "hsla", "var", "calc", "url"},
}

_PATTERN = re.compile(
    r'(?P<string>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)'
    r'|(?P<comment>#.*|//.*|/\*.*?\*/)'
    r'|(?P<word>[A-Za-z_][A-Za-z0-9_]*)'
    r'|(?P<number>\b\d+(?:\.\d+)?\b)'
    r'|(?P<other>\s+|.)'
)

def highlight_code(line: str, lang: str) -> str:
    """Highlights a single line of code with ANSI escape sequences."""
    lang = lang.lower()
    keywords = _LANG_KEYWORDS.get(lang, _LANG_KEYWORDS["python"] | _LANG_KEYWORDS["javascript"])
    
    out = []
    prev_word = None
    
    for m in _PATTERN.finditer(line):
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
            elif prev_word in {"def", "class", "function", "interface", "type"}:
                out.append(f"{_FUNCTION}{text}{_RST}")
            else:
                out.append(text)
            prev_word = text
        else:
            if text.strip() and kind == "other":
                prev_word = None # Reset on punctuation
            out.append(text)
            
    return "".join(out)
