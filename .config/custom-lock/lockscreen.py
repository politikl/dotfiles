#!/usr/bin/env python3
"""
Custom Lock Screen for Hyprland
"""

import gi
import subprocess
import os
import datetime

gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')

from gi.repository import Gtk, Gdk, GLib, GdkPixbuf
from gi.repository import Gtk4LayerShell as LayerShell

# Catppuccin Mocha colors
COLORS = {
    'bg': 'rgba(17, 17, 27, 0.8)',
    'fg': '#cdd6f4',
    'fg_dim': '#6c7086',
    'accent': '#89b4fa',
    'green': '#a6e3a1',
    'red': '#f38ba8',
    'surface': 'rgba(30, 30, 46, 0.95)',
    'outer': 'rgba(137, 180, 250, 0.5)',
}

class LockScreen(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.custom.lockscreen')
        # Ensure keybinds are disabled immediately
        subprocess.run(['hyprctl', 'dispatch', 'submap', 'lockscreen'], capture_output=True)
        self.password = ""
        self.is_typing = False
        self.quote = self.get_quote()
        self.windows = []
        self.stacks = []
        self.date_labels = []
        self.battery_labels = []
        self.hour_labels_idle = []
        self.minute_labels_idle = []
        self.hour_labels_typing = []
        self.minute_labels_typing = []
        self.password_labels = []
        self.error_labels = []
        self.wallpaper_path = os.path.expanduser("~/.config/hypr/wallpaper_effects/.wallpaper_current")

    def get_quote(self):
        quote_script = os.path.expanduser("~/.config/hypr/scripts/RandomQuote.sh")
        try:
            if os.path.exists(quote_script):
                result = subprocess.run(['bash', quote_script], capture_output=True, text=True, timeout=2)
                return result.stdout.strip() or "The supreme art of war is to subdue the enemy without fighting."
        except:
            pass
        return "The supreme art of war is to subdue the enemy without fighting."

    def get_battery(self):
        try:
            with open('/sys/class/power_supply/macsmc-battery/capacity', 'r') as f:
                capacity = int(f.read().strip())
                # Icons matching waybar config
                icons = ["󰂎", "󰁺", "󰁻", "󰁼", "󰁽", "󰁾", "󰁿", "󰂀", "󰂁", "󰂂", "󰁹"]
                icon_idx = min(capacity // 10, 10)
                return f"{icons[icon_idx]} {capacity}%"
        except:
            return "󰁹 --"

    def get_date(self):
        return datetime.datetime.now().strftime("%I:%M %p")

    def get_time(self):
        now = datetime.datetime.now()
        return now.strftime("%H"), now.strftime("%M")

    def create_blurred_wallpaper(self):
        """Create a blurred version of the wallpaper (cached)"""
        try:
            blurred_path = "/tmp/lockscreen_blurred.png"
            if os.path.exists(self.wallpaper_path):
                # Check if we need to regenerate (wallpaper changed)
                wall_mtime = os.path.getmtime(self.wallpaper_path)
                if os.path.exists(blurred_path):
                    blur_mtime = os.path.getmtime(blurred_path)
                    if blur_mtime > wall_mtime:
                        return blurred_path  # Use cached version

                # Generate with light blur
                subprocess.run([
                    'magick', self.wallpaper_path,
                    '-resize', '1920x1080>',
                    '-blur', '0x3',
                    '-brightness-contrast', '-15x0',
                    blurred_path
                ], capture_output=True, timeout=10)
                if os.path.exists(blurred_path):
                    return blurred_path
        except:
            pass
        return None

    def do_activate(self):
        # Create blurred wallpaper
        self.blurred_wallpaper = self.create_blurred_wallpaper()

        display = Gdk.Display.get_default()
        monitors = display.get_monitors()

        for i in range(monitors.get_n_items()):
            monitor = monitors.get_item(i)
            win = self.create_lock_window(monitor)
            self.windows.append(win)
            win.present()

        self.apply_css()
        self.update_time()
        GLib.timeout_add_seconds(1, self.update_time)

    def create_lock_window(self, monitor):
        win = Gtk.ApplicationWindow(application=self)

        LayerShell.init_for_window(win)
        LayerShell.set_layer(win, LayerShell.Layer.OVERLAY)
        LayerShell.set_monitor(win, monitor)
        LayerShell.set_exclusive_zone(win, -1)
        LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.EXCLUSIVE)
        LayerShell.set_namespace(win, "lockscreen")

        LayerShell.set_anchor(win, LayerShell.Edge.TOP, True)
        LayerShell.set_anchor(win, LayerShell.Edge.BOTTOM, True)
        LayerShell.set_anchor(win, LayerShell.Edge.LEFT, True)
        LayerShell.set_anchor(win, LayerShell.Edge.RIGHT, True)

        # Main overlay to stack background and content
        overlay = Gtk.Overlay()
        overlay.set_vexpand(True)
        overlay.set_hexpand(True)

        # Background with blurred wallpaper
        if self.blurred_wallpaper and os.path.exists(self.blurred_wallpaper):
            bg_picture = Gtk.Picture.new_for_filename(self.blurred_wallpaper)
            bg_picture.set_content_fit(Gtk.ContentFit.COVER)
            bg_picture.set_can_shrink(True)
            overlay.set_child(bg_picture)
        else:
            # Fallback solid background
            bg_box = Gtk.Box()
            bg_box.add_css_class('fallback-bg')
            overlay.set_child(bg_box)

        # Dark overlay for better readability
        dark_overlay = Gtk.Box()
        dark_overlay.add_css_class('dark-overlay')
        dark_overlay.set_vexpand(True)
        dark_overlay.set_hexpand(True)
        overlay.add_overlay(dark_overlay)

        # Content
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        main_box.set_valign(Gtk.Align.FILL)
        main_box.set_halign(Gtk.Align.FILL)
        main_box.set_vexpand(True)
        main_box.set_hexpand(True)

        idle_view = self.create_idle_view()
        typing_view = self.create_typing_view()

        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        stack.set_transition_duration(200)
        stack.add_named(idle_view, "idle")
        stack.add_named(typing_view, "typing")
        stack.set_visible_child_name("idle")
        self.stacks.append(stack)

        main_box.append(stack)
        overlay.add_overlay(main_box)

        win.set_child(overlay)

        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self.on_key_press)
        win.add_controller(key_controller)

        return win

    def create_top_bar(self):
        """Create top bar with time, quote, battery all on same line"""
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        top_bar.set_halign(Gtk.Align.FILL)
        top_bar.set_hexpand(True)
        top_bar.set_margin_top(40)
        top_bar.set_margin_start(50)
        top_bar.set_margin_end(50)

        # Time (left)
        date_label = Gtk.Label(label=self.get_date())
        date_label.add_css_class('top-text')
        date_label.set_halign(Gtk.Align.START)
        self.date_labels.append(date_label)
        top_bar.append(date_label)

        # Quote (center) - takes remaining space
        quote_label = Gtk.Label(label=f'"{self.quote}" — Sun Tzu')
        quote_label.add_css_class('top-text')
        quote_label.add_css_class('quote')
        quote_label.set_halign(Gtk.Align.CENTER)
        quote_label.set_hexpand(True)
        quote_label.set_ellipsize(3)
        top_bar.append(quote_label)

        # Battery (right)
        battery_label = Gtk.Label(label=self.get_battery())
        battery_label.add_css_class('top-text')
        battery_label.add_css_class('battery')
        battery_label.set_halign(Gtk.Align.END)
        self.battery_labels.append(battery_label)
        top_bar.append(battery_label)

        return top_bar

    def create_idle_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_valign(Gtk.Align.FILL)
        box.set_halign(Gtk.Align.FILL)
        box.set_vexpand(True)
        box.set_hexpand(True)

        # Top section
        box.append(self.create_top_bar())

        # Spacer
        spacer1 = Gtk.Box()
        spacer1.set_vexpand(True)
        box.append(spacer1)

        # Clock
        clock_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        clock_box.set_halign(Gtk.Align.CENTER)
        clock_box.set_valign(Gtk.Align.CENTER)

        hour, minute = self.get_time()

        hour_label = Gtk.Label(label=hour)
        hour_label.add_css_class('time-large')
        self.hour_labels_idle.append(hour_label)

        minute_label = Gtk.Label(label=minute)
        minute_label.add_css_class('time-large')
        self.minute_labels_idle.append(minute_label)

        clock_box.append(hour_label)
        clock_box.append(minute_label)
        box.append(clock_box)

        # Spacer
        spacer2 = Gtk.Box()
        spacer2.set_vexpand(True)
        box.append(spacer2)

        return box

    def create_typing_view(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_valign(Gtk.Align.FILL)
        box.set_halign(Gtk.Align.FILL)
        box.set_vexpand(True)
        box.set_hexpand(True)

        # Top section
        box.append(self.create_top_bar())

        # Spacer
        spacer1 = Gtk.Box()
        spacer1.set_vexpand(True)
        box.append(spacer1)

        # Split time with password
        center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        center_box.set_halign(Gtk.Align.CENTER)
        center_box.set_valign(Gtk.Align.CENTER)
        center_box.set_spacing(15)

        hour, minute = self.get_time()

        # Hour
        hour_label = Gtk.Label(label=hour)
        hour_label.add_css_class('time-large')
        self.hour_labels_typing.append(hour_label)
        center_box.append(hour_label)

        # Password field
        password_frame = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        password_frame.add_css_class('password-frame')
        password_frame.set_halign(Gtk.Align.CENTER)
        password_frame.set_valign(Gtk.Align.CENTER)

        password_label = Gtk.Label()
        password_label.add_css_class('password-dots')
        password_label.set_halign(Gtk.Align.CENTER)
        password_label.set_valign(Gtk.Align.CENTER)
        self.password_labels.append(password_label)

        password_frame.append(password_label)
        center_box.append(password_frame)

        # Error label
        error_label = Gtk.Label()
        error_label.add_css_class('error')
        self.error_labels.append(error_label)
        center_box.append(error_label)

        # Minutes
        minute_label = Gtk.Label(label=minute)
        minute_label.add_css_class('time-large')
        self.minute_labels_typing.append(minute_label)
        center_box.append(minute_label)

        box.append(center_box)

        # Spacer
        spacer2 = Gtk.Box()
        spacer2.set_vexpand(True)
        box.append(spacer2)

        return box

    def apply_css(self):
        css = f"""
        .fallback-bg {{
            background-color: rgb(17, 17, 27);
        }}

        .dark-overlay {{
            background-color: rgba(0, 0, 0, 0.4);
        }}

        .top-text {{
            font-family: "JetBrainsMono Nerd Font";
            font-size: 24px;
            font-weight: 500;
            color: {COLORS['fg']};
        }}

        .quote {{
            font-style: italic;
            color: {COLORS['accent']};
        }}

        .battery {{
            color: {COLORS['green']};
        }}

        .time-large {{
            font-family: "JetBrainsMono Nerd Font Mono";
            font-size: 200px;
            font-weight: 800;
            color: {COLORS['fg']};
            margin: -35px 0;
        }}

        .password-frame {{
            background-color: {COLORS['surface']};
            border: 3px solid {COLORS['outer']};
            border-radius: 25px;
            min-width: 280px;
            min-height: 50px;
            padding: 5px 20px;
        }}

        .password-dots {{
            font-family: "JetBrainsMono Nerd Font Mono";
            font-size: 28px;
            color: {COLORS['fg']};
            letter-spacing: 8px;
        }}

        .error {{
            font-family: "JetBrainsMono Nerd Font";
            font-size: 14px;
            color: {COLORS['red']};
        }}
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def update_time(self):
        hour, minute = self.get_time()
        date = self.get_date()
        battery = self.get_battery()

        for label in self.date_labels:
            label.set_text(date)
        for label in self.battery_labels:
            label.set_text(battery)
        for label in self.hour_labels_idle:
            label.set_text(hour)
        for label in self.minute_labels_idle:
            label.set_text(minute)
        for label in self.hour_labels_typing:
            label.set_text(hour)
        for label in self.minute_labels_typing:
            label.set_text(minute)

        return True

    def update_password_display(self):
        dots = "●" * len(self.password)
        for label in self.password_labels:
            label.set_text(dots)

    def switch_view(self, view_name):
        for stack in self.stacks:
            stack.set_visible_child_name(view_name)

    def on_key_press(self, controller, keyval, keycode, state):
        keyname = Gdk.keyval_name(keyval)

        if keyname in ('Shift_L', 'Shift_R', 'Control_L', 'Control_R',
                       'Alt_L', 'Alt_R', 'Super_L', 'Super_R', 'Caps_Lock',
                       'Num_Lock', 'Scroll_Lock'):
            return True

        if keyname == 'Return':
            self.try_unlock()
        elif keyname == 'Escape':
            self.password = ""
            self.is_typing = False
            for label in self.error_labels:
                label.set_text("")
            self.update_password_display()
            self.switch_view("idle")
        elif keyname == 'BackSpace':
            if self.password:
                self.password = self.password[:-1]
                self.update_password_display()
                if not self.password:
                    self.is_typing = False
                    self.switch_view("idle")
        else:
            char = None
            if keyval >= 32 and keyval <= 126:
                char = chr(keyval)
            elif keyname == 'space':
                char = ' '

            if char:
                if not self.is_typing:
                    self.is_typing = True
                    self.switch_view("typing")
                self.password += char
                self.update_password_display()

        return True

    def try_unlock(self):
        if not self.password:
            return

        try:
            import pam
            p = pam.pam()
            user = os.environ.get('USER', 'aarav')
            if p.authenticate(user, self.password):
                self.quit()
            else:
                for label in self.error_labels:
                    label.set_text("󰅜 Wrong password")
                self.password = ""
                self.update_password_display()
        except ImportError:
            result = subprocess.run(
                ['sudo', '-S', '-k', 'true'],
                input=self.password.encode(),
                capture_output=True
            )
            if result.returncode == 0:
                self.quit()
            else:
                for label in self.error_labels:
                    label.set_text("󰅜 Wrong password")
                self.password = ""
                self.update_password_display()

if __name__ == '__main__':
    app = LockScreen()
    app.run()
