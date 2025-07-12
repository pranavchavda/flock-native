#!/bin/bash
# Launcher script for Flock Native Python Tray version

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed."
    exit 1
fi

# Check if AppIndicator3 is available
if ! python3 -c "import gi; gi.require_version('AppIndicator3', '0.1')" &> /dev/null; then
    echo "AppIndicator3 is required. Install with: sudo pacman -S libappindicator-gtk3"
    exit 1
fi

# Launch the Python tray version
exec python3 "$SCRIPT_DIR/flock-tray.py" "$@"