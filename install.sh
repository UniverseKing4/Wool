#!/usr/bin/env bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BLUE}🐑 Installing Wool AI CLI...${NC}"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Detect environment and package manager
PM=""
IS_TERMUX=false
if command_exists pkg && [ -n "$TERMUX_VERSION" ]; then
    PM="pkg"
    IS_TERMUX=true
    echo -e "${BLUE}ℹ Android Termux environment detected.${NC}"
elif command_exists apt-get; then
    PM="apt-get"
elif command_exists pacman; then
    PM="pacman"
elif command_exists dnf; then
    PM="dnf"
elif command_exists zypper; then
    PM="zypper"
elif command_exists yum; then
    PM="yum"
elif command_exists apk; then
    PM="apk"
else
    echo -e "${YELLOW}⚠ Unsupported package manager. Auto-install of dependencies might fail.${NC}"
fi

# 2. Check dependencies
NEEDS_PYTHON=false
NEEDS_GIT=false

if ! command_exists python3; then
    NEEDS_PYTHON=true
else
    # Check version >= 3.11
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
    if $(python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null); then
        echo -e "${GREEN}✓ Python $PY_VER detected.${NC}"
    else
        echo -e "${YELLOW}ℹ Python version is $PY_VER, need 3.11+. Will attempt to upgrade.${NC}"
        NEEDS_PYTHON=true
    fi
fi

if ! command_exists git; then
    NEEDS_GIT=true
else
    echo -e "${GREEN}✓ Git detected.${NC}"
fi

# 3. Install missing dependencies
if [ "$NEEDS_PYTHON" = true ] || [ "$NEEDS_GIT" = true ] || [ "$IS_TERMUX" = true ]; then
    if [ -n "$PM" ]; then
        echo -e "${BLUE}ℹ Installing missing dependencies using $PM...${NC}"
        
        # Needs root unless termux
        SUDO=""
        if [ "$PM" != "pkg" ] && [ "$(id -u)" -ne 0 ] && command_exists sudo; then
            SUDO="sudo"
        fi

        if [ "$PM" = "pkg" ]; then
            $SUDO pkg update -y
            [ "$NEEDS_PYTHON" = true ] && $SUDO pkg install -y python
            [ "$NEEDS_GIT" = true ] && $SUDO pkg install -y git
            $SUDO pkg install -y termux-api  # required for clipboard support in wool
        elif [ "$PM" = "apt-get" ]; then
            $SUDO apt-get update -y
            [ "$NEEDS_PYTHON" = true ] && $SUDO apt-get install -y python3 python3-pip python3-venv
            [ "$NEEDS_GIT" = true ] && $SUDO apt-get install -y git
        elif [ "$PM" = "pacman" ]; then
            $SUDO pacman -Sy --noconfirm
            [ "$NEEDS_PYTHON" = true ] && $SUDO pacman -S --noconfirm python python-pip
            [ "$NEEDS_GIT" = true ] && $SUDO pacman -S --noconfirm git
        elif [ "$PM" = "dnf" ] || [ "$PM" = "yum" ]; then
            [ "$NEEDS_PYTHON" = true ] && $SUDO $PM install -y python3 python3-pip
            [ "$NEEDS_GIT" = true ] && $SUDO $PM install -y git
        elif [ "$PM" = "zypper" ]; then
            [ "$NEEDS_PYTHON" = true ] && $SUDO zypper install -y python3 python3-pip
            [ "$NEEDS_GIT" = true ] && $SUDO zypper install -y git
        elif [ "$PM" = "apk" ]; then
            $SUDO apk add --update
            [ "$NEEDS_PYTHON" = true ] && $SUDO apk add python3 py3-pip
            [ "$NEEDS_GIT" = true ] && $SUDO apk add git
        fi
    fi
fi

# 4. Final verification
if ! command_exists python3; then
    echo -e "${RED}✗ Failed to install Python 3. Please install manually.${NC}"
    exit 1
fi
if ! command_exists git; then
    echo -e "${RED}✗ Failed to install Git. Please install manually.${NC}"
    exit 1
fi

# 5. Download & Install Wool
echo -e "${BLUE}ℹ Downloading and installing Wool...${NC}"

if [ "$IS_TERMUX" = true ]; then
    # Termux forbids pip install --upgrade pip and pipx is unnecessary.
    # Use pip directly — Termux doesn't enforce --user or --break-system-packages.
    pip install --upgrade --force-reinstall "git+https://github.com/UniverseKing4/Wool.git"
else
    # On standard Linux, prefer pipx for isolated installs.
    if ! command_exists pipx; then
        echo -e "${BLUE}ℹ Setting up isolated installation (pipx)...${NC}"
        python3 -m pip install --user --upgrade pipx 2>/dev/null || \
        python3 -m pip install --user --break-system-packages pipx 2>/dev/null || true
    fi

    export PATH="$PATH:$HOME/.local/bin"

    if command_exists pipx; then
        pipx ensurepath >/dev/null 2>&1 || true
        pipx install --force "git+https://github.com/UniverseKing4/Wool.git"
    else
        echo -e "${YELLOW}ℹ pipx not available, using pip install --user...${NC}"
        python3 -m pip install --user --upgrade --force-reinstall --break-system-packages "git+https://github.com/UniverseKing4/Wool.git" 2>/dev/null || \
        python3 -m pip install --user --upgrade --force-reinstall "git+https://github.com/UniverseKing4/Wool.git"
    fi
fi

# Detect the user's ACTUAL login shell (not the script runner)
CURRENT_SHELL=$(basename "$SHELL" 2>/dev/null || echo "bash")

if [ "$CURRENT_SHELL" = "zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
    RECOMMENDED_SOURCE="source ~/.zshrc"
elif [ "$CURRENT_SHELL" = "fish" ]; then
    SHELL_RC="$HOME/.config/fish/config.fish"
    RECOMMENDED_SOURCE="source ~/.config/fish/config.fish"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
    RECOMMENDED_SOURCE="source ~/.bashrc"
else
    SHELL_RC="$HOME/.profile"
    RECOMMENDED_SOURCE="source ~/.profile"
fi

# Ensure ~/.local/bin is in the user's shell profile if not already present
if ! grep -qF '.local/bin' "$SHELL_RC" 2>/dev/null; then
    echo '' >> "$SHELL_RC"
    echo '# Added by Wool installer' >> "$SHELL_RC"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_RC"
    echo -e "${BLUE}ℹ Added ~/.local/bin to PATH in $SHELL_RC${NC}"
fi

echo ""
echo -e "${GREEN}────────────────────────────────────────${NC}"
echo -e "${GREEN}  ✓ Wool installed successfully! 🐑${NC}"
echo -e "${GREEN}────────────────────────────────────────${NC}"
echo ""
echo -e "  To get started, run:"
echo -e "    ${BOLD}${RECOMMENDED_SOURCE}${NC}"
echo -e "    ${BOLD}wool${NC}"
echo ""
echo -e "  ${BLUE}Or simply restart your terminal, then type: ${BOLD}wool${NC}"
echo ""
