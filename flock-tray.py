#!/usr/bin/env python3
import sys
import gi
import threading
import time
import re
import os
import tempfile
import hashlib

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, WebKit2, GLib, AppIndicator3, Notify

try:
    from gi.repository import GdkPixbuf, Pango, PangoCairo
    import cairo
except ImportError:
    print("Warning: Could not import cairo/pango for avatar generation")
    cairo = None

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
    
    def generate_letter_avatar(self, name, size=48):
        """Generate a letter avatar image for the given name"""
        if not cairo:
            return None
            
        # Get first letter and color
        letter = name[0].upper() if name else "?"
        
        # Generate a color based on the name (consistent color for same name)
        colors = [
            (0.91, 0.30, 0.24),  # Red
            (0.90, 0.49, 0.13),  # Orange
            (0.95, 0.77, 0.06),  # Yellow
            (0.54, 0.76, 0.29),  # Green
            (0.12, 0.53, 0.90),  # Blue
            (0.41, 0.30, 0.65),  # Purple
            (0.90, 0.30, 0.55),  # Pink
        ]
        color_index = ord(letter) % len(colors)
        bg_color = colors[color_index]
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Create cairo surface and context
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
            ctx = cairo.Context(surface)
            
            # Draw circular background
            ctx.arc(size/2, size/2, size/2, 0, 2 * 3.14159)
            ctx.set_source_rgb(*bg_color)
            ctx.fill()
            
            # Draw letter
            ctx.set_source_rgb(1, 1, 1)  # White text
            ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            ctx.set_font_size(size * 0.5)
            
            # Center the text
            text_extents = ctx.text_extents(letter)
            x = (size - text_extents.width) / 2 - text_extents.x_bearing
            y = (size - text_extents.height) / 2 - text_extents.y_bearing
            
            ctx.move_to(x, y)
            ctx.show_text(letter)
            
            # Save to file
            surface.write_to_png(temp_path)
            
            return temp_path
        except Exception as e:
            print(f"Error generating avatar: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return None
    
    def on_show_notification(self, webview, notification):
        # Handle WebKit notification and show it via libnotify
        title = notification.get_title()
        body = notification.get_body()
        
        # Generate a letter avatar based on the sender's name
        avatar_path = self.generate_letter_avatar(title)
        
        # Use generated avatar or fall back to default icon
        if avatar_path:
            icon_path = avatar_path
            # Clean up temp file after notification
            GLib.timeout_add_seconds(10, lambda: os.unlink(avatar_path) if os.path.exists(avatar_path) else None)
        else:
            icon_path = "/home/pranav/.config/flock-native/icon.png"
        
        # Show the notification
        notify = Notify.Notification.new(title, body, icon_path)
        notify.set_urgency(Notify.Urgency.CRITICAL)  # High urgency - requires manual dismissal
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
            has_unread = js_result if isinstance(js_result, bool) else False
            
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