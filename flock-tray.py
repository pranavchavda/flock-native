#!/usr/bin/env python3
import sys
import gi
import threading
import time
import re
import os
import tempfile
import urllib.request

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, WebKit2, GLib, AppIndicator3, Notify

class FlockTrayWindow:
    def __init__(self):
        # Initialize notifications
        Notify.init("Flock Native")
        
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
        
        # Set up WebKit context for notifications
        context = self.webview.get_context()
        context.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
        
        # Initialize notification permission
        context.initialize_notification_permissions([
            WebKit2.SecurityOrigin.new_for_uri("https://web.flock.com"),
            WebKit2.SecurityOrigin.new_for_uri("https://flock.com")
        ], [])
        
        # Handle permission requests (for notifications)
        self.webview.connect("permission-request", self.on_permission_request)
        
        # Handle show-notification signal
        self.webview.connect("show-notification", self.on_show_notification)
        
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
    
    def on_permission_request(self, webview, request):
        # Allow notification permissions
        if isinstance(request, WebKit2.NotificationPermissionRequest):
            print("Notification permission requested - allowing")
            request.allow()
            return True
        return False
    
    def on_show_notification(self, webview, notification):
        # Handle WebKit notification and show it via libnotify
        title = notification.get_title()
        body = notification.get_body()
        
        print(f"Showing notification: {title} - {body}")
        
        # Try to get the icon URL from the notification
        icon_path = "/home/pranav/.config/flock-native/icon.png"  # Default icon
        
        # WebKit2 notifications may have an icon URL
        try:
            # Try to get icon URL from notification tag or other properties
            # Since WebKit2 doesn't expose icon directly, we'll extract it from the page
            js_code = """
            (function() {
                // Look for recent notification with matching text
                const notifications = document.querySelectorAll('.notification-avatar img, .message-avatar img, [class*="avatar"] img');
                for (let img of notifications) {
                    const parent = img.closest('.message, .notification, [class*="message"]');
                    if (parent && parent.textContent.includes('%s')) {
                        return img.src;
                    }
                }
                // Fallback: get the most recent avatar
                const recentAvatar = document.querySelector('.message:last-child img[src*="avatar"], .chat-message:last-child img');
                return recentAvatar ? recentAvatar.src : null;
            })();
            """ % (body[:30].replace("'", "\\'").replace('"', '\\"'))
            
            self.webview.evaluate_javascript(js_code, -1, None, None, self._on_avatar_url_ready, (notification, title, body))
            return True
        except Exception as e:
            print(f"Error getting avatar: {e}")
        
        # Fallback: show notification without avatar
        self._show_notification_with_icon(title, body, icon_path)
        notification.close()
        return True
    
    def _on_avatar_url_ready(self, webview, result, user_data):
        notification, title, body = user_data
        try:
            js_result = webview.evaluate_javascript_finish(result)
            avatar_url = js_result.to_string() if js_result else None
            
            if avatar_url and avatar_url != 'null':
                # Download avatar to temp file
                self._download_and_show_notification(title, body, avatar_url)
            else:
                self._show_notification_with_icon(title, body, "/home/pranav/.config/flock-native/icon.png")
        except Exception as e:
            print(f"Error processing avatar: {e}")
            self._show_notification_with_icon(title, body, "/home/pranav/.config/flock-native/icon.png")
        
        notification.close()
    
    def _download_and_show_notification(self, title, body, avatar_url):
        try:
            # Create temp file for avatar
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                # Download avatar
                with urllib.request.urlopen(avatar_url, timeout=2) as response:
                    tmp_file.write(response.read())
                tmp_path = tmp_file.name
            
            # Show notification with avatar
            self._show_notification_with_icon(title, body, tmp_path)
            
            # Clean up temp file after a delay
            GLib.timeout_add_seconds(10, lambda: os.unlink(tmp_path) if os.path.exists(tmp_path) else None)
        except Exception as e:
            print(f"Error downloading avatar: {e}")
            self._show_notification_with_icon(title, body, "/home/pranav/.config/flock-native/icon.png")
    
    def _show_notification_with_icon(self, title, body, icon_path):
        notify = Notify.Notification.new(title, body, icon_path)
        notify.set_urgency(Notify.Urgency.NORMAL)
        notify.show()
    
    def quit_app(self, widget):
        Notify.uninit()
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
                self.webview.evaluate_javascript("""
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
                """, -1, None, None, self.on_unread_check_finished, None)
            except:
                pass  # Page might be loading
            
            time.sleep(2)  # Check every 2 seconds
    
    def on_unread_check_finished(self, webview, result, user_data):
        try:
            js_result = webview.evaluate_javascript_finish(result)
            has_unread = js_result.to_boolean()
            
            # Update tray icon on main thread
            GLib.idle_add(self.update_tray_icon, has_unread)
        except:
            pass
    
    def update_tray_icon(self, has_unread):
        if has_unread:
            self.indicator.set_icon_full("/home/pranav/.config/flock-native/tray-icon-green.png", "Unread messages")
        else:
            self.indicator.set_icon_full("/home/pranav/.config/flock-native/tray-icon-mono.png", "No unread messages")
        return False

if __name__ == "__main__":
    app = FlockTrayWindow()
    Gtk.main()