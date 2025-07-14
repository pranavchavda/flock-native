# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flock Native is a desktop wrapper for the Flock Chat web application that solves font rendering issues on Linux by providing a native Electron or Python/GTK alternative to Snap packages.

## Key Commands

### Development
- `npm install` - Install all dependencies
- `npm start` - Run the Electron application
- `./run-flock.sh` - Run with proper environment setup (recommended)
- `./run-flock-tray.sh` - Run Python/GTK version with tray support
- `python3 flock-tray.py` - Run Python version directly

### Build & Package
- `npm run install-electron` - Install Electron specifically
- No build step required - this is a runtime wrapper

## Architecture

### Core Components

1. **Electron Version** (`main.js`)
   - Main process creates BrowserWindow with WebView for https://web.flock.com
   - Injects JavaScript to monitor unread messages via `webContents.executeJavaScript()`
   - Updates tray icon between white (no unread) and green (unread messages)
   - Implements custom notification handling to bypass web notifications

2. **Python Alternative** (`flock-tray.py`)
   - Uses GTK3 + WebKit2 for rendering
   - AppIndicator3 for system tray integration
   - Similar unread monitoring via JavaScript injection

### Unread Message Detection
The app monitors for unread messages by:
- Checking page title for patterns like "(3) Flock"
- Querying DOM elements: `.zc-dm__text.unread`, `.zc-badge--notification`
- Extracting badge counts from sidebar elements
- Polling interval: 2 seconds

### Key Features Implementation
- **System Tray**: Dynamic icon switching based on unread status
- **Notifications**: Native desktop notifications with sender avatars
- **Deep Linking**: Handles `flock://` protocol URLs
- **Minimize to Tray**: Overrides close behavior to keep app running

## Important Notes

- Target platform: Linux (specifically Arch-based distributions)
- Font rendering fix: Sets `FREETYPE_PROPERTIES=truetype:interpreter-version=35`
- User agent spoofing required for web app compatibility
- Icons stored locally in: `flock-icon.png`, `flock-tray-white.png`, `flock-tray-green.png`
- Desktop integration via `.desktop` files for app launchers