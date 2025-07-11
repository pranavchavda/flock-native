#!/bin/bash

cd "$(dirname "$0")"

# Check if electron is installed
if [ ! -d "node_modules/electron" ]; then
    echo "Installing Electron..."
    npm install electron
fi

# Download icon if not present
if [ ! -f "icon.png" ]; then
    echo "Downloading Flock icon..."
    curl -s -o icon.png "https://web.flock.com/favicon.ico" || \
    curl -s -o icon.png "https://raw.githubusercontent.com/flockos/icons/master/flock-icon.png" || \
    echo "Could not download icon, continuing without it"
fi

# Run with proper font configuration
export ELECTRON_FORCE_IS_PACKAGED=true
export ELECTRON_ENABLE_FEATURES="UseOzonePlatform"
export ELECTRON_OZONE_PLATFORM_HINT="auto"

# Launch Flock
exec npm start "$@"