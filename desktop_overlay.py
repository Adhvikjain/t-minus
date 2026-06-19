import os
import sys
import json
import math
import time
import signal
import datetime
import tkinter as tk
import ctypes
from PIL import Image, ImageDraw, ImageTk

# -----------------------------------------------------------------------------
# 1. Configuration & Path Setup
# -----------------------------------------------------------------------------
user_dir = os.path.expanduser("~")
wallpaper_dir = os.path.join(user_dir, "wallpaper_life")
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
pid_path = os.path.join(wallpaper_dir, "overlay.pid")

# Ensure wallpaper dir exists
os.makedirs(wallpaper_dir, exist_ok=True)

# Write current process ID to overlay.pid
try:
    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))
except Exception as e:
    print(f"Warning: Could not write PID file: {e}")

# -----------------------------------------------------------------------------
# 2. Windows API Ctypes Helpers
# -----------------------------------------------------------------------------
class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_mouse_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def get_window_class_under_cursor(x, y, tooltip_hwnd=None, highlight_hwnd=None):
    pt = POINT(x, y)
    hwnd = ctypes.windll.user32.WindowFromPoint(pt)
    if not hwnd:
        return ""
        
    # Check if it is our tooltip or highlight window
    if (tooltip_hwnd and hwnd == tooltip_hwnd) or (highlight_hwnd and hwnd == highlight_hwnd):
        return "Tooltip"
    
    # Check current window class
    buf = ctypes.create_unicode_buffer(512)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 512)
    class_name = buf.value
    
    # Desktop list view or background windows
    if class_name in ("SysListView32", "SHELLDLL_DefView", "WorkerW", "Progman"):
        return class_name
        
    # Check parent windows (traverse up to find if it's hosted in WorkerW/Progman or is our tooltip)
    parent = ctypes.windll.user32.GetParent(hwnd)
    while parent:
        if (tooltip_hwnd and parent == tooltip_hwnd) or (highlight_hwnd and parent == highlight_hwnd):
            return "Tooltip"
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetClassNameW(parent, buf, 512)
        parent_class = buf.value
        if parent_class in ("WorkerW", "Progman"):
            return parent_class
        parent = ctypes.windll.user32.GetParent(parent)
        
    return class_name

# -----------------------------------------------------------------------------
# 3. Grid & Metrics Calculations
# -----------------------------------------------------------------------------
def get_screen_resolution():
    """Retrieves physical screen resolution."""
    if sys.platform == "win32":
        try:
            # Set process DPI aware so we get physical pixel coords
            ctypes.windll.user32.SetProcessDPIAware()
            width = ctypes.windll.user32.GetSystemMetrics(0)
            height = ctypes.windll.user32.GetSystemMetrics(1)
            if width > 0 and height > 0:
                return width, height
        except Exception:
            pass
    return 1920, 1080

def compute_grid_coords(width, height):
    """Calculates dot positions and spacing matching generate_wallpaper.py."""
    padding_right = 24
    padding_top = 24
    padding_bottom = 24
    
    grid_width_ratio = 0.55
    grid_w = (width * grid_width_ratio) - padding_right
    grid_h = height - padding_top - padding_bottom
    
    cols = 50
    rows = 65
    
    approx_spacing = min(grid_w / cols, grid_h / rows)
    lived_radius = approx_spacing * 0.30
    lived_radius = max(1.5, lived_radius)
    
    grid_w_centers = grid_w - (2 * lived_radius)
    grid_h_centers = grid_h - (2 * lived_radius)
    
    dx = grid_w_centers / max(1, cols - 1)
    dy = grid_h_centers / max(1, rows - 1)
    spacing = min(dx, dy)
    
    drawn_w = spacing * (cols - 1)
    drawn_h = spacing * (rows - 1)
    
    start_x = width - padding_right - lived_radius - drawn_w
    start_y = padding_top + lived_radius + (grid_h_centers - drawn_h) / 2
    
    return {
        "start_x": start_x,
        "start_y": start_y,
        "spacing": spacing,
        "cols": cols,
        "rows": rows,
        "lived_radius": lived_radius
    }

def load_config():
    """Loads configuration from config.json."""
    default_config = {
        "birth_date": "2000-01-01",
        "life_expectancy_years": 80,
        "theme": {
            "background": "#09090b",
            "lived_dot": "#a3a3a3",
            "remaining_dot": "#262626",
            "text": "#737373"
        }
    }
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                return config, os.path.getmtime(config_path)
    except Exception:
        pass
    return default_config, 0

def draw_squircle(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1+r, y1,
        x2-r, y1,
        x2, y1,
        x2, y1+r,
        x2, y2-r,
        x2, y2,
        x2-r, y2,
        x1+r, y2,
        x1, y2,
        x1, y2-r,
        x1, y1+r,
        x1, y1
    ]
    return canvas.create_polygon(points, **kwargs, smooth=True)

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c*2 for c in hex_color])
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

class TooltipWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # Start hidden
        self.root.overrideredirect(True)  # Borderless window
        self.root.wm_attributes("-topmost", True)  # Always on top
        
        # Configure window styles via Windows API to be completely non-activatable (non-focusable click-through)
        if sys.platform == "win32":
            self.root.update_idletasks()  # Force window creation to get valid HWND
            self.hwnd = self.root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT)
            
            # Set transparency color key
            self.root.attributes("-transparentcolor", "#09090b")
        else:
            self.hwnd = None
            
        self.root.config(bg="#09090b")
        self.card_width = 240
        self.card_height = 125
        
        # Create canvas
        self.canvas = tk.Canvas(self.root, bg="#09090b", highlightthickness=0, width=self.card_width, height=self.card_height)
        self.canvas.pack(fill="both", expand=True)
        
        self.visible = False
        self.theme = {}
        self.photo_img = None
        
    def update_theme(self, theme):
        self.theme = theme
        bg_color = theme.get("background", "#09090b")
        if sys.platform == "win32":
            self.root.attributes("-transparentcolor", bg_color)
        self.root.config(bg=bg_color)
        self.canvas.config(bg=bg_color)
        
    def show(self, week_num, is_lived, age_str, dates_str, cx, cy):
        # Render the tooltip card as a solid RGB image
        bg_color = self.theme.get("background", "#09090b")
        img = Image.new("RGB", (self.card_width, self.card_height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 1. Main Background Squircle
        draw.rounded_rectangle([2, 2, self.card_width - 2, self.card_height - 2], radius=16, fill=(24, 24, 27)) # #18181b
        
        # 2. Load Fonts
        try:
            import os
            font_dir = "C:\\Windows\\Fonts"
            font_bold = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 14)
            font_regular = ImageFont.truetype(os.path.join(font_dir, "segoeui.ttf"), 12)
            font_sm_bold = ImageFont.truetype(os.path.join(font_dir, "segoeuib.ttf"), 10)
        except Exception:
            font_bold = ImageFont.load_default()
            font_regular = ImageFont.load_default()
            font_sm_bold = ImageFont.load_default()
            
        # 3. Draw Header Week text
        try:
            draw.text((20, 24), f"Week {week_num}", font=font_bold, fill=(255, 255, 255), anchor="lm")
        except (ValueError, AttributeError):
            draw.text((20, 18), f"Week {week_num}", font=font_bold, fill=(255, 255, 255))
        
        # 4. Draw Header Badge: LIVED / REMAINING
        badge_text = "LIVED" if is_lived else "REMAINING"
        if is_lived:
            badge_bg = (39, 39, 42) # #27272a
            badge_fg = (161, 161, 170) # #a1a1aa
        else:
            badge_bg = (30, 30, 32) # #1e1e20
            badge_fg = (113, 113, 122) # #71717a
            
        # Draw badge squircle
        draw.rounded_rectangle([155, 14, 220, 34], radius=5, fill=badge_bg)
        try:
            draw.text((187, 24), badge_text, font=font_sm_bold, fill=badge_fg, anchor="mm")
        except (ValueError, AttributeError):
            draw.text((165, 18), badge_text, font=font_sm_bold, fill=badge_fg)
        
        # 5. Divider Line
        draw.line([(20, 44), (220, 44)], fill=(39, 39, 42), width=1) # #27272a
        
        # 6. Body: Age Row
        try:
            draw.text((20, 62), "Age:", font=font_regular, fill=(113, 113, 122), anchor="lm") # #71717a
            draw.text((220, 62), age_str, font=font_bold, fill=(255, 255, 255), anchor="rm")
        except (ValueError, AttributeError):
            draw.text((20, 56), "Age:", font=font_regular, fill=(113, 113, 122))
            draw.text((150, 56), age_str, font=font_bold, fill=(255, 255, 255))
        
        # 7. Body: Date Range Pill
        draw.rounded_rectangle([20, 78, 220, 108], radius=6, fill=(9, 9, 11)) # #09090b
        try:
            draw.text((120, 93), dates_str, font=font_bold, fill=(228, 228, 231), anchor="mm") # #e4e4e7
        except (ValueError, AttributeError):
            draw.text((30, 86), dates_str, font=font_bold, fill=(228, 228, 231))
        
        # Convert to PhotoImage and update canvas
        self.photo_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo_img, anchor="nw")
        
        # Center horizontally, offset above dot
        tx = int(cx - self.card_width / 2)
        ty = int(cy - self.card_height - 15)
        
        # Prevent tooltip from rendering off-screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        if tx < 10:
            tx = 10
        elif tx + self.card_width > screen_w - 10:
            tx = screen_w - self.card_width - 10
            
        if ty < 10:
            ty = cy + 15
            
        self.root.geometry(f"{self.card_width}x{self.card_height}+{tx}+{ty}")
            
        if not self.visible:
            self.root.deiconify()
            self.visible = True
            
    def hide(self):
        if self.visible:
            self.root.withdraw()
            self.visible = False

class HighlightWindow:
    def __init__(self, master):
        self.root = tk.Toplevel(master)
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        
        if sys.platform == "win32":
            self.root.update_idletasks()
            self.hwnd = self.root.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TRANSPARENT = 0x00000020
            style = ctypes.windll.user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT)
            self.root.attributes("-transparentcolor", "#09090b")
            
        self.root.config(bg="#09090b")
        self.size = 60
        self.canvas = tk.Canvas(self.root, bg="#09090b", highlightthickness=0, width=self.size, height=self.size)
        self.canvas.pack(fill="both", expand=True)
        self.visible = False
        self.glow_img = None
        self.photo_img = None

    def update_glow(self, radius, color, bg_color):
        r, g, b = 255, 255, 255  # White highlight/glow
        
        # Solid base image
        img = Image.new("RGB", (self.size, self.size), bg_color)
        
        # RGBA overlay
        overlay = Image.new("RGBA", (self.size, self.size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        center = self.size // 2
        glow_radius = radius * 3.0
        
        # Smooth radial glow
        for i in range(int(glow_radius), radius - 1, -1):
            pct = (i - radius) / max(1, (glow_radius - radius))
            alpha = int(120 * (1.0 - pct)**2)
            draw.rounded_rectangle(
                [center - i, center - i, center + i, center + i],
                radius=int(i * 0.45),
                fill=(r, g, b, alpha)
            )
            
        # Main bright white dot
        draw.rounded_rectangle(
            [center - radius, center - radius, center + radius, center + radius],
            radius=int(radius * 0.45),
            fill=(255, 255, 255, 255)
        )
        
        # Alpha composite overlay onto base image
        img.paste(overlay, (0, 0), overlay)
        
        self.glow_img = img
        self.photo_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(center, center, image=self.photo_img)

    def update_theme(self, theme):
        bg_color = theme.get("background", "#09090b")
        if sys.platform == "win32":
            self.root.attributes("-transparentcolor", bg_color)
        self.root.config(bg=bg_color)
        self.canvas.config(bg=bg_color)

    def show(self, cx, cy):
        tx = int(cx - self.size / 2)
        ty = int(cy - self.size / 2)
        self.root.geometry(f"{self.size}x{self.size}+{tx}+{ty}")
        if not self.visible:
            self.root.deiconify()
            self.visible = True

    def hide(self):
        if self.visible:
            self.root.withdraw()
            self.visible = False

# -----------------------------------------------------------------------------
# 5. Core Polling Loop
# -----------------------------------------------------------------------------
def check_hover():
    global last_mtime, config, birth_date, weeks_lived
    global start_x, start_y, spacing, cols, rows, lived_radius
    
    # Reload config if file changes
    try:
        current_mtime = os.path.getmtime(config_path)
        if current_mtime != last_mtime:
            config, last_mtime = load_config()
            birth_date = datetime.datetime.strptime(config["birth_date"], "%Y-%m-%d").date()
            
            # Recalculate metrics
            life_expectancy = float(config["life_expectancy_years"])
            total_days = int(round(life_expectancy * 365.25))
            today = datetime.date.today()
            days_lived = (today - birth_date).days
            days_lived = max(0, min(days_lived, total_days))
            weeks_lived = days_lived // 7
            
            tooltip.update_theme(config.get("theme", {}))
            highlight.update_theme(config.get("theme", {}))
            highlight.update_glow(int(lived_radius), "#ffffff", config.get("theme", {}).get("background", "#09090b"))
            
            # Recalculate grid coordinate projections (in case resolution changed too)
            width, height = get_screen_resolution()
            geom = compute_grid_coords(width, height)
            start_x = geom["start_x"]
            start_y = geom["start_y"]
            spacing = geom["spacing"]
            cols = geom["cols"]
            rows = geom["rows"]
            lived_radius = geom["lived_radius"]
    except Exception:
        pass
        
    # Get current cursor position
    mx, my = get_mouse_pos()
    
    # Check if window class under cursor is Windows desktop
    cls = get_window_class_under_cursor(mx, my, tooltip.hwnd, highlight.hwnd)
    is_on_desktop = cls in ("WorkerW", "Progman", "SysListView32", "Tooltip")
    
    hovering_dot = False
    
    if is_on_desktop:
        c_float = (mx - start_x) / spacing
        r_float = (my - start_y) / spacing
        c = int(round(c_float))
        r = int(round(r_float))
        
        if 0 <= c < cols and 0 <= r < rows:
            cx = start_x + (c * spacing)
            cy = start_y + (r * spacing)
            dist = math.sqrt((mx - cx)**2 + (my - cy)**2)
            
            # spacing * 0.45 hit box
            if dist <= spacing * 0.45:
                i = r * cols + c
                week_num = i + 1
                is_lived = (i < weeks_lived)
                
                # Calculate dates
                w_start = birth_date + datetime.timedelta(weeks=i)
                w_end = w_start + datetime.timedelta(days=6)
                dates_str = f"{w_start.strftime('%b %d, %Y')} - {w_end.strftime('%b %d, %Y')}"
                
                # Calculate age
                diff_days = i * 7
                age_years = diff_days // 365
                age_weeks = (diff_days % 365) // 7
                age_str = f"{age_years} yr{'s' if age_years != 1 else ''}, {age_weeks} wk{'s' if age_weeks != 1 else ''}"
                
                tooltip.show(week_num, is_lived, age_str, dates_str, int(cx), int(cy))
                highlight.show(int(cx), int(cy))
                hovering_dot = True
                
    if not hovering_dot:
        tooltip.hide()
        highlight.hide()
        
    # Poll every 100ms
    tooltip.root.after(100, check_hover)

# -----------------------------------------------------------------------------
# 6. Main Execution
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Standard signal handling for terminations
    def sig_handler(signum, frame):
        try:
            if os.path.exists(pid_path):
                os.remove(pid_path)
        except Exception:
            pass
        sys.exit(0)
        
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    # Initialize state
    config, last_mtime = load_config()
    birth_date = datetime.datetime.strptime(config["birth_date"], "%Y-%m-%d").date()
    
    life_expectancy = float(config["life_expectancy_years"])
    total_days = int(round(life_expectancy * 365.25))
    today = datetime.date.today()
    days_lived = (today - birth_date).days
    days_lived = max(0, min(days_lived, total_days))
    weeks_lived = days_lived // 7

    # Calculate coordinates
    width, height = get_screen_resolution()
    geom = compute_grid_coords(width, height)
    start_x = geom["start_x"]
    start_y = geom["start_y"]
    spacing = geom["spacing"]
    cols = geom["cols"]
    rows = geom["rows"]
    lived_radius = geom["lived_radius"]

    # Start tooltip UI
    tooltip = TooltipWindow()
    tooltip.update_theme(config.get("theme", {}))
    
    highlight = HighlightWindow(tooltip.root)
    highlight.update_theme(config.get("theme", {}))
    highlight.update_glow(int(lived_radius), "#ffffff", config.get("theme", {}).get("background", "#09090b"))
    
    # Start polling
    tooltip.root.after(100, check_hover)
    
    try:
        tooltip.root.mainloop()
    finally:
        try:
            if os.path.exists(pid_path):
                os.remove(pid_path)
        except Exception:
            pass
