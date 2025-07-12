#!/usr/bin/env python3
import sys
import gi
import threading
import time
import re

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, WebKit2, GLib, AppIndicator3

class FlockTrayWindow:
    def __init__(self):
        self.window = Gtk.Window()
        self.window.set_title("Flock")
        self.window.set_default_size(1200, 800)
        self.window.set_icon_from_file("/home/pranav/.config/flock-native/icon.png")
        
        # Track window visibility
        self.is_visible = True
        
        # Create WebView
        self.webview = WebKit2.WebView()
        settings = self.webview.get_settings()
        settings.set_enable_developer_extras(True)
        settings.set_enable_javascript(True)
        settings.set_javascript_can_open_windows_automatically(True)
        
        # Load Flock
        self.webview.load_uri("https://web.flock.com")
        
        # Add webview to window
        self.window.add(self.webview)
        
        # Create system tray
        self.indicator = AppIndicator3.Indicator.new(
            "flock-native",
            "/home/pranav/.config/flock-native/tray-icon-mono.png",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        
        # Create tray menu
        self.create_menu()
        
        # Handle window delete event (close button)
        self.window.connect("delete-event", self.on_window_delete)
        
        # Start monitoring for unread messages
        self.start_unread_monitor()
        
        # Show window
        self.window.show_all()
    
    def create_menu(self):
        menu = Gtk.Menu()
        
        # Show/Hide item
        self.show_hide_item = Gtk.MenuItem(label="Hide")
        self.show_hide_item.connect("activate", self.toggle_window)
        menu.append(self.show_hide_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quit item
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.quit_app)
        menu.append(quit_item)
        
        menu.show_all()
        self.indicator.set_menu(menu)
    
    def toggle_window(self, widget=None):
        if self.is_visible:
            self.window.hide()
            self.is_visible = False
            self.show_hide_item.set_label("Show")
        else:
            self.window.show()
            self.window.present()
            self.is_visible = True
            self.show_hide_item.set_label("Hide")
    
    def on_window_delete(self, widget, event):
        # Hide window instead of closing
        self.toggle_window()
        return True  # Prevent default close
    
    def quit_app(self, widget):
        Gtk.main_quit()
        sys.exit(0)
    
    def start_unread_monitor(self):
        # Run monitor in a separate thread
        monitor_thread = threading.Thread(target=self.monitor_unread_messages, daemon=True)
        monitor_thread.start()
    
    def monitor_unread_messages(self):
        time.sleep(5)  # Wait for page to load initially
        
        while True:
            try:
                # Execute JavaScript to check for unread messages
                self.webview.run_javascript("""
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
                """, None, self.on_unread_check_finished, None)
            except:
                pass  # Page might be loading
            
            time.sleep(2)  # Check every 2 seconds
    
    def on_unread_check_finished(self, webview, result, user_data):
        try:
            js_result = webview.run_javascript_finish(result)
            value = js_result.get_js_value()
            has_unread = value.to_boolean()
            
            # Update tray icon on main thread
            GLib.idle_add(self.update_tray_icon, has_unread)
        except:
            pass
    
    def update_tray_icon(self, has_unread):
        if has_unread:
            self.indicator.set_icon("/home/pranav/.config/flock-native/tray-icon-green.png")
        else:
            self.indicator.set_icon("/home/pranav/.config/flock-native/tray-icon-mono.png")
        return False

if __name__ == "__main__":
    app = FlockTrayWindow()
    Gtk.main()