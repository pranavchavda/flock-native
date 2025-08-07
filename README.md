# Flock Native - Electron Wrapper for Flock Chat

A native Electron wrapper for Flock Chat that fixes font rendering issues on Linux and provides a proper system tray with unread message indicators.

## The Problem

The official Flock Snap package on Linux (especially on Arch-based distros like EndeavourOS) has several issues:
- **Poor font rendering**: Fonts appear blurry and poorly anti-aliased due to Snap's sandboxing
- **No system font access**: Cannot use your carefully configured system fonts
- **Missing system tray features**: Basic tray functionality with no unread indicators

## The Solution

This Electron wrapper runs Flock's web app natively on your system, bypassing Snap's limitations:
- ✅ **Crystal clear fonts**: Uses your system's font rendering
- ✅ **Smart tray icon**: Monochrome icon that turns green when you have unread messages
- ✅ **Minimize to tray**: Close button minimizes to tray instead of quitting
- ✅ **Native notifications**: Full system notification support
- ✅ **Autostart support**: Proper .desktop file for session autostart

## Installation

### Prerequisites

- Node.js and npm (for Electron version)
- Python 3 with GTK bindings (for Python versions)
- AppIndicator3 (for Python tray version): `sudo pacman -S libappindicator-gtk3`
- Git

### Quick Install

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/flock-native.git ~/.config/flock-native
cd ~/.config/flock-native

# Install dependencies
npm install

# Make the launcher executable
chmod +x run-flock.sh

# Run the app
./run-flock.sh
```

### Desktop Integration

The app includes .desktop files for proper desktop integration:

```bash
# Copy desktop file for app launcher
cp ~/.config/flock-native/flock-native.desktop ~/.local/share/applications/

# Enable autostart (optional)
cp ~/.config/flock-native/flock-native.desktop ~/.config/autostart/
```

### Disable Snap Version Autostart

If you have the Snap version installed and want to prevent it from autostarting:

```bash
echo "Hidden=true" >> ~/.config/autostart/flock-chat_flock-chat.desktop
```

## Features

### Smart Tray Icon

The tray icon changes color based on unread message status:
- **White/Monochrome**: No unread messages
- **Green**: You have unread messages

The app monitors for unread messages by checking:
- Page title for notification counts (e.g., "(3) Flock")
- DOM elements with unread indicators
- Badge counts in the sidebar

### LanguageTool Integration (Electron Version)

The Electron version includes built-in LanguageTool support for grammar and spell checking:
- **Automatic download**: LanguageTool server is downloaded on first run if not present
- **Local server**: Runs LanguageTool locally on port 8081 for privacy and speed
- **Seamless integration**: Works automatically with text inputs in Flock
- **No external dependencies**: Self-contained Java runtime included with LanguageTool

### Window Management

- **Close to tray**: Closing the window minimizes to tray instead of quitting
- **Tray menu**: Right-click the tray icon for options:
  - Show/Hide window
  - Quit application

## Alternative: Python Versions

If you don't want to install Node.js, there are Python/GTK alternatives:

### Python with Tray Support (Recommended)

```bash
python3 ~/.config/flock-native/flock-tray.py
```

This version includes:
- System tray icon with unread message indicators (same as Electron version)
- Minimize to tray functionality
- Right-click menu on tray icon

**Dependencies**: `python3-gi`, `gir1.2-appindicator3-0.1`, `gir1.2-webkit2-4.0`

### Simple Python Version (No Tray)

```bash
python3 ~/.config/flock-native/flock-simple.py
```

A minimal version without tray support - just a simple browser window.

## Troubleshooting

### Fonts still look bad
Make sure you have proper font configuration in your system. The app uses your system's fontconfig settings.

### Tray icon not showing
- Check that your window manager supports system tray (most do)
- For i3wm users: ensure you have a system tray in your bar configuration

### Can't see icon color changes
The monochrome and green icons are designed for both light and dark tray backgrounds. If you have visibility issues, you can replace the PNG files in the app directory.

## Technical Details

This wrapper:
- Uses Electron to run Flock's web app (https://web.flock.com)
- Monitors the page for unread message indicators every 2 seconds
- Stores window position and size between sessions
- Handles deep linking for `flock://` URLs

## Contributing

Feel free to submit issues and pull requests! Some ideas for improvement:
- Custom icon themes
- More granular notification controls
- Keyboard shortcuts
- Multiple account support

## License

MIT License - See LICENSE file for details

## Credits

Created to solve font rendering issues with the official Snap package on Arch Linux/EndeavourOS.

---

**Note**: This is an unofficial wrapper for Flock Chat. All trademarks belong to their respective owners.