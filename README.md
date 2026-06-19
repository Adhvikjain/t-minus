# T-Minus: Life Progress Wallpaper Generator

`T-Minus` is a Python-based desktop wallpaper visualizer that renders your life progress as a beautiful grid of rounded squares (squircles) and updates it daily on Windows.

It organizes your life progress into a highly structured grid of **50 columns by 65 rows** (representing 3,250 weeks or ~62.5 years of life progress) and positions it as a clean, framed widget on the right side of your desktop, keeping the left 45% clear for your desktop icons.

---

## 🎨 Premium Theme Options

The repository includes an interactive theme switcher containing 7 premium color schemes:

*   **Sand & Chestnut (Warm Earthy)**: Cozy latte/cream background with rich chestnut brown progress indicators and sand-gray remaining dots.
*   **Minimalist Monochrome**: Slate near-black background with soft-gray progress indicators and dark charcoal remaining dots.
*   **Tokyo Night**: Slate navy background with electric cyan/blue accents.
*   **Nordic Aurora**: Deep frost-gray background with aurora peach/orange accents.
*   **Dracula**: Cozy deep-purple background with vibrant cyber-pink accents.
*   **Forest Green**: Deep forest-black background with emerald green accents.
*   **Solarized Dark**: Classic deep-teal base03 background with cyan accents.

---

## 🛠️ Project Structure

*   `generate_wallpaper.py`: Core logic for date mathematics, screen resolution detection, rendering, framing, and applying the wallpaper via Windows APIs.
*   `change_theme.py`: Interactive CLI script for shifting color themes on the fly.
*   `config.json`: Configuration file containing birth date, expectancy, and current active color settings.
*   `register_task.ps1`: Zero-admin PowerShell automation registration script.
*   `requirements.txt`: Python package dependencies.

---

## 🚀 Setup & Installation

### 1. Clone & Install Dependencies
First, clone the repository and install the dependencies (`Pillow` and `screeninfo`):
```bash
git clone https://github.com/Adhvikjain/t-minus.git
cd t-minus
pip install -r requirements.txt
```

### 2. Configure Your Metrics
Open `config.json` and set your birth date (YYYY-MM-DD) and your expected lifespan:
```json
{
  "birth_date": "2007-10-08",
  "life_expectancy_years": 75
}
```

### 3. Choose a Color Theme
Run the interactive theme selector to apply your favorite look:
```bash
python change_theme.py
```
Type in a theme number (1 to 7) and press **Enter** to update your config and refresh the background immediately.

### 4. Setup Daily Auto-Updates (Zero Admin Required)
To keep the wallpaper fresh, run the PowerShell script to schedule automated updates. This sets up a silent daily task (at 12:05 AM with missed-run catchup) and a Windows Startup folder shortcut to automatically refresh your wallpaper when you log into Windows:
```powershell
powershell -ExecutionPolicy Bypass -File .\register_task.ps1
```

---

## 💻 Manual Commands

*   **Manually Force Update**:
    ```bash
    python generate_wallpaper.py
    ```
*   **Open Interactive Progress Dashboard**:
    Generate the visualizer and open it in your default browser:
    ```bash
    python generate_wallpaper.py --open
    ```
    This generates a self-contained, beautiful, offline-capable `life_progress.html` in your `~/wallpaper_life/` directory with interactive hover tooltips that show the exact date ranges and age metrics for each week of your life.
*   **Manual Task Scheduler Test**:
    ```powershell
    schtasks /run /tn "LifeProgressWallpaper"
    ```
