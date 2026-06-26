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

# We will use pipx if available, otherwise pip --user.
if ! command_exists pipx; then
    echo -e "${BLUE}ℹ Setting up isolated installation (pipx)...${NC}"
    if [ "$PM" = "pkg" ]; then
        python3 -m pip install --upgrade pip
        python3 -m pip install pipx
    else
        python3 -m pip install --user --upgrade pipx || python3 -m pip install --user --break-system-packages pipx || true
    fi
fi

export PATH="$PATH:$HOME/.local/bin"

if command_exists pipx; then
    pipx ensurepath >/dev/null 2>&1 || true
    pipx install --force "git+https://github.com/UniverseKing4/Wool.git"
else
    echo -e "${YELLOW}ℹ pipx not found, falling back to pip install --user...${NC}"
    python3 -m pip install --user --upgrade --force-reinstall --break-system-packages "git+https://github.com/UniverseKing4/Wool.git" || \
    python3 -m pip install --user --upgrade --force-reinstall "git+https://github.com/UniverseKing4/Wool.git"
fi

# Ensure ~/.local/bin is in PATH if not already
SHELL_PROFILE=""
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    if [ -n "$ZSH_VERSION" ] || [ -f "$HOME/.zshrc" ]; then
        SHELL_PROFILE="$HOME/.zshrc"
    elif [ -n "$BASH_VERSION" ] || [ -f "$HOME/.bashrc" ]; then
        SHELL_PROFILE="$HOME/.bashrc"
    else
        SHELL_PROFILE="$HOME/.profile"
    fi
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_PROFILE"
    echo -e "${BLUE}ℹ Added ~/.local/bin to your PATH in $SHELL_PROFILE${NC}"
fi

echo ""
echo -e "${GREEN}✓ Wool installed successfully! 🐑${NC}"
if [ -n "$SHELL_PROFILE" ]; then
    echo -e "Please restart your terminal or run: ${BOLD}source $SHELL_PROFILE${NC}"
fi
echo -e "You can then run it by typing: ${BOLD}wool${NC}"
