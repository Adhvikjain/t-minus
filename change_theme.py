import os
import sys
import json
import subprocess

# Pre-defined Premium Color Themes
THEMES = {
    "1": {
        "name": "Minimalist Monochrome",
        "background": "#09090b",
        "lived_dot": "#a3a3a3",
        "remaining_dot": "#262626",
        "text": "#737373"
    },
    "2": {
        "name": "Tokyo Night",
        "background": "#1a1b26",
        "lived_dot": "#7aa2f7",
        "remaining_dot": "#3b4261",
        "text": "#a9b1d6"
    },
    "3": {
        "name": "Nordic Aurora",
        "background": "#2e3440",
        "lived_dot": "#d08770",
        "remaining_dot": "#4c566a",
        "text": "#d8dee9"
    },
    "4": {
        "name": "Dracula",
        "background": "#282a36",
        "lived_dot": "#ff79c6",
        "remaining_dot": "#44475a",
        "text": "#f8f8f2"
    },
    "5": {
        "name": "Forest Green",
        "background": "#0a0f0d",
        "lived_dot": "#4ade80",
        "remaining_dot": "#1b2a24",
        "text": "#a7f3d0"
    },
    "6": {
        "name": "Solarized Dark",
        "background": "#002b36",
        "lived_dot": "#2aa198",
        "remaining_dot": "#073642",
        "text": "#93a1a1"
    },
    "7": {
        "name": "Sand & Chestnut (Warm Earthy)",
        "background": "#f5efe6",
        "lived_dot": "#9c6644",
        "remaining_dot": "#d5ccbc",
        "text": "#4e3526"
    }
}

def load_config(config_path):
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading config: {e}")
        # Default fallback
        return {
            "birth_date": "2000-01-01",
            "life_expectancy_years": 80
        }

def save_config(config_path, config):
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def main():
    config_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(config_dir, "config.json")
    
    print("\n=============================================")
    print("      LIFE WALLPAPER THEME SELECTOR")
    print("=============================================\n")
    
    # 1. List Available Themes
    for key, theme in THEMES.items():
        print(f" [{key}] {theme['name']}")
        print(f"     Background: {theme['background']} | Lived: {theme['lived_dot']} | Remaining: {theme['remaining_dot']}\n")
        
    # 2. Get User Choice
    choice = input("Select a theme number (or press Enter to exit): ").strip()
    if not choice:
        print("Exiting.")
        return
        
    if choice not in THEMES:
        print(f"Error: '{choice}' is not a valid theme number.")
        return
        
    selected = THEMES[choice]
    print(f"\nApplying theme: {selected['name']}...")
    
    # 3. Update config.json
    config = load_config(config_path)
    config["theme"] = {
        "background": selected["background"],
        "lived_dot": selected["lived_dot"],
        "remaining_dot": selected["remaining_dot"],
        "text": selected["text"]
    }
    
    if save_config(config_path, config):
        print("Successfully updated config.json!")
        
        # 4. Trigger wallpaper update script
        wallpaper_script = os.path.join(config_dir, "generate_wallpaper.py")
        if os.path.exists(wallpaper_script):
            print("Regenerating wallpaper...")
            try:
                subprocess.run([sys.executable, wallpaper_script], check=True)
            except Exception as e:
                print(f"Error running generate_wallpaper.py: {e}")
        else:
            print("Error: generate_wallpaper.py not found in the same folder.")
            
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
