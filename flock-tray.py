#!/usr/bin/env python3
import sys
import gi
import threading
import time
import re

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
        
        # Debug: Let's see what methods/properties are available on the notification object
        print("Notification object type:", type(notification))
        print("Notification methods/properties:", [attr for attr in dir(notification) if not attr.startswith('_')])
        
        # Try to get more data
        try:
            # Check for tag (might contain user ID or other info)
            if hasattr(notification, 'get_tag'):
                tag = notification.get_tag()
                print(f"Notification tag: {tag}")
            
            # Check for icon URL
            if hasattr(notification, 'get_icon'):
                icon = notification.get_icon()
                print(f"Notification icon: {icon}")
            
            # Check for any other properties
            if hasattr(notification, 'get_lang'):
                lang = notification.get_lang()
                print(f"Notification lang: {lang}")
                
            if hasattr(notification, 'get_id'):
                notif_id = notification.get_id()
                print(f"Notification ID: {notif_id}")
        except Exception as e:
            print(f"Error exploring notification: {e}")
        
        # For now, just use the default icon
        # WebKit2 Python bindings have issues with getting icon data from notifications
        icon_path = "/home/pranav/.config/flock-native/icon.png"
        
        # Show the notification
        notify = Notify.Notification.new(title, body, icon_path)
        notify.set_urgency(Notify.Urgency.NORMAL)
        notify.show()
        
        # Close the WebKit notification (we're handling it ourselves)
        notification.close()
        return True
    
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
                """, -1, None, self.on_unread_check_finished, None)
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