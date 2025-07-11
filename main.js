const { app, BrowserWindow, Tray, Menu, shell, session } = require('electron');
const path = require('path');

let mainWindow;
let tray;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    icon: path.join(__dirname, 'icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webviewTag: false,
      // Enable features needed for Flock
      plugins: true,
      webSecurity: true
    },
    // Better font rendering
    backgroundColor: '#ffffff',
    show: false
  });

  // Load Flock web app
  mainWindow.loadURL('https://web.flock.com', {
    userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  });

  // Handle external links
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Minimize to tray instead of closing
  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  // Enable desktop notifications
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.executeJavaScript(`
      if ("Notification" in window) {
        Notification.requestPermission();
      }
    `);
    
    // Start monitoring for unread messages
    monitorUnreadMessages();
  });
}

function createTray() {
  tray = new Tray(path.join(__dirname, 'tray-icon-mono.png'));
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Flock',
      click: () => {
        mainWindow.show();
        mainWindow.focus();
      }
    },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('Flock Chat');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    mainWindow.isVisible() ? mainWindow.hide() : mainWindow.show();
  });
}

app.whenReady().then(() => {
  // Set app name
  app.setName('Flock Chat');

  // Session configuration for better compatibility
  const ses = session.defaultSession;
  
  // Allow notifications
  ses.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowedPermissions = ['notifications', 'media', 'mediaKeySystem', 'clipboard-read'];
    if (allowedPermissions.includes(permission)) {
      callback(true);
    } else {
      callback(false);
    }
  });

  createWindow();
  createTray();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  } else {
    mainWindow.show();
  }
});

// Handle protocol for deep linking
app.setAsDefaultProtocolClient('flock');

// Monitor for unread messages
function monitorUnreadMessages() {
  setInterval(() => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.executeJavaScript(`
        // Check for unread messages in multiple ways
        (function() {
          // Check for unread badge in title
          const titleMatch = document.title.match(/\\((\\d+)\\)/);
          if (titleMatch) {
            return parseInt(titleMatch[1]) > 0;
          }
          
          // Check for unread indicators in DOM
          const unreadDots = document.querySelectorAll('.unread-dot, .unread-indicator, .badge-count');
          if (unreadDots.length > 0) {
            return true;
          }
          
          // Check for notification count in sidebar
          const notificationBadges = document.querySelectorAll('[class*="notification"], [class*="unread"], [class*="badge"]');
          for (let badge of notificationBadges) {
            const text = badge.textContent.trim();
            if (text && !isNaN(text) && parseInt(text) > 0) {
              return true;
            }
          }
          
          return false;
        })();
      `).then(hasUnread => {
        // Update tray icon based on unread status
        if (tray && !tray.isDestroyed()) {
          const iconPath = hasUnread 
            ? path.join(__dirname, 'tray-icon-green.png')
            : path.join(__dirname, 'tray-icon-mono.png');
          tray.setImage(iconPath);
        }
      }).catch(err => {
        // Silent fail - page might be loading
      });
    }
  }, 2000); // Check every 2 seconds
}