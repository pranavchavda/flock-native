#!/usr/bin/env python3
import sys
import gi
import threading
import time
import re
import os
import tempfile
import hashlib
import webbrowser
import subprocess

gi.require_version('Gtk', '3.0')
gi.require_version('WebKit2', '4.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
gi.require_version('PangoCairo', '1.0')
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
        settings.set_allow_file_access_from_file_urls(True)
        
        # Enable audio/video
        settings.set_media_playback_requires_user_gesture(False)
        settings.set_enable_media(True)
        settings.set_enable_webaudio(True)
        
        # Enable downloads
        settings.set_enable_write_console_messages_to_stdout(True)
        
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
        
        # Handle navigation decisions (for external links)
        self.webview.connect("decide-policy", self.on_navigation_decision)
        
        # Handle download requests
        context.connect("download-started", self.on_download_started)
        
        # Enable context menu for debugging
        self.webview.connect("context-menu", self.on_context_menu)
        
        # Handle new window requests
        self.webview.connect("create", self.on_create_window)
        
        # Inject JavaScript to handle downloads
        self.webview.connect("load-changed", self.on_load_changed)
        
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
            request.allow()
            return True
        return False
    
    def on_navigation_decision(self, webview, decision, decision_type):
        print(f"Decision type: {decision_type}")
        
        if decision_type == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            navigation_action = decision.get_navigation_action()
            request = navigation_action.get_request()
            uri = request.get_uri()
            
            # Get the navigation type
            nav_type = navigation_action.get_navigation_type()
            
            # Debug print
            print(f"Navigation action - URI: {uri}, Type: {nav_type}")
            
            # Check for download links by looking at the URI
            if uri and any(pattern in uri.lower() for pattern in ['/download/', 'download=', 'export=', '.pdf', '.zip', '.doc', '.xls']):
                print(f"Detected download link: {uri}")
                decision.download()
                return True
            
            # Handle different types of navigation
            if nav_type in [WebKit2.NavigationType.LINK_CLICKED, 
                           WebKit2.NavigationType.FORM_SUBMITTED,
                           WebKit2.NavigationType.OTHER]:
                # Check if this is an external link (not flock.com)
                if uri and not any(domain in uri for domain in ['flock.com', 'web.flock.com', 'flockws.com', 'about:blank']):
                    print(f"Opening external link: {uri}")
                    # Use subprocess to ensure proper handling
                    try:
                        subprocess.run(['xdg-open', uri], check=True)
                    except subprocess.CalledProcessError:
                        # Fallback to webbrowser
                        webbrowser.open(uri)
                    decision.ignore()
                    return True
        
        elif decision_type == WebKit2.PolicyDecisionType.RESPONSE:
            # Handle downloads based on response
            response = decision.get_response()
            mime_type = response.get_mime_type()
            uri = response.get_uri()
            
            print(f"Response decision - URI: {uri}, MIME: {mime_type}")
            
            # Check Content-Disposition header - fix deprecation warning
            headers = response.get_http_headers()
            if headers:
                # Use iterate() method instead of deprecated get()
                iter = headers.iter()
                while iter:
                    name, value = iter.next()
                    if name and name.lower() == "content-disposition" and value and "attachment" in value:
                        print(f"Attachment detected: {uri}")
                        decision.download()
                        return True
                    if not iter:
                        break
            
            # Check if this is a downloadable file by MIME type
            downloadable_mimes = [
                'application/pdf', 'application/zip', 'application/octet-stream',
                'application/msword', 'application/vnd.ms-excel', 'image/', 'video/', 'audio/'
            ]
            if mime_type and any(mime in mime_type for mime in downloadable_mimes):
                print(f"Downloadable MIME type: {mime_type}")
                decision.download()
                return True
        
        # Let WebKit handle by default
        return False
    
    def on_context_menu(self, webview, context_menu, event, hit_test_result):
        # Debug what was right-clicked
        if hit_test_result.context_is_image():
            print("Right-clicked on image")
        if hit_test_result.context_is_link():
            print(f"Right-clicked on link: {hit_test_result.get_link_uri()}")
        
        # Let the default context menu appear
        return False
    
    def on_create_window(self, webview, navigation_action):
        # Handle requests to open new windows (target="_blank" links)
        request = navigation_action.get_request()
        uri = request.get_uri()
        
        print(f"New window requested for: {uri}")
        
        if uri:
            # Open in default browser
            try:
                subprocess.run(['xdg-open', uri], check=True)
            except subprocess.CalledProcessError:
                webbrowser.open(uri)
        
        # Return None to prevent new window creation
        return None
    
    def on_load_changed(self, webview, load_event):
        if load_event == WebKit2.LoadEvent.FINISHED:
            # Inject JavaScript to intercept all links
            script = """
            (function() {
                // Log all link clicks for debugging
                document.addEventListener('click', function(e) {
                    let target = e.target;
                    while (target && target.tagName !== 'A') {
                        target = target.parentElement;
                    }
                    
                    if (target && target.href) {
                        console.log('Link clicked:', target.href);
                        console.log('Link target:', target.target);
                        console.log('Link host:', new URL(target.href).hostname);
                        
                        // Check if it's an external link
                        const url = new URL(target.href);
                        const currentHost = window.location.hostname;
                        if (url.hostname !== currentHost && 
                            !url.hostname.includes('flock.com') &&
                            !url.hostname.includes('flockws.com')) {
                            console.log('External link detected, opening in browser');
                            e.preventDefault();
                            // Create a temporary link with target="_blank" to trigger navigation
                            const tempLink = document.createElement('a');
                            tempLink.href = target.href;
                            tempLink.target = '_blank';
                            tempLink.click();
                            return false;
                        }
                        
                        // Check if it's a download link
                        if (target.hasAttribute('download') || 
                            target.href.includes('/download/') ||
                            target.href.includes('download=') ||
                            target.href.match(/\.(pdf|zip|doc|docx|xls|xlsx|ppt|pptx|rar|7z|tar|gz)$/i)) {
                            
                            console.log('Download link clicked:', target.href);
                            // Force navigation to trigger our handler
                            e.preventDefault();
                            window.location.href = target.href;
                        }
                    }
                }, true);
                
                console.log('Link interceptor installed');
            })();
            """
            # Use the new evaluate_javascript method to avoid deprecation
            self.webview.evaluate_javascript(script, -1, None, None, None, None)
            
            # Initialize audio context to ensure notification sounds work
            audio_init_script = """
            (function() {
                // Create and resume audio context to enable sounds
                if (window.AudioContext || window.webkitAudioContext) {
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    const audioContext = new AudioContext();
                    
                    // Resume audio context (required by some browsers)
                    if (audioContext.state === 'suspended') {
                        audioContext.resume().then(() => {
                            console.log('Audio context resumed');
                        });
                    }
                    
                    // Try to find and initialize Flock's notification sound
                    setTimeout(() => {
                        // Look for audio elements or Flock's sound initialization
                        const audioElements = document.querySelectorAll('audio');
                        audioElements.forEach(audio => {
                            audio.load();
                            console.log('Preloaded audio element:', audio.src);
                        });
                    }, 2000);
                }
                
                console.log('Audio initialization complete');
            })();
            """
            self.webview.evaluate_javascript(audio_init_script, -1, None, None, None, None)
    
    def on_download_started(self, context, download):
        # Get the download details
        uri = download.get_request().get_uri()
        
        # Get suggested filename - method name is different in WebKit2
        response = download.get_response()
        suggested_filename = response.get_suggested_filename() if response else None
        
        # If no suggested filename, extract from URI
        if not suggested_filename:
            from urllib.parse import urlparse, unquote
            path = urlparse(uri).path
            suggested_filename = unquote(os.path.basename(path)) or "download"
        
        print(f"Download started for URI: {uri}")
        print(f"Suggested filename: {suggested_filename}")
        
        # Set download destination
        downloads_dir = os.path.expanduser("~/Downloads")
        if not os.path.exists(downloads_dir):
            downloads_dir = os.path.expanduser("~")
        
        destination = os.path.join(downloads_dir, suggested_filename)
        
        # Handle file conflicts
        base, ext = os.path.splitext(destination)
        counter = 1
        while os.path.exists(destination):
            destination = f"{base} ({counter}){ext}"
            counter += 1
        
        print(f"Saving to: {destination}")
        download.set_destination(f"file://{destination}")
        
        # Connect to download progress signals
        download.connect("finished", self.on_download_finished, destination)
        download.connect("failed", self.on_download_failed)
        
        return False  # Let WebKit handle the download
    
    def on_download_finished(self, download, destination):
        print(f"Download completed: {destination}")
        # Show notification
        notify = Notify.Notification.new(
            "Download Complete",
            f"File saved to: {os.path.basename(destination)}",
            "/home/pranav/.config/flock-native/icon.png"
        )
        notify.show()
        
        # Open the downloads folder
        try:
            subprocess.run(['xdg-open', os.path.dirname(destination)], check=False)
        except:
            pass
    
    def on_download_failed(self, download, error):
        print(f"Download failed: {error}")
        notify = Notify.Notification.new(
            "Download Failed",
            "The download could not be completed",
            "/home/pranav/.config/flock-native/icon.png"
        )
        notify.show()
    
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
        notify.set_urgency(Notify.Urgency.NORMAL)
        notify.set_timeout(Notify.EXPIRES_NEVER)  # Stay until dismissed without being red
        notify.show()
        
        # Play Flock notification sound
        sound_file = "/home/pranav/.config/flock-native/notification-sound/onmessage.wav"
        if os.path.exists(sound_file):
            try:
                # Use paplay (PulseAudio) to play the sound
                subprocess.Popen(['paplay', sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                try:
                    # Fallback to aplay if paplay is not available
                    subprocess.Popen(['aplay', '-q', sound_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except:
                    pass
        
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
                """, -1, None, self.on_unread_check_finished, None, None)
            except:
                pass  # Page might be loading
            
            time.sleep(2)  # Check every 2 seconds
    
    def on_unread_check_finished(self, webview, result, user_data):
        try:
            # Use the new method for WebKit2 4.0
            value = webview.evaluate_javascript_finish(result)
            has_unread = value.to_boolean() if value else False
            
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