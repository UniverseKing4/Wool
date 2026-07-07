import os
import select
import shutil
import sys
import termios
import tty

from wool.utils.ansi import bold, cyan, dim, green, red, white


def run_session_menu(
    sessions: list[str], active_session: str, initial_idx: int = -1
) -> tuple[str, str, int] | None:
    """
    Renders an interactive menu for sessions.
    Returns (action, session_name, last_idx) where action is "switch" or "delete",
    or None if cancelled.
    """
    if not sessions:
        return None

    if 0 <= initial_idx < len(sessions):
        selected_idx = initial_idx
    else:
        try:
            selected_idx = sessions.index(active_session)
        except ValueError:
            selected_idx = 0

    delete_confirm_idx = -1

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    print(f"\n  {bold(cyan('Sessions:'))}")

    try:
        term_lines = shutil.get_terminal_size().lines
    except Exception:
        term_lines = 24
    max_display = max(5, term_lines - 8)

    def _render(offset: int, sel: int) -> list[str]:
        try:
            term_width = shutil.get_terminal_size().columns
        except Exception:
            term_width = 80

        max_name_len = max(10, term_width - 12)

        lines = []
        visible = sessions[offset : offset + max_display]
        for i, name in enumerate(visible):
            actual_idx = offset + i
            display_name = (
                name if len(name) <= max_name_len else name[: max_name_len - 3] + "..."
            )

            prefix = "❯" if actual_idx == sel else " "
            if name == active_session:
                icon = green("●")
                colored_name = (
                    cyan(display_name)
                    if actual_idx != delete_confirm_idx
                    else red(display_name)
                )
            else:
                icon = dim("○")
                colored_name = (
                    white(display_name)
                    if actual_idx != delete_confirm_idx
                    else red(display_name)
                )

            if actual_idx == sel:
                colored_name = bold(colored_name)

            color_prefix = cyan(prefix) if actual_idx == sel else prefix
            lines.append(f"  {color_prefix} {icon} {colored_name}")

        lines.append("")
        if delete_confirm_idx != -1:
            lines.append(
                f"  {red('Press')} {bold(red('d'))} {red('again to confirm delete')}"
            )
            lines.append(f"  {dim('or press any other key to cancel')}")
        else:
            lines.append(f"  {dim('↑/↓: move   Enter: switch')}")
            lines.append(f"  {dim('d: delete   q/Esc: cancel')}")
        return lines

    # Make sure offset keeps the selected item in view
    offset = max(0, min(selected_idx - max_display // 2, len(sessions) - max_display))
    if selected_idx < offset:
        offset = selected_idx

    def _draw():
        lines = _render(offset, selected_idx)
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\r\n")
        sys.stdout.flush()
        return len(lines)

    try:
        tty.setraw(sys.stdin.fileno())
        num_lines = _draw()

        while True:
            ch = os.read(fd, 1).decode("utf-8", errors="ignore")
            if not ch:
                sys.stdout.write("\r\033[K\r\n")
                return None

            if ch == "\x03" or ch.lower() == "q":  # Ctrl+C or q
                sys.stdout.write("\r\033[K\r\n")
                return None

            elif ch == "\r" or ch == "\n":  # Enter
                sys.stdout.write("\r\033[K\r\n")
                return "switch", sessions[selected_idx], selected_idx

            elif ch.lower() == "d":
                if delete_confirm_idx == selected_idx:
                    sys.stdout.write("\r\033[K\r\n")
                    return "delete", sessions[selected_idx], selected_idx
                else:
                    delete_confirm_idx = selected_idx

            elif ch == "\x1b":  # Escape sequence
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    seq = os.read(fd, 2).decode("utf-8", errors="ignore")
                    if seq in ("[A", "OA"):  # Up
                        selected_idx = (selected_idx - 1) % len(sessions)
                        if selected_idx < offset:
                            offset = selected_idx
                        elif selected_idx >= offset + max_display:
                            offset = selected_idx - max_display + 1
                        delete_confirm_idx = -1
                    elif seq in ("[B", "OB"):  # Down
                        selected_idx = (selected_idx + 1) % len(sessions)
                        if selected_idx >= offset + max_display:
                            offset = selected_idx - max_display + 1
                        elif selected_idx < offset:
                            offset = selected_idx
                        delete_confirm_idx = -1
                else:
                    sys.stdout.write("\r\033[K\r\n")
                    return None

            else:
                delete_confirm_idx = -1

            # Move cursor back up
            sys.stdout.write(f"\r\033[{num_lines}A")
            num_lines = _draw()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def run_rewind_menu(messages: list[tuple[int, str]]) -> int | None:
    """
    Renders an interactive menu for rewinding.
    messages is a list of (msg_index, snippet).
    Returns the msg_index to rewind to, or None if cancelled.
    """
    if not messages:
        return None

    selected_idx = len(messages) - 1
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    print(f"\n  {bold(cyan('Select message to rewind to:'))}")

    # At most we show 10 messages to avoid breaking the screen if there are too many.
    # Actually, let's just show all of them or up to 15.
    max_display = 15

    try:
        term_width = shutil.get_terminal_size().columns
    except Exception:
        term_width = 80

    def _render(offset: int, sel: int) -> list[str]:
        max_len = max(10, term_width - 6)
        lines = []
        visible = messages[offset : offset + max_display]
        for i, (msg_idx, snippet) in enumerate(visible):
            actual_idx = offset + i
            prefix = "❯" if actual_idx == sel else " "

            # Truncate strictly to terminal width to prevent line wrapping which breaks stdout cursor up logic.
            display_snippet = (
                snippet if len(snippet) <= max_len else snippet[: max_len - 3] + "..."
            )

            colored = (
                cyan(display_snippet) if actual_idx == sel else white(display_snippet)
            )
            if actual_idx == sel:
                colored = bold(colored)

            color_prefix = cyan(prefix) if actual_idx == sel else prefix
            lines.append(f"  {color_prefix} {colored}")

        lines.append("")
        lines.append(f"  {dim('↑/↓: move   Enter: rewind   q/Esc: cancel')}")
        return lines

    offset = max(0, len(messages) - max_display)

    def _draw():
        lines = _render(offset, selected_idx)
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\r\n")
        sys.stdout.flush()
        return len(lines)

    try:
        tty.setraw(sys.stdin.fileno())
        num_lines = _draw()

        while True:
            ch = os.read(fd, 1).decode("utf-8", errors="ignore")
            if not ch:
                sys.stdout.write("\r\033[K\r\n")
                return None

            if ch == "\x03" or ch.lower() == "q":
                sys.stdout.write("\r\033[K\r\n")
                return None

            elif ch == "\r" or ch == "\n":
                sys.stdout.write("\r\033[K\r\n")
                return messages[selected_idx][0]

            elif ch == "\x1b":
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    seq = os.read(fd, 2).decode("utf-8", errors="ignore")
                    if seq in ("[A", "OA"):  # Up
                        selected_idx = max(0, selected_idx - 1)
                        if selected_idx < offset:
                            offset = selected_idx
                    elif seq in ("[B", "OB"):  # Down
                        selected_idx = min(len(messages) - 1, selected_idx + 1)
                        if selected_idx >= offset + max_display:
                            offset = selected_idx - max_display + 1
                else:
                    sys.stdout.write("\r\033[K\r\n")
                    return None

            sys.stdout.write(f"\r\033[{num_lines}A")
            num_lines = _draw()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def run_settings_menu(config) -> None:
    """
    Renders an interactive menu for settings.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    selected_idx = 0
    # Currently only one setting
    options = ["restrict_workspace"]

    print(f"\n  {bold(cyan('Settings:'))}")

    def _render(sel: int) -> list[str]:
        lines = []
        for i, opt in enumerate(options):
            prefix = "❯" if i == sel else " "
            if opt == "restrict_workspace":
                val_str = green("ON") if config.restrict_workspace else red("OFF")
                name_str = "Workspace restriction (current folder only)"
            else:
                val_str = "?"
                name_str = opt
            
            color_prefix = cyan(prefix) if i == sel else prefix
            colored_name = cyan(name_str) if i == sel else white(name_str)
            if i == sel:
                colored_name = bold(colored_name)
            
            lines.append(f"  {color_prefix} {colored_name}: [{val_str}]")

        lines.append("")
        lines.append(f"  {dim('↑/↓: move   Enter: toggle   q/Esc: exit')}")
        return lines

    def _draw():
        lines = _render(selected_idx)
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\r\n")
        sys.stdout.flush()
        return len(lines)

    try:
        tty.setraw(sys.stdin.fileno())
        num_lines = _draw()

        while True:
            ch = os.read(fd, 1).decode("utf-8", errors="ignore")
            if not ch:
                sys.stdout.write("\r\033[K\r\n")
                return None

            if ch == "\x03" or ch.lower() == "q":
                sys.stdout.write("\r\033[K\r\n")
                return

            elif ch == "\r" or ch == "\n":
                opt = options[selected_idx]
                if opt == "restrict_workspace":
                    config.restrict_workspace = not config.restrict_workspace
                    config.save()
                    # Also update the global flag in base.py
                    import wool.tools.base as base
                    base.IS_RESTRICTED = config.restrict_workspace
                
                # Redraw
                sys.stdout.write(f"\r\033[{num_lines}A")
                num_lines = _draw()

            elif ch == "\x1b":
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    seq = os.read(fd, 2).decode("utf-8", errors="ignore")
                    if seq in ("[A", "OA"):  # Up
                        selected_idx = max(0, selected_idx - 1)
                    elif seq in ("[B", "OB"):  # Down
                        selected_idx = min(len(options) - 1, selected_idx + 1)
                else:
                    sys.stdout.write("\r\033[K\r\n")
                    return

                sys.stdout.write(f"\r\033[{num_lines}A")
                num_lines = _draw()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def run_list_menu(
    title: str, items: list[str], active_item: str | None
) -> str | None:
    """
    Renders an interactive menu for selecting an item from a list.
    Returns the selected item, or None if cancelled.
    """
    if not items:
        return None

    try:
        selected_idx = items.index(active_item) if active_item in items else 0
    except ValueError:
        selected_idx = 0

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    print(f"\n  {bold(cyan(title))}")

    try:
        term_lines = shutil.get_terminal_size().lines
    except Exception:
        term_lines = 24
    max_display = max(5, term_lines - 8)

    def _render(offset: int, sel: int) -> list[str]:
        try:
            term_width = shutil.get_terminal_size().columns
        except Exception:
            term_width = 80

        max_name_len = max(10, term_width - 12)
        lines = []
        visible = items[offset : offset + max_display]
        for i, name in enumerate(visible):
            actual_idx = offset + i
            display_name = (
                name if len(name) <= max_name_len else name[: max_name_len - 3] + "..."
            )

            prefix = "❯" if actual_idx == sel else " "
            if name == active_item:
                icon = green("●")
                colored_name = cyan(display_name)
            else:
                icon = dim("○")
                colored_name = white(display_name)

            if actual_idx == sel:
                colored_name = bold(colored_name)

            color_prefix = cyan(prefix) if actual_idx == sel else prefix
            lines.append(f"  {color_prefix} {icon} {colored_name}")

        lines.append("")
        lines.append(f"  {dim('↑/↓: move   Enter: select   q/Esc: cancel')}")
        return lines

    offset = max(0, min(selected_idx - max_display // 2, len(items) - max_display))
    if selected_idx < offset:
        offset = selected_idx

    def _draw():
        lines = _render(offset, selected_idx)
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\r\n")
        sys.stdout.flush()
        return len(lines)

    try:
        tty.setraw(sys.stdin.fileno())
        num_lines = _draw()

        while True:
            ch = os.read(fd, 1).decode("utf-8", errors="ignore")
            if not ch:
                sys.stdout.write("\r\033[K\r\n")
                return None

            if ch == "\x03" or ch.lower() == "q":  # Ctrl+C or q
                sys.stdout.write("\r\033[K\r\n")
                return None

            elif ch == "\r" or ch == "\n":  # Enter
                sys.stdout.write("\r\033[K\r\n")
                return items[selected_idx]

            elif ch == "\x1b":  # Escape sequence
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    seq = os.read(fd, 2).decode("utf-8", errors="ignore")
                    if seq in ("[A", "OA"):  # Up
                        selected_idx = (selected_idx - 1) % len(items)
                        if selected_idx < offset:
                            offset = selected_idx
                        elif selected_idx >= offset + max_display:
                            offset = selected_idx - max_display + 1
                    elif seq in ("[B", "OB"):  # Down
                        selected_idx = (selected_idx + 1) % len(items)
                        if selected_idx >= offset + max_display:
                            offset = selected_idx - max_display + 1
                        elif selected_idx < offset:
                            offset = selected_idx
                else:
                    sys.stdout.write("\r\033[K\r\n")
                    return None

            sys.stdout.write(f"\r\033[{num_lines}A")
            num_lines = _draw()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def run_tools_menu(
    config, built_in_tools: list, mcp_tools: list
) -> None:
    """
    Renders an interactive menu for tools.
    Supports toggling built-in tools.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    active_tab = 0  # 0 for built-in, 1 for MCP
    tabs = ["Built-in Tools"]
    if mcp_tools:
        tabs.append("MCP Tools")

    selected_idx = 0
    offset = 0

    try:
        term_lines = shutil.get_terminal_size().lines
    except Exception:
        term_lines = 24
    max_display = max(5, term_lines - 8)

    def _render(tab: int, sel: int, off: int) -> list[str]:
        try:
            term_width = shutil.get_terminal_size().columns
        except Exception:
            term_width = 80

        lines = []
        
        # Tabs header
        tab_str = ""
        for i, t in enumerate(tabs):
            if i == tab:
                tab_str += f"  {bold(cyan(t))}  "
            else:
                tab_str += f"  {dim(t)}  "
        lines.append("")
        lines.append(tab_str)
        lines.append("")
        
        current_list = built_in_tools if tab == 0 else mcp_tools
        
        # List tools
        if not current_list:
            lines.append(f"  {dim('No tools available.')}")
        else:
            visible = current_list[off : off + max_display]
            for i, tool in enumerate(visible):
                actual_idx = off + i
                prefix = "❯" if actual_idx == sel else " "
                
                if tab == 0:
                    name = tool.name
                    desc = tool.description
                    is_disabled = name in config.disabled_tools
                    status = dim("○") if is_disabled else green("●")
                else:
                    fn = tool.get("function", {})
                    name = fn.get("name", "?")
                    desc = fn.get("description", "")
                    status = green("●")
                
                # Truncate description to fit terminal width
                max_desc_len = max(5, term_width - 40)
                desc = desc.replace("\n", " ").strip()
                if len(desc) > max_desc_len:
                    desc = desc[:max_desc_len - 3] + "..."
                
                name_padded = f"{name:<25s}"
                color_prefix = cyan(prefix) if actual_idx == sel else prefix
                colored_name = cyan(name_padded) if actual_idx == sel else white(name_padded)
                if actual_idx == sel:
                    colored_name = bold(colored_name)
                
                lines.append(f"  {color_prefix} {status} {colored_name} {dim(desc)}")

        lines.append("")
        if tab == 0:
            lines.append(f"  {dim('←/→: switch tabs   ↑/↓: move   Enter: toggle   q/Esc: exit')}")
        else:
            lines.append(f"  {dim('←/→: switch tabs   ↑/↓: move   q/Esc: exit')}")
            
        return lines

    def _draw():
        lines = _render(active_tab, selected_idx, offset)
        for line in lines:
            sys.stdout.write(f"\r\033[K{line}\r\n")
        sys.stdout.flush()
        return len(lines)

    try:
        tty.setraw(sys.stdin.fileno())
        num_lines = _draw()

        while True:
            ch = os.read(fd, 1).decode("utf-8", errors="ignore")
            if not ch:
                sys.stdout.write("\r\033[K\r\n")
                return None

            if ch == "\x03" or ch.lower() == "q":
                sys.stdout.write("\r\033[K\r\n")
                return

            elif ch == "\r" or ch == "\n":
                if active_tab == 0 and built_in_tools:
                    tool = built_in_tools[selected_idx]
                    if tool.name in config.disabled_tools:
                        config.disabled_tools.remove(tool.name)
                    else:
                        config.disabled_tools.append(tool.name)
                    config.save()
                
                sys.stdout.write(f"\r\033[{num_lines}A")
                num_lines = _draw()

            elif ch == "\x1b":
                r, _, _ = select.select([fd], [], [], 0.05)
                if r:
                    seq = os.read(fd, 2).decode("utf-8", errors="ignore")
                    current_list = built_in_tools if active_tab == 0 else mcp_tools
                    if seq in ("[C", "OC"):  # Right
                        if len(tabs) > 1 and active_tab == 0:
                            active_tab = 1
                            selected_idx = 0
                            offset = 0
                    elif seq in ("[D", "OD"):  # Left
                        if active_tab == 1:
                            active_tab = 0
                            selected_idx = 0
                            offset = 0
                    elif seq in ("[A", "OA"):  # Up
                        selected_idx = max(0, selected_idx - 1)
                        if selected_idx < offset:
                            offset = selected_idx
                    elif seq in ("[B", "OB"):  # Down
                        if current_list:
                            selected_idx = min(len(current_list) - 1, selected_idx + 1)
                            if selected_idx >= offset + max_display:
                                offset = selected_idx - max_display + 1
                else:
                    sys.stdout.write("\r\033[K\r\n")
                    return

                sys.stdout.write(f"\r\033[{num_lines}A")
                num_lines = _draw()

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
