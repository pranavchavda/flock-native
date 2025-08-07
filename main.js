const { app, BrowserWindow, Tray, Menu, shell, session } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let tray;
let languageToolProcess;

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
  // Add keyboard shortcut for grammar check (Ctrl+Shift+G)
  mainWindow.webContents.on('before-input-event', (event, input) => {
    if (input.control && input.shift && input.key === 'G') {
      console.log('Grammar check shortcut triggered - forcing check');
      // Force immediate grammar check
      mainWindow.webContents.executeJavaScript(`
        const activeElement = document.activeElement;
        const text = (activeElement && (activeElement.value || activeElement.innerText)) || window.getSelection().toString() || '';
        
        if (text && text.length > 0) {
          console.log('Force checking grammar for:', text);
          window.currentErrorElement = activeElement;
          window.checkGrammar(text, activeElement).then(errors => {
            if (errors && errors.length > 0) {
              console.log('Found', errors.length, 'grammar issues');
              // Also show in alert for now as backup
              const issues = errors.map(m => '• ' + m.message + (m.replacements && m.replacements.length > 0 ? ' (Suggestion: ' + m.replacements[0].value + ')' : '')).join('\\n');
              alert('Grammar Check Results:\\n\\n' + issues + '\\n\\nNote: Errors should be underlined in the text. Right-click on underlined words for corrections.');
            } else {
              alert('No grammar issues found!');
            }
          }).catch(err => {
            console.error('Grammar check failed:', err);
          });
        } else {
          alert('Please type or select some text first');
        }
      `).catch(err => console.error('Grammar check script failed:', err));
      event.preventDefault();
    }
  });
  
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

function startLanguageTool() {
  // Check if LanguageTool is installed
  const ltPath = path.join(__dirname, 'LanguageTool-6.6');
  const ltJar = path.join(ltPath, 'languagetool-server.jar');
  
  if (!fs.existsSync(ltJar)) {
    console.log('LanguageTool not found at:', ltJar);
    console.log('Please extract LanguageTool.zip first');
    return;
  }
  
  console.log('Starting LanguageTool server...');
  
  // Start LanguageTool server on port 8081
  languageToolProcess = spawn('java', [
    '-cp', ltJar,
    'org.languagetool.server.HTTPServer',
    '--port', '8081',
    '--allow-origin', '*'
  ], {
    cwd: ltPath,
    detached: false
  });
  
  languageToolProcess.stdout.on('data', (data) => {
    console.log(`LanguageTool: ${data}`);
  });
  
  languageToolProcess.stderr.on('data', (data) => {
    console.error(`LanguageTool Error: ${data}`);
  });
  
  languageToolProcess.on('close', (code) => {
    console.log(`LanguageTool server exited with code ${code}`);
    languageToolProcess = null;
  });
  
  // Give the server time to start
  setTimeout(() => {
    console.log('LanguageTool should be available at http://127.0.0.1:8081');
    // Inject after a delay, regardless of page load state
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        injectLanguageToolIntegration();
      }
    }, 5000); // Give both server and page time to be ready
  }, 3000);
}

function injectLanguageToolIntegration() {
  if (!mainWindow) return;
  
  console.log('Injecting advanced LanguageTool integration...');
  
  const advancedScript = `
    (function() {
      // Store grammar errors for the current input
      window.grammarErrors = [];
      window.currentErrorElement = null;
      
      // Add CSS for grammar error highlighting
      if (!document.getElementById('grammar-styles')) {
        const style = document.createElement('style');
        style.id = 'grammar-styles';
        style.textContent = \`
          .grammar-error {
            background: linear-gradient(to bottom, transparent 75%, #FFA500 75%, #FFA500 85%, transparent 85%);
            background-position: 0 100%;
            background-repeat: repeat-x;
            cursor: context-menu;
          }
          
          .grammar-error-severe {
            background: linear-gradient(to bottom, transparent 75%, #FF4444 75%, #FF4444 85%, transparent 85%);
            background-position: 0 100%;
            background-repeat: repeat-x;
          }
          
          .grammar-popup {
            position: absolute;
            background: white;
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            z-index: 10000;
            max-width: 400px;
            font-size: 14px;
            color: #333;
          }
          
          .grammar-popup-item {
            padding: 4px 8px;
            cursor: pointer;
            border-radius: 3px;
          }
          
          .grammar-popup-item:hover {
            background: #f0f0f0;
          }
          
          .grammar-popup-message {
            padding: 4px 8px;
            font-weight: bold;
            border-bottom: 1px solid #eee;
            margin-bottom: 4px;
          }
        \`;
        document.head.appendChild(style);
      }
      
      // Check grammar function
      window.checkGrammar = async function(text, element) {
        try {
          const response = await fetch('http://127.0.0.1:8081/v2/check', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: 'text=' + encodeURIComponent(text) + '&language=en-US'
          });
          
          const data = await response.json();
          window.grammarErrors = data.matches || [];
          
          if (element) {
            highlightErrors(element, text, window.grammarErrors);
          }
          
          return window.grammarErrors;
        } catch (error) {
          console.error('LanguageTool error:', error);
          return [];
        }
      };
      
      // Highlight errors in text
      function highlightErrors(element, text, errors) {
        // Clear previous highlights
        const existingSpans = element.querySelectorAll('.grammar-error, .grammar-error-severe');
        existingSpans.forEach(span => {
          const parent = span.parentNode;
          while (span.firstChild) {
            parent.insertBefore(span.firstChild, span);
          }
          parent.removeChild(span);
        });
        
        if (errors.length === 0 || !element.isContentEditable) return;
        
        // Sort errors by offset (reverse order for replacement)
        errors.sort((a, b) => b.offset - a.offset);
        
        // Create a working copy of the HTML
        let html = element.innerHTML;
        
        errors.forEach(error => {
          const errorText = text.substring(error.offset, error.offset + error.length);
          const severity = error.rule.category.id === 'TYPOS' ? 'severe' : '';
          
          // Create a unique marker for this error
          const marker = \`<span class="grammar-error \${severity ? 'grammar-error-severe' : ''}" 
            data-error-index="\${errors.indexOf(error)}"
            data-original="\${encodeURIComponent(errorText)}"
            title="\${error.message}">\${errorText}</span>\`;
          
          // Try to replace in HTML (simple approach - may need refinement)
          const beforeError = text.substring(0, error.offset);
          const afterError = text.substring(error.offset + error.length);
          
          // This is simplified - in production you'd need more sophisticated HTML manipulation
          // For now, we'll skip if the element has complex HTML
        });
      }
      
      // Monitor input fields
      let checkTimeout = null;
      let lastCheckedText = '';
      
      document.addEventListener('input', function(e) {
        const target = e.target;
        if (target && (target.contentEditable === 'true' || target.tagName === 'TEXTAREA')) {
          clearTimeout(checkTimeout);
          checkTimeout = setTimeout(function() {
            const text = target.innerText || target.value || '';
            if (text.length > 10 && text !== lastCheckedText) {
              lastCheckedText = text;
              window.currentErrorElement = target;
              window.checkGrammar(text, target);
            }
          }, 1500);
        }
      });
      
      // Handle right-click on errors
      document.addEventListener('contextmenu', function(e) {
        const errorSpan = e.target.closest('.grammar-error, .grammar-error-severe');
        if (errorSpan && window.grammarErrors.length > 0) {
          const errorIndex = parseInt(errorSpan.dataset.errorIndex);
          const error = window.grammarErrors[errorIndex];
          
          if (error && error.replacements && error.replacements.length > 0) {
            e.preventDefault();
            showGrammarPopup(e.pageX, e.pageY, error, errorSpan);
          }
        }
      });
      
      // Show grammar correction popup
      function showGrammarPopup(x, y, error, errorSpan) {
        // Remove any existing popup
        const existingPopup = document.getElementById('grammar-popup');
        if (existingPopup) {
          existingPopup.remove();
        }
        
        const popup = document.createElement('div');
        popup.id = 'grammar-popup';
        popup.className = 'grammar-popup';
        popup.style.left = x + 'px';
        popup.style.top = y + 'px';
        
        // Add error message
        const message = document.createElement('div');
        message.className = 'grammar-popup-message';
        message.textContent = error.message;
        popup.appendChild(message);
        
        // Add suggestions
        error.replacements.slice(0, 5).forEach(replacement => {
          const item = document.createElement('div');
          item.className = 'grammar-popup-item';
          item.textContent = replacement.value;
          item.onclick = function() {
            // Replace the error with the suggestion
            const original = decodeURIComponent(errorSpan.dataset.original);
            if (window.currentErrorElement) {
              const text = window.currentErrorElement.innerText || window.currentErrorElement.value;
              const newText = text.replace(original, replacement.value);
              
              if (window.currentErrorElement.contentEditable === 'true') {
                window.currentErrorElement.innerText = newText;
              } else {
                window.currentErrorElement.value = newText;
              }
              
              // Trigger input event to update the UI
              window.currentErrorElement.dispatchEvent(new Event('input', { bubbles: true }));
            }
            popup.remove();
          };
          popup.appendChild(item);
        });
        
        document.body.appendChild(popup);
        
        // Remove popup when clicking elsewhere
        setTimeout(() => {
          document.addEventListener('click', function removePopup() {
            popup.remove();
            document.removeEventListener('click', removePopup);
          }, { once: true });
        }, 100);
      }
      
      console.log('LanguageTool: Advanced integration ready!');
      return 'Success';
    })();
  `;
  
  mainWindow.webContents.executeJavaScript(advancedScript)
    .then(result => {
      console.log('LanguageTool advanced integration result:', result);
    })
    .catch(err => {
      console.error('Failed to inject LanguageTool:', err);
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
      label: 'Test Grammar Check',
      click: () => {
        console.log('Testing LanguageTool integration...');
        if (mainWindow && !mainWindow.isDestroyed()) {
          // Simple test to check if injection works
          mainWindow.webContents.executeJavaScript(`
            console.log('Grammar test triggered from tray menu');
            fetch('http://127.0.0.1:8081/v2/check', {
              method: 'POST',
              headers: {'Content-Type': 'application/x-www-form-urlencoded'},
              body: 'text=I has a apple&language=en-US'
            })
            .then(r => r.json())
            .then(data => {
              console.log('LanguageTool test successful!');
              console.log('Found', data.matches.length, 'issues');
              data.matches.forEach(m => console.log('-', m.message));
            })
            .catch(err => console.error('LanguageTool test failed:', err));
          `).catch(err => console.error('Script injection failed:', err));
        }
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

app.whenReady().then(async () => {
  // Setup context menu using dynamic import for ES module
  try {
    const contextMenuModule = await import('electron-context-menu');
    const contextMenu = contextMenuModule.default;
    
    // Store for grammar check results
    let lastGrammarCheck = null;
    
    contextMenu({
      showInspectElement: true,
      showCopyImage: true,
      showCopyImageAddress: true,
      showSaveImageAs: true,
      showSearchWithGoogle: true,
      showLearnSpelling: true,
      showLookUpSelection: true,
      showSelectAll: true,
      showCopyLink: true,
      prepend: (defaultActions, params, browserWindow) => {
        const items = [];
        
        // Add manual grammar check option for selected text
        if (params.selectionText && params.selectionText.trim().length > 0) {
          items.push({
            label: '📝 Check Grammar',
            click: async () => {
              try {
                console.log('Checking grammar for:', params.selectionText);
                const response = await fetch('http://127.0.0.1:8081/v2/check', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                  },
                  body: 'text=' + encodeURIComponent(params.selectionText) + '&language=en-US'
                });
            
                const data = await response.json();
                
                if (data.matches && data.matches.length > 0) {
                  // Build a menu with corrections
                  const { Menu, MenuItem, clipboard } = require('electron');
                  const correctionMenu = new Menu();
                  
                  // Add header
                  correctionMenu.append(new MenuItem({
                    label: `📝 Found ${data.matches.length} issue(s)`,
                    enabled: false
                  }));
                  
                  correctionMenu.append(new MenuItem({ type: 'separator' }));
                  
                  // Add each error and its corrections
                  data.matches.forEach((error, index) => {
                    const errorText = params.selectionText.substring(error.offset, error.offset + error.length);
                    
                    // Add error description
                    correctionMenu.append(new MenuItem({
                      label: `❌ "${errorText}": ${error.message.substring(0, 60)}...`,
                      enabled: false
                    }));
                    
                    // Add suggestions
                    if (error.replacements && error.replacements.length > 0) {
                      error.replacements.slice(0, 3).forEach(replacement => {
                        correctionMenu.append(new MenuItem({
                          label: `   ✓ Use "${replacement.value}"`,
                          click: () => {
                            // Directly replace the selected text
                            mainWindow.webContents.executeJavaScript(`
                              try {
                                // Get the current selection and active element
                                const selection = window.getSelection();
                                const activeElement = document.activeElement;
                                
                                if (selection.rangeCount > 0 && activeElement) {
                                  const range = selection.getRangeAt(0);
                                  const selectedText = range.toString();
                                  
                                  // Calculate the corrected text
                                  const originalText = "${params.selectionText.replace(/"/g, '\\"')}";
                                  const errorOffset = ${error.offset};
                                  const errorLength = ${error.length};
                                  const replacement = "${replacement.value.replace(/"/g, '\\"')}";
                                  
                                  const correctedText = originalText.substring(0, errorOffset) + 
                                                      replacement + 
                                                      originalText.substring(errorOffset + errorLength);
                                  
                                  // Replace the selected text with corrected version
                                  if (activeElement.contentEditable === 'true') {
                                    // For contenteditable elements
                                    range.deleteContents();
                                    const textNode = document.createTextNode(correctedText);
                                    range.insertNode(textNode);
                                    
                                    // Position cursor at the end
                                    range.setStartAfter(textNode);
                                    range.setEndAfter(textNode);
                                    selection.removeAllRanges();
                                    selection.addRange(range);
                                  } else if (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT') {
                                    // For input/textarea elements
                                    const start = activeElement.selectionStart;
                                    const end = activeElement.selectionEnd;
                                    const value = activeElement.value;
                                    
                                    activeElement.value = value.substring(0, start) + correctedText + value.substring(end);
                                    
                                    // Position cursor
                                    const newPosition = start + correctedText.length;
                                    activeElement.setSelectionRange(newPosition, newPosition);
                                  }
                                  
                                  // Trigger input events to notify the app
                                  activeElement.dispatchEvent(new Event('input', { bubbles: true }));
                                  activeElement.dispatchEvent(new Event('change', { bubbles: true }));
                                  
                                  // Show success notification
                                  const notification = document.createElement('div');
                                  notification.textContent = 'Text corrected!';
                                  notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #4CAF50; color: white; padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10000; font-family: sans-serif;';
                                  document.body.appendChild(notification);
                                  setTimeout(() => notification.remove(), 2000);
                                } else {
                                  throw new Error('No selection found');
                                }
                              } catch (err) {
                                console.log('Direct replacement failed, copying to clipboard instead');
                                // Fallback to clipboard
                                const correctedText = "${params.selectionText.substring(0, error.offset) + replacement.value + params.selectionText.substring(error.offset + error.length)}".replace(/\\"/g, '"');
                                navigator.clipboard.writeText(correctedText).then(() => {
                                  const notification = document.createElement('div');
                                  notification.textContent = 'Corrected text copied to clipboard!';
                                  notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #2196F3; color: white; padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10000; font-family: sans-serif;';
                                  document.body.appendChild(notification);
                                  setTimeout(() => notification.remove(), 3000);
                                });
                              }
                            `).catch(() => {
                              // Final fallback - main process clipboard
                              const correctedText = params.selectionText.substring(0, error.offset) + 
                                                  replacement.value + 
                                                  params.selectionText.substring(error.offset + error.length);
                              clipboard.writeText(correctedText);
                            });
                          }
                        }));
                      });
                    }
                    
                    if (index < data.matches.length - 1) {
                      correctionMenu.append(new MenuItem({ type: 'separator' }));
                    }
                  });
                  
                  // Add "fix all" option
                  correctionMenu.append(new MenuItem({ type: 'separator' }));
                  correctionMenu.append(new MenuItem({
                    label: '✨ Apply All Corrections',
                    click: () => {
                      // Calculate corrected text
                      let correctedText = params.selectionText;
                      const sortedMatches = [...data.matches].sort((a, b) => b.offset - a.offset);
                      sortedMatches.forEach(error => {
                        if (error.replacements && error.replacements.length > 0) {
                          correctedText = correctedText.substring(0, error.offset) + 
                                        error.replacements[0].value + 
                                        correctedText.substring(error.offset + error.length);
                        }
                      });
                      
                      // Directly replace the text
                      mainWindow.webContents.executeJavaScript(`
                        try {
                          const selection = window.getSelection();
                          const activeElement = document.activeElement;
                          const correctedText = "${correctedText.replace(/"/g, '\\"')}";
                          
                          if (selection.rangeCount > 0 && activeElement) {
                            const range = selection.getRangeAt(0);
                            
                            if (activeElement.contentEditable === 'true') {
                              range.deleteContents();
                              const textNode = document.createTextNode(correctedText);
                              range.insertNode(textNode);
                              
                              range.setStartAfter(textNode);
                              range.setEndAfter(textNode);
                              selection.removeAllRanges();
                              selection.addRange(range);
                            } else if (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT') {
                              const start = activeElement.selectionStart;
                              const end = activeElement.selectionEnd;
                              const value = activeElement.value;
                              
                              activeElement.value = value.substring(0, start) + correctedText + value.substring(end);
                              
                              const newPosition = start + correctedText.length;
                              activeElement.setSelectionRange(newPosition, newPosition);
                            }
                            
                            activeElement.dispatchEvent(new Event('input', { bubbles: true }));
                            activeElement.dispatchEvent(new Event('change', { bubbles: true }));
                            
                            const notification = document.createElement('div');
                            notification.textContent = 'All corrections applied!';
                            notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #4CAF50; color: white; padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10000; font-family: sans-serif;';
                            document.body.appendChild(notification);
                            setTimeout(() => notification.remove(), 2000);
                          } else {
                            throw new Error('No selection');
                          }
                        } catch (err) {
                          // Fallback to clipboard
                          navigator.clipboard.writeText("${correctedText.replace(/"/g, '\\"')}").then(() => {
                            const notification = document.createElement('div');
                            notification.textContent = 'All corrections copied to clipboard!';
                            notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #2196F3; color: white; padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10000; font-family: sans-serif;';
                            document.body.appendChild(notification);
                            setTimeout(() => notification.remove(), 3000);
                          });
                        }
                      `).catch(() => {
                        clipboard.writeText(correctedText);
                      });
                    }
                  }));
                  
                  // Show the menu
                  correctionMenu.popup();
                  
                } else {
                  // No errors found
                  mainWindow.webContents.executeJavaScript(`
                    const notification = document.createElement('div');
                    notification.textContent = 'No grammar issues found!';
                    notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #4CAF50; color: white; padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10000; font-family: sans-serif;';
                    document.body.appendChild(notification);
                    setTimeout(() => notification.remove(), 3000);
                  `).catch(() => {});
                }
              } catch (error) {
                console.error('Grammar check failed:', error);
                mainWindow.webContents.executeJavaScript(`
                  const notification = document.createElement('div');
                  notification.textContent = 'Grammar check failed: ${error.message}';
                  notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #f44336; color: white; padding: 12px 20px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); z-index: 10000; font-family: sans-serif;';
                  document.body.appendChild(notification);
                  setTimeout(() => notification.remove(), 4000);
                `).catch(() => {});
              }
            }
          });
          items.push({ type: 'separator' });
        }
        
        // Add link option (only if external link)
        if (params.linkURL && params.linkURL.length > 0 && !params.linkURL.includes('flock.com')) {
          items.push({
            label: 'Open Link in Browser',
            click: () => {
              shell.openExternal(params.linkURL);
            }
          });
          items.push({ type: 'separator' });
        }
        
        return items;
      }
    });
  } catch (error) {
    console.error('Failed to load context menu:', error);
  }

  // Set app name
  app.setName('Flock Chat');

  // Session configuration for better compatibility
  const ses = session.defaultSession;
  
  // Enable spellcheck with language detection
  ses.setSpellCheckerLanguages(['en-US']);
  ses.setSpellCheckerEnabled(true);
  
  // Load Chrome extensions (if you want to add any)
  // Example: To load an unpacked extension from a directory:
  // ses.loadExtension('/path/to/unpacked/extension').then((extension) => {
  //   console.log('Extension loaded:', extension.name);
  // }).catch((err) => {
  //   console.error('Failed to load extension:', err);
  // });
  
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
  
  // Start LanguageTool server
  startLanguageTool();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  // Kill LanguageTool server when app quits
  if (languageToolProcess) {
    console.log('Stopping LanguageTool server...');
    languageToolProcess.kill();
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