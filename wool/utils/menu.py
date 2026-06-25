import os
import sys
import select
import termios
import tty
from typing import Callable
from wool.utils.ansi import bold, cyan, dim, green, red, white

def run_session_menu(sessions: list[str], active_session: str) -> tuple[str, str] | None:
    """
    Renders an interactive menu for sessions.
    Returns (action, session_name) where action is "switch" or "delete",
    or None if cancelled.
    """
    if not sessions:
        return None

    # Determine initial selected index (default to active session)
    try:
        selected_idx = sessions.index(active_session)
    except ValueError:
        selected_idx = 0

    delete_confirm_idx = -1

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def _render() -> None:
        # Move cursor up to overwrite previous lines if we've already printed
        # But for the very first render, we don't move up.
        # We will handle cursor movement in the loop.
        pass

    # Print the header once
    print(f"\n  {bold(cyan('Sessions:'))}")
    
    # We will print the list, then we will keep moving cursor up and reprinting.
    num_lines = len(sessions) + 3  # list + 1 blank line + 2 prompt lines

    def _render() -> None:
        try:
            import shutil
            term_width = shutil.get_terminal_size().columns
        except Exception:
            term_width = 80
            
        max_name_len = max(10, term_width - 12)
        
        lines = []
        for i, name in enumerate(sessions):
            display_name = name if len(name) <= max_name_len else name[:max_name_len-3] + "..."
            
            prefix = "❯" if i == selected_idx else " "
            if name == active_session:
                icon = green("●")
                colored_name = cyan(display_name) if i != delete_confirm_idx else red(display_name)
            else:
                icon = dim("○")
                colored_name = white(display_name) if i != delete_confirm_idx else red(display_name)
                
            if i == selected_idx:
                colored_name = bold(colored_name)
                
            color_prefix = cyan(prefix) if i == selected_idx else prefix
            lines.append(f"  {color_prefix} {icon} {colored_name}")
            
        lines.append("")
        if delete_confirm_idx != -1:
            lines.append(f"  {red('Press')} {bold(red('d'))} {red('again to confirm delete')}")
            lines.append(f"  {dim('or press any other key to cancel')}")
        else:
            lines.append(f"  {dim('↑/↓: move   Enter: switch')}")
            lines.append(f"  {dim('d: delete   q/Esc: cancel')}")
        
        # In raw mode, we must use \r\n
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\r\n")
        sys.stdout.flush()

    try:
        tty.setraw(sys.stdin.fileno())
        _render()
        
        while True:
            ch = os.read(fd, 1).decode("utf-8", errors="ignore")
            
            if ch == '\x03' or ch.lower() == 'q':  # Ctrl+C or q
                sys.stdout.write(f"\r\033[K\r\n")
                return None
                
            elif ch == '\r' or ch == '\n':  # Enter
                sys.stdout.write(f"\r\033[K\r\n")
                return "switch", sessions[selected_idx]
                
            elif ch.lower() == 'd':
                if delete_confirm_idx == selected_idx:
                    sys.stdout.write(f"\r\033[K\r\n")
                    return "delete", sessions[selected_idx]
                else:
                    delete_confirm_idx = selected_idx
            
            elif ch == '\x1b':  # Escape sequence
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    seq = os.read(fd, 2).decode("utf-8", errors="ignore")
                    if seq in ('[A', 'OA'):  # Up
                        selected_idx = (selected_idx - 1) % len(sessions)
                        delete_confirm_idx = -1
                    elif seq in ('[B', 'OB'):  # Down
                        selected_idx = (selected_idx + 1) % len(sessions)
                        delete_confirm_idx = -1
                else:
                    sys.stdout.write(f"\r\033[K\r\n")
                    return None
            
            else:
                delete_confirm_idx = -1

            # Move cursor back up
            sys.stdout.write(f"\r\033[{num_lines}A")
            _render()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
