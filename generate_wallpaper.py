import os
import sys
import json
import math
from datetime import datetime, date

# -----------------------------------------------------------------------------
# 1. Dependency Checks & Imports
# -----------------------------------------------------------------------------
dependencies_missing = False

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Error: The 'Pillow' library is required to render the wallpaper.")
    dependencies_missing = True

try:
    import screeninfo
except ImportError:
    # screeninfo is optional; we have ctypes fallback on Windows
    pass

if dependencies_missing:
    print("\nPlease install the missing dependencies using requirements.txt or run:")
    print("  pip install Pillow screeninfo")
    sys.exit(1)

# -----------------------------------------------------------------------------
# 2. Helper Functions
# -----------------------------------------------------------------------------
def load_config():
    """Loads configuration from config.json. Creates default if missing."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    
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
        if not os.path.exists(config_path):
            with open(config_path, "w") as f:
                json.dump(default_config, f, indent=2)
            return default_config
            
        with open(config_path, "r") as f:
            config = json.load(f)
            
        # Ensure default values are populated if keys are missing
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
            elif key == "theme" and isinstance(config[key], dict):
                for t_key, t_val in default_config["theme"].items():
                    if t_key not in config["theme"]:
                        config["theme"][t_key] = t_val
        return config
    except Exception as e:
        print(f"Error loading/creating config.json: {e}")
        print("Falling back to default configuration.")
        return default_config

def get_screen_resolution():
    """Retrieves screen resolution. Prioritizes DPI-aware ctypes, then screeninfo, then default."""
    # 1. Try ctypes on Windows (DPI-aware)
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Set process DPI aware so we get real physical pixels, not scaled ones
            user32.SetProcessDPIAware()
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            if width > 0 and height > 0:
                return width, height
        except Exception as e:
            print(f"Warning: DPI-aware resolution check failed: {e}")
            
    # 2. Try screeninfo library
    try:
        monitors = screeninfo.get_monitors()
        if monitors:
            primary = next((m for m in monitors if m.is_primary), monitors[0])
            return primary.width, primary.height
    except Exception as e:
        print(f"Warning: screeninfo resolution check failed: {e}")
        
    # 3. Fallback
    print("Warning: Could not detect screen resolution. Using default 1920x1080.")
    return 1920, 1080

def update_wallpaper_registry(image_path):
    """Updates registry settings for wallpaper fit/style."""
    if sys.platform != "win32":
        return
        
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_SET_VALUE)
        # Style 6 = Fit, TileWallpaper = 0 (do not tile)
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "6")
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"Warning: Could not update registry settings: {e}")

def set_wallpaper(image_path):
    """Sets the wallpaper on Windows using ctypes SystemParametersInfoW."""
    if sys.platform != "win32":
        print("Skipping wallpaper setting: not on Windows.")
        return False
        
    abs_path = os.path.abspath(image_path)
    if not os.path.exists(abs_path):
        print(f"Error: Wallpaper image file not found at: {abs_path}")
        return False
        
    try:
        # First update registry for style settings
        update_wallpaper_registry(abs_path)
        
        import ctypes
        SPI_SETDESKWALLPAPER = 20
        SPIF_UPDATEINIFILE = 0x01
        SPIF_SENDCHANGE = 0x02
        
        result = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER,
            0,
            abs_path,
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
        )
        if not result:
            raise ctypes.WinError()
        print("Successfully updated desktop wallpaper!")
        return True
    except Exception as e:
        print(f"Error setting wallpaper via system API: {e}")
        return False

# -----------------------------------------------------------------------------
# 3. Main Logic
# -----------------------------------------------------------------------------
def main():
    print("Starting Life Progress Wallpaper generator...")
    
    # Load settings
    config = load_config()
    
    # 1. Parse dates and calculate metrics
    try:
        birth_date = datetime.strptime(config["birth_date"], "%Y-%m-%d").date()
    except ValueError as e:
        print(f"Error parsing birth_date: {e}. Please use YYYY-MM-DD format.")
        sys.exit(1)
        
    life_expectancy = float(config["life_expectancy_years"])
    total_days = int(round(life_expectancy * 365.25))
    
    today = date.today()
    days_lived = (today - birth_date).days
    days_lived = max(0, min(days_lived, total_days))
    
    # Calculate weeks metrics instead of days
    total_weeks = total_days // 7
    weeks_lived = days_lived // 7
    weeks_lived = max(0, min(weeks_lived, total_weeks))
    weeks_remaining = total_weeks - weeks_lived
    pct_lived = (weeks_lived / total_weeks) * 100.0 if total_weeks > 0 else 0.0
    
    print(f"Life Metrics: Expected {life_expectancy} years ({total_weeks} weeks).")
    print(f"Lived: {weeks_lived} weeks ({pct_lived:.2f}%). Remaining: {weeks_remaining} weeks.")
    
    # 2. Get screen resolution
    width, height = get_screen_resolution()
    print(f"Detected screen resolution: {width}x{height}")
    
    # 3. Load theme colors
    theme = config.get("theme", {})
    bg_color = theme.get("background", "#0b0f19")
    lived_color = theme.get("lived_dot", "#ff5f40")
    remaining_color = theme.get("remaining_dot", "#475569")
    text_color = theme.get("text", "#94a3b8")
    
    # Create blank canvas
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # 4. Grid Calculations
    # Corner-to-corner layout setup (margins equal to lived_radius to touch edges exactly)
    # 4. Grid Calculations (Right-Aligned Column Layout)
    padding_right = 24
    padding_top = 24
    padding_bottom = 24 # Symmetrical small top/bottom padding to stretch height
    
    # Grid width is set to 55% of screen width (keeps left 45% clear for icons)
    grid_width_ratio = 0.55
    grid_w = (width * grid_width_ratio) - padding_right
    grid_h = height - padding_top - padding_bottom
    
    grid_aspect = grid_w / grid_h
    
    # Force grid to exactly 50 columns and 65 rows as requested
    cols = 50
    rows = 65
    total_weeks = cols * rows
    pct_lived = (weeks_lived / total_weeks) * 100.0 if total_weeks > 0 else 0.0
        
    # Approximate spacing to determine dot sizes
    approx_spacing = min(grid_w / cols, grid_h / rows)
    lived_radius = approx_spacing * 0.30
    lived_radius = max(1.5, lived_radius)
    remaining_radius = lived_radius
    
    # Grid centers bounding box
    grid_w_centers = grid_w - (2 * lived_radius)
    grid_h_centers = grid_h - (2 * lived_radius)
    
    # Spacing between dot centers (keep uniform to maintain perfect square aspect ratio)
    dx = grid_w_centers / max(1, cols - 1)
    dy = grid_h_centers / max(1, rows - 1)
    spacing = min(dx, dy)
    
    # Actual drawn size
    drawn_w = spacing * (cols - 1)
    drawn_h = spacing * (rows - 1)
    
    # Align to the right side of the screen
    start_x = width - padding_right - lived_radius - drawn_w
    start_y = padding_top + lived_radius + (grid_h_centers - drawn_h) / 2
    
    # Keep spacing safety margins
    if lived_radius * 2 >= spacing:
        lived_radius = max(1.0, (spacing - 1.0) / 2)
        
    # Convert all radii to exact integer pixels to prevent sub-pixel rasterization size differences
    lived_radius_int = int(round(lived_radius))
    remaining_radius_int = lived_radius_int
    corner_rad_int = int(round(max(1.0, lived_radius_int * 0.45)))
        
    print(f"Grid details: {cols} cols x {rows} rows. Spacing: {spacing:.2f}px. Dot radii (pixels): lived={lived_radius_int}px, remaining={remaining_radius_int}px")
    
    # 5. Draw the grid
    for i in range(total_weeks):
        c = i % cols
        r = i // cols
        
        # Round coordinate centers to exact integers to align on pixel grid perfectly
        cx = int(round(start_x + (c * spacing)))
        cy = int(round(start_y + (r * spacing)))
        
        is_lived = (i < weeks_lived)
        rad = lived_radius_int
        color = lived_color if is_lived else remaining_color
        
        # Bounding box for the dot (integer bounds guarantee identical pixel width/height)
        bbox = [cx - rad, cy - rad, cx + rad, cy + rad]
        draw.rounded_rectangle(bbox, radius=corner_rad_int, fill=color)
        
    # Draw a rounded rectangle border box enclosing the grid
    border_padding = 16
    bx0 = int(round(start_x - lived_radius_int - border_padding))
    by0 = int(round(start_y - lived_radius_int - border_padding))
    bx1 = int(round(start_x + drawn_w + lived_radius_int + border_padding))
    by1 = int(round(start_y + drawn_h + lived_radius_int + border_padding))
    
    border_bbox = [bx0, by0, bx1, by1]
    border_corner_rad = 16
    
    # Draw the card border outline using lived_color
    draw.rounded_rectangle(border_bbox, radius=border_corner_rad, outline=lived_color, width=2)
    
    # 7. Save Image
    user_dir = os.path.expanduser("~")
    wallpaper_dir = os.path.join(user_dir, "wallpaper_life")
    
    try:
        os.makedirs(wallpaper_dir, exist_ok=True)
        wallpaper_path = os.path.join(wallpaper_dir, "life_wallpaper.png")
        img.save(wallpaper_path, "PNG")
        print(f"Successfully generated and saved wallpaper to: {wallpaper_path}")
    except Exception as e:
        print(f"Error saving wallpaper image file: {e}")
        sys.exit(1)
        
    # 8. Set Wallpaper
    success = set_wallpaper(wallpaper_path)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error during execution: {e}")
        sys.exit(1)
