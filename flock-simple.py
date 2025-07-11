#!/usr/bin/env python3

import sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
from gi.repository import Gtk, WebKit2, GLib

class FlockWindow:
    def __init__(self):
        self.window = Gtk.Window()
        self.window.set_title("Flock Chat")
        self.window.set_default_size(1200, 800)
        self.window.connect("destroy", Gtk.main_quit)

        # Create WebView
        self.webview = WebKit2.WebView()
        
        # Configure settings for better compatibility
        settings = self.webview.get_settings()
        settings.set_enable_javascript(True)
        settings.set_enable_media_stream(True)
        settings.set_enable_webgl(True)
        settings.set_user_agent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Handle permission requests (for notifications)
        self.webview.connect("permission-request", self.on_permission_request)
        
        # Load Flock
        self.webview.load_uri("https://web.flock.com")
        
        # Add to window
        self.window.add(self.webview)
        self.window.show_all()

    def on_permission_request(self, webview, request):
        if isinstance(request, WebKit2.NotificationPermissionRequest):
            request.allow()
            return True
        return False

if __name__ == "__main__":
    app = FlockWindow()
    Gtk.main()