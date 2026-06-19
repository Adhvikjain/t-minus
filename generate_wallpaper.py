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
    
    # Parse arguments
    import argparse
    parser = argparse.ArgumentParser(description="Life Progress Wallpaper Generator")
    parser.add_argument("--open", action="store_true", help="Open the interactive web dashboard in your default browser")
    args, unknown = parser.parse_known_args()
    
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

    # 3.5 Draw Left Panel text and metrics
    try:
        from PIL import ImageFont
        font_logo = ImageFont.truetype("segoeuib.ttf", 20)
        font_h1 = ImageFont.truetype("segoeuib.ttf", 60)
        font_subtitle = ImageFont.truetype("segoeui.ttf", 22)
        font_metric_label = ImageFont.truetype("segoeuib.ttf", 16)
        font_metric_value = ImageFont.truetype("segoeuib.ttf", 32)
    except Exception:
        font_logo = ImageFont.load_default()
        font_h1 = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_metric_label = ImageFont.load_default()
        font_metric_value = ImageFont.load_default()

    left_padding = int(width * 0.08)
    top_padding = int(height * 0.15)
    
    # Texts
    draw.text((left_padding, top_padding), "T-MINUS", font=font_logo, fill=lived_color)
    draw.text((left_padding, top_padding + 30), "Your Life Progress", font=font_h1, fill=(255,255,255))
    draw.text((left_padding, top_padding + 110), "Every square represents one week of your life. Make each one count.", font=font_subtitle, fill=text_color)
    
    # Metrics
    metrics_top = top_padding + 190
    
    # Born
    draw.text((left_padding, metrics_top), "BORN", font=font_metric_label, fill=text_color)
    draw.text((left_padding, metrics_top + 25), birth_date.strftime("%B %d, %Y"), font=font_metric_value, fill=(255,255,255))
    
    # Age
    age_years = (today.year - birth_date.year) - ((today.month, today.day) < (birth_date.month, birth_date.day))
    age_months = (today.month - birth_date.month) % 12
    if age_months < 0: age_months += 12
    draw.text((left_padding, metrics_top + 100), "AGE", font=font_metric_label, fill=text_color)
    draw.text((left_padding, metrics_top + 125), f"{age_years} yrs, {age_months} mos", font=font_metric_value, fill=(255,255,255))
    
    # Weeks
    draw.text((left_padding, metrics_top + 200), "LIVED / TOTAL WEEKS", font=font_metric_label, fill=text_color)
    draw.text((left_padding, metrics_top + 225), f"{weeks_lived} / {total_weeks}", font=font_metric_value, fill=(255,255,255))
    
    # Progress Bar
    bar_top = metrics_top + 320
    bar_width = int(width * 0.3)
    bar_height = 8
    draw.rounded_rectangle([left_padding, bar_top, left_padding + bar_width, bar_top + bar_height], radius=4, fill=remaining_color)
    draw.rounded_rectangle([left_padding, bar_top, left_padding + int(bar_width * (pct_lived / 100)), bar_top + bar_height], radius=4, fill=lived_color)
    
    draw.text((left_padding, bar_top + 20), f"{pct_lived:.2f}% Lived", font=font_metric_label, fill=text_color)
    draw.text((left_padding + bar_width - 120, bar_top + 20), f"{weeks_remaining} weeks left", font=font_metric_label, fill=text_color)

    
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
    lived_corner_rad = int(round(max(1.0, lived_radius_int * 0.15)))
    remaining_corner_rad = int(round(max(1.0, lived_radius_int * 0.45)))
        
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
        if is_lived:
            draw.rounded_rectangle(bbox, radius=lived_corner_rad, fill=color)
        else:
            draw.rounded_rectangle(bbox, radius=remaining_corner_rad, fill=color)
        
    # Draw a rounded rectangle border box enclosing the grid
    border_padding = 16
    bx0 = int(round(start_x - lived_radius_int - border_padding))
    by0 = int(round(start_y - lived_radius_int - border_padding))
    bx1 = int(round(start_x + drawn_w + lived_radius_int + border_padding))
    by1 = int(round(start_y + drawn_h + lived_radius_int + border_padding))
    
    border_bbox = [bx0, by0, bx1, by1]
    border_corner_rad = 24
    
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
        
    # 7b. Generate and save interactive HTML dashboard
    html_path = os.path.join(wallpaper_dir, "life_progress.html")
    try:
        def hex_to_rgb_str(hex_val):
            hex_val = hex_val.lstrip('#')
            if len(hex_val) == 3:
                hex_val = ''.join([c*2 for c in hex_val])
            try:
                r = int(hex_val[0:2], 16)
                g = int(hex_val[2:4], 16)
                b = int(hex_val[4:6], 16)
                return f"{r}, {g}, {b}"
            except Exception:
                return "163, 163, 163"
                
        lived_rgb = hex_to_rgb_str(lived_color)
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>T-Minus: Life Progress Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: {bg_color};
            --lived-color: {lived_color};
            --remaining-color: {remaining_color};
            --text-color: {text_color};
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            background-color: var(--bg-color);
            color: #f4f4f5;
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 2rem;
            overflow-x: hidden;
            position: relative;
        }}
        
        /* Ambient Background Glow */
        body::before {{
            content: '';
            position: absolute;
            width: 600px;
            height: 600px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba({lived_rgb}, 0.08) 0%, rgba(0,0,0,0) 70%);
            top: 10%;
            right: 10%;
            pointer-events: none;
            z-index: 0;
        }}
        body::after {{
            content: '';
            position: absolute;
            width: 400px;
            height: 400px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba({lived_rgb}, 0.05) 0%, rgba(0,0,0,0) 70%);
            bottom: 10%;
            left: 10%;
            pointer-events: none;
            z-index: 0;
        }}
        
        .container {{
            width: 100%;
            max-width: 1200px;
            background: rgba(255, 255, 255, 0.015);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 24px;
            padding: 2.5rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            display: grid;
            grid-template-columns: 1fr 1.5fr;
            gap: 3rem;
            position: relative;
            z-index: 1;
            animation: fadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .info-panel {{
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        
        .header {{
            margin-bottom: 2rem;
        }}
        
        .logo {{
            font-family: 'Outfit', sans-serif;
            font-size: 1rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--lived-color);
            margin-bottom: 0.5rem;
        }}
        
        h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 3rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 1rem;
            background: linear-gradient(to right, #ffffff, rgba(255, 255, 255, 0.7));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .subtitle {{
            font-size: 1.1rem;
            color: var(--text-color);
            line-height: 1.6;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 1.25rem;
            margin: 2rem 0;
        }}
        
        .metric-card {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 16px;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            transition: all 0.3s ease;
        }}
        
        .metric-card:hover {{
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(255, 255, 255, 0.08);
            transform: translateY(-2px);
        }}
        
        .metric-label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-color);
            font-weight: 500;
        }}
        
        .metric-value {{
            font-family: 'Outfit', sans-serif;
            font-size: 1.75rem;
            font-weight: 700;
            color: #f4f4f5;
        }}
        
        .progress-container {{
            margin-top: 1rem;
        }}
        
        .progress-bar-bg {{
            height: 8px;
            background: var(--remaining-color);
            border-radius: 9999px;
            overflow: hidden;
            margin-bottom: 0.5rem;
        }}
        
        .progress-bar-fill {{
            height: 100%;
            background: var(--lived-color);
            border-radius: 9999px;
            width: 0%;
            transition: width 1.2s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        
        .progress-stats {{
            display: flex;
            justify-content: space-between;
            font-size: 0.85rem;
            color: var(--text-color);
        }}
        
        .legend {{
            display: flex;
            gap: 1.5rem;
            margin-top: auto;
            padding-top: 2rem;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            color: var(--text-color);
        }}
        
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
        }}
        
        .legend-dot.lived {{
            background-color: var(--lived-color);
        }}
        
        .legend-dot.remaining {{
            background-color: var(--remaining-color);
        }}
        
        .grid-panel {{
            display: flex;
            justify-content: center;
            align-items: center;
            background: rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.03);
            border-radius: 20px;
            padding: 1.5rem;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: repeat(50, 1fr);
            gap: 3px;
            width: 100%;
            max-width: 600px;
            aspect-ratio: 50 / 65;
        }}
        
        .dot {{
            aspect-ratio: 1;
            cursor: pointer;
            transition: transform 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275), 
                        box-shadow 0.2s ease, 
                        filter 0.2s ease;
            position: relative;
        }}
        
        .dot.lived {{
            border-radius: 15%;
        }}
        
        .dot.remaining {{
            border-radius: 35%;
        }}
        
        .dot:hover {{
            transform: scale(2.2);
            z-index: 10;
            box-shadow: 0 0 10px var(--lived-color);
            filter: brightness(1.3);
        }}
        
        .dot.remaining:hover {{
            box-shadow: 0 0 10px var(--text-color);
        }}
        
        /* Floating Tooltip */
        .tooltip {{
            position: absolute;
            pointer-events: none;
            opacity: 0;
            background: rgba(18, 18, 24, 0.95);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1rem;
            box-shadow: 0 15px 35px -5px rgba(0, 0, 0, 0.7);
            color: #f4f4f5;
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            z-index: 1000;
            width: 250px;
            transition: opacity 0.15s ease;
            transform: translate(-50%, -115%);
        }}
        
        .tooltip-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 0.5rem;
            margin-bottom: 0.5rem;
        }}
        
        .tooltip-week {{
            font-family: 'Outfit', sans-serif;
            font-weight: 700;
            color: var(--lived-color);
        }}
        
        .tooltip-status {{
            font-size: 0.75rem;
            text-transform: uppercase;
            font-weight: 600;
            letter-spacing: 0.05em;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        
        .tooltip-status.lived {{
            background: rgba({lived_rgb}, 0.15);
            color: var(--lived-color);
        }}
        
        .tooltip-status.remaining {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-color);
        }}
        
        .tooltip-body {{
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
        }}
        
        .tooltip-row {{
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
        }}
        
        .tooltip-label {{
            color: var(--text-color);
        }}
        
        .tooltip-val {{
            font-weight: 500;
        }}
        
        .tooltip-dates {{
            margin-top: 0.25rem;
            font-size: 0.8rem;
            background: rgba(255, 255, 255, 0.02);
            padding: 6px;
            border-radius: 6px;
            border: 1px solid rgba(255, 255, 255, 0.04);
            text-align: center;
            font-weight: 500;
        }}
        
        /* Responsiveness */
        @media (max-width: 900px) {{
            body {{
                padding: 1rem;
            }}
            .container {{
                grid-template-columns: 1fr;
                gap: 2rem;
                padding: 1.5rem;
            }}
            .info-panel {{
                gap: 2rem;
            }}
            .legend {{
                margin-top: 2rem;
            }}
        }}
    </style>
</head>
<body>

    <div class="container">
        <div class="info-panel">
            <div class="header">
                <div class="logo">T-MINUS</div>
                <h1>Your Life Progress</h1>
                <p class="subtitle">Every square represents one week of your life. Make each one count.</p>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-card">
                    <span class="metric-label">Born</span>
                    <span class="metric-value" id="birth-date-val">-</span>
                </div>
                <div class="metric-card">
                    <span class="metric-label">Age</span>
                    <span class="metric-value" id="age-val">-</span>
                </div>
                <div class="metric-card">
                    <span class="metric-label">Lived / Total Weeks</span>
                    <span class="metric-value" id="weeks-val">-</span>
                </div>
            </div>
            
            <div class="progress-container">
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="progress-fill"></div>
                </div>
                <div class="progress-stats">
                    <span id="pct-lived-val">0.00% Lived</span>
                    <span id="weeks-remaining-val">- weeks left</span>
                </div>
            </div>
            
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-dot lived"></div>
                    <span>Lived Week</span>
                </div>
                <div class="legend-item">
                    <div class="legend-dot remaining"></div>
                    <span>Remaining Week</span>
                </div>
            </div>
        </div>
        
        <div class="grid-panel">
            <div class="grid" id="grid"></div>
        </div>
    </div>
    
    <div class="tooltip" id="tooltip">
        <div class="tooltip-header">
            <span class="tooltip-week" id="tt-week">Week 0</span>
            <span class="tooltip-status" id="tt-status">Lived</span>
        </div>
        <div class="tooltip-body">
            <div class="tooltip-row">
                <span class="tooltip-label">Age:</span>
                <span class="tooltip-val" id="tt-age">-</span>
            </div>
            <div class="tooltip-dates" id="tt-dates">-</div>
        </div>
    </div>

    <script>
        const config = {{
            birthDate: "{config['birth_date']}",
            lifeExpectancy: {life_expectancy},
            weeksLived: {weeks_lived},
            totalWeeks: {total_weeks},
            theme: {{
                background: "{bg_color}",
                lived: "{lived_color}",
                remaining: "{remaining_color}",
                text: "{text_color}"
            }}
        }};

        // Populate Dashboard UI
        const birthDateObj = new Date(config.birthDate);
        const dateFormatter = new Intl.DateTimeFormat('en-US', {{ year: 'numeric', month: 'long', day: 'numeric' }});
        document.getElementById('birth-date-val').textContent = dateFormatter.format(birthDateObj);
        
        // Calculate age
        const today = new Date();
        let ageYears = today.getFullYear() - birthDateObj.getFullYear();
        let ageMonths = today.getMonth() - birthDateObj.getMonth();
        if (ageMonths < 0 || (ageMonths === 0 && today.getDate() < birthDateObj.getDate())) {{
            ageYears--;
            ageMonths = (ageMonths + 12) % 12;
        }}
        document.getElementById('age-val').textContent = `${{ageYears}} yrs, ${{ageMonths}} mos`;
        
        // Populate stats
        document.getElementById('weeks-val').textContent = `${{config.weeksLived}} / ${{config.totalWeeks}}`;
        const pctLived = ((config.weeksLived / config.totalWeeks) * 100).toFixed(2);
        document.getElementById('pct-lived-val').textContent = `${{pctLived}}% Lived`;
        
        const remainingWeeks = config.totalWeeks - config.weeksLived;
        document.getElementById('weeks-remaining-val').textContent = `${{remainingWeeks}} weeks remaining`;
        
        // Fill progress bar with delay for animation
        setTimeout(() => {{
            document.getElementById('progress-fill').style.width = `${{pctLived}}%`;
        }}, 100);

        // Generate Grid
        const grid = document.getElementById('grid');
        const tooltip = document.getElementById('tooltip');
        const ttWeek = document.getElementById('tt-week');
        const ttStatus = document.getElementById('tt-status');
        const ttAge = document.getElementById('tt-age');
        const ttDates = document.getElementById('tt-dates');
        
        for (let i = 0; i < config.totalWeeks; i++) {{
            const dot = document.createElement('div');
            dot.className = 'dot';
            const isLived = i < config.weeksLived;
            dot.style.backgroundColor = isLived ? config.theme.lived : config.theme.remaining;
            dot.classList.add(isLived ? 'lived' : 'remaining');
            
            // Precompute week metadata
            const startWeekDate = new Date(birthDateObj);
            startWeekDate.setDate(startWeekDate.getDate() + (i * 7));
            const endWeekDate = new Date(startWeekDate);
            endWeekDate.setDate(endWeekDate.getDate() + 6);
            
            // Format dates
            const opt = {{ month: 'short', day: 'numeric', year: 'numeric' }};
            const dateRangeStr = `${{startWeekDate.toLocaleDateString('en-US', opt)}} - ${{endWeekDate.toLocaleDateString('en-US', opt)}}`;
            
            // Compute exact age at this week
            const diffMs = startWeekDate - birthDateObj;
            const diffDays = Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
            const wAgeYears = Math.floor(diffDays / 365.25);
            const wAgeWeeks = Math.floor((diffDays % 365.25) / 7);
            const ageStr = `${{wAgeYears}} yr${{wAgeYears !== 1 ? 's' : ''}}, ${{wAgeWeeks}} wk${{wAgeWeeks !== 1 ? 's' : ''}}`;
            
            // Hover events
            dot.addEventListener('mouseenter', (e) => {{
                ttWeek.textContent = `Week ${{i + 1}}`;
                ttStatus.textContent = isLived ? 'Lived' : 'Remaining';
                ttStatus.className = `tooltip-status ${{isLived ? 'lived' : 'remaining'}}`;
                ttAge.textContent = ageStr;
                ttDates.textContent = dateRangeStr;
                
                tooltip.style.opacity = '1';
            }});
            
            dot.addEventListener('mousemove', (e) => {{
                // Position tooltip above the cursor
                const mouseX = e.pageX;
                const mouseY = e.pageY;
                
                tooltip.style.left = `${{mouseX}}px`;
                tooltip.style.top = `${{mouseY}}px`;
            }});
            
            dot.addEventListener('mouseleave', () => {{
                tooltip.style.opacity = '0';
            }});
            
            grid.appendChild(dot);
        }}
    </script>
</body>
</html>"""
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Successfully generated and saved interactive dashboard to: {html_path}")
        
        if args.open:
            import webbrowser
            url = f"file:///{os.path.abspath(html_path).replace(os.sep, '/')}"
            print(f"Opening interactive dashboard in default browser: {url}")
            webbrowser.open(url)
    except Exception as e:
        print(f"Error saving/opening interactive HTML dashboard: {e}")
        
    # 8. Set Wallpaper
    success = set_wallpaper(wallpaper_path)
    if not success:
        sys.exit(1)

    # 9. Start / Restart desktop hover overlay helper
    overlay_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "desktop_overlay.py")
    if os.path.exists(overlay_script):
        pid_path = os.path.join(wallpaper_dir, "overlay.pid")
        if os.path.exists(pid_path):
            try:
                with open(pid_path, "r") as f:
                    old_pid = int(f.read().strip())
                import signal
                os.kill(old_pid, signal.SIGTERM)
                print(f"Terminated existing overlay process with PID: {old_pid}")
                import time
                time.sleep(0.1)
            except Exception:
                pass
                
        try:
            import subprocess
            pythonw = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(pythonw):
                pythonw = sys.executable
            
            # Start background overlay process silently
            subprocess.Popen([pythonw, overlay_script], close_fds=True, creationflags=0x08000000)
            print("Successfully launched desktop hover overlay helper!")
        except Exception as e:
            print(f"Warning: Could not launch desktop overlay helper: {e}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Fatal error during execution: {e}")
        sys.exit(1)
