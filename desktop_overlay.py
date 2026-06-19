import os
import sys
import json
import math
import time
import signal
import datetime
import tkinter as tk
import ctypes

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

def get_window_class_under_cursor(x, y, tooltip_hwnd=None):
    pt = POINT(x, y)
    hwnd = ctypes.windll.user32.WindowFromPoint(pt)
    if not hwnd:
        return ""
        
    # Check if it is our tooltip window
    if tooltip_hwnd and hwnd == tooltip_hwnd:
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
        if tooltip_hwnd and parent == tooltip_hwnd:
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

# -----------------------------------------------------------------------------
# 4. Tkinter Tooltip UI Class
# -----------------------------------------------------------------------------
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
            self.root.attributes("-transparentcolor", "#121212")
        else:
            self.hwnd = None
            
        self.root.config(bg="#121212")
        self.card_width = 280
        self.card_height = 110
        
        # Create canvas for squircle drawing
        self.canvas = tk.Canvas(self.root, bg="#121212", highlightthickness=0, width=self.card_width, height=self.card_height)
        self.canvas.pack(fill="both", expand=True)
        
        # We will initialize the frame and place it in the canvas window
        self.frame = tk.Frame(self.canvas)
        self.canvas.create_window(self.card_width / 2, self.card_height / 2, window=self.frame, width=self.card_width - 16, height=self.card_height - 16)
        
        # Title/Header (Week X)
        self.header_frame = tk.Frame(self.frame)
        self.header_frame.pack(fill="x", padx=4, pady=(4, 4))
        
        self.week_label = tk.Label(self.header_frame, font=("Segoe UI", 11, "bold"))
        self.week_label.pack(side="left")
        
        self.status_label = tk.Label(self.header_frame, font=("Segoe UI", 8, "bold"), padx=6, pady=2)
        self.status_label.pack(side="right")
        
        # Divider Line
        self.divider = tk.Frame(self.frame, height=1)
        self.divider.pack(fill="x", padx=4, pady=4)
        
        # Details (Age & Date Range)
        self.body_frame = tk.Frame(self.frame)
        self.body_frame.pack(fill="both", expand=True, padx=4, pady=(4, 4))
        
        self.age_lbl = tk.Label(self.body_frame, text="Age:", font=("Segoe UI", 9))
        self.age_lbl.grid(row=0, column=0, sticky="w", pady=2)
        self.age_val = tk.Label(self.body_frame, font=("Segoe UI", 9, "bold"))
        self.age_val.grid(row=0, column=1, sticky="e", pady=2)
        
        self.date_lbl = tk.Label(self.body_frame, text="Dates:", font=("Segoe UI", 9))
        self.date_lbl.grid(row=1, column=0, sticky="w", pady=2)
        self.date_val = tk.Label(self.body_frame, font=("Segoe UI", 9, "bold"))
        self.date_val.grid(row=1, column=1, sticky="e", pady=2)
        
        self.body_frame.columnconfigure(0, weight=1)
        self.body_frame.columnconfigure(1, weight=1)
        
        self.visible = False
        
    def update_theme(self, theme):
        lived = theme.get("lived_dot", "#a3a3a3")
        remaining = theme.get("remaining_dot", "#262626")
        text = theme.get("text", "#737373")
        
        # Elegant dark card design
        card_bg = "#18181b"
        card_fg = "#f4f4f5"
        border_color = lived
        
        # Redraw canvas squircle
        self.canvas.delete("squircle_bg")
        draw_squircle(self.canvas, 2, 2, self.card_width - 2, self.card_height - 2, 16, fill=card_bg, outline=border_color, width=2, tags="squircle_bg")
        
        # Style inner widgets
        self.frame.config(bg=card_bg)
        self.header_frame.config(bg=card_bg)
        self.week_label.config(bg=card_bg, fg=lived)
        self.divider.config(bg="#27272a")
        self.body_frame.config(bg=card_bg)
        
        self.age_lbl.config(bg=card_bg, fg=text)
        self.age_val.config(bg=card_bg, fg=card_fg)
        self.date_lbl.config(bg=card_bg, fg=text)
        self.date_val.config(bg=card_bg, fg=card_fg)
        
        self.lived_color = lived
        self.remaining_color = remaining
        self.text_color = text
        
    def show(self, week_num, is_lived, age_str, dates_str, x, y):
        self.week_label.config(text=f"Week {week_num}")
        
        if is_lived:
            status_bg = "#22c55e" if self.lived_color == "#4ade80" else self.lived_color
            status_fg = "#ffffff" if self.lived_color in ("#a3a3a3", "#262626") else "#000000"
        else:
            status_bg = self.remaining_color
            status_fg = "#ffffff"
            
        self.status_label.config(text="LIVED" if is_lived else "REMAINING", bg=status_bg, fg=status_fg)
        self.age_val.config(text=age_str)
        self.date_val.config(text=dates_str)
        
        # Position slightly offset from mouse cursor
        tx = x + 15
        ty = y + 15
        
        # Prevent tooltip from rendering off-screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        
        if tx + self.card_width > screen_w:
            tx = x - self.card_width - 15
        if ty + self.card_height > screen_h:
            ty = y - self.card_height - 15
            
        self.root.geometry(f"{self.card_width}x{self.card_height}+{tx}+{ty}")
            
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
    cls = get_window_class_under_cursor(mx, my, tooltip.hwnd)
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
                hovering_dot = True
                
    if not hovering_dot:
        tooltip.hide()
        
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
