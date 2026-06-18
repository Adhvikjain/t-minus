# Register Life Progress Wallpaper Daily Update Task in Windows
# Run this script in a standard PowerShell console (no admin required)

# 1. Resolve pythonw.exe path
try {
    $PythonW = python -c "import sys, os; print(os.path.abspath(sys.executable.replace('python.exe', 'pythonw.exe')))"
} catch {
    Write-Error "Failed to execute Python to locate pythonw.exe. Ensure Python is in your PATH."
    exit 1
}

if (-not $PythonW -or -not (Test-Path $PythonW)) {
    Write-Error "Could not find pythonw.exe. Please check your Python installation."
    exit 1
}

# 2. Resolve script path
$ScriptPath = Join-Path (Get-Item -Path ".").FullName "generate_wallpaper.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Could not find generate_wallpaper.py at '$ScriptPath'."
    exit 1
}

$TaskName = "LifeProgressWallpaper"

# 3. Create Task Scheduler XML for Daily Update
$TempXmlPath = [System.IO.Path]::GetTempFileName()

$DateStr = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
$StartBoundaryStr = (Get-Date).ToString("yyyy-MM-dd") + "T00:05:00"

$XmlContent = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>$DateStr</Date>
    <Author>$env:COMPUTERNAME\$env:USERNAME</Author>
    <URI>\$TaskName</URI>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$StartBoundaryStr</StartBoundary>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
    </Principal>
  </Principals>
  <Settings>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$PythonW</Command>
      <Arguments>`"$ScriptPath`"</Arguments>
    </Exec>
  </Actions>
</Task>
"@

try {
    # schtasks expects UTF-16/unicode XML
    $XmlContent | Out-File -FilePath $TempXmlPath -Encoding unicode
    
    # Import the task
    $output = schtasks /create /xml "$TempXmlPath" /tn "$TaskName" /f
    Write-Host $output
} catch {
    Write-Error "Failed to register scheduled task: $_"
} finally {
    if (Test-Path $TempXmlPath) {
        Remove-Item $TempXmlPath
    }
}

# 4. Set up Logon Shortcut in user's Startup folder
try {
    $StartupDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
    $ShortcutPath = Join-Path $StartupDir "$TaskName.lnk"
    
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = $PythonW
    $Shortcut.Arguments = "`"$ScriptPath`""
    $Shortcut.WorkingDirectory = (Get-Item -Path ".").FullName
    $Shortcut.WindowStyle = 7 # Minimized/No Window (in combination with pythonw.exe)
    $Shortcut.Description = "Generates and updates the Life Progress desktop wallpaper at logon."
    $Shortcut.Save()
    
    Write-Host "Startup shortcut created successfully in Startup folder:" -ForegroundColor Green
    Write-Host "  $ShortcutPath"
} catch {
    Write-Warning "Could not create startup folder shortcut: $_"
}

Write-Host ""
Write-Host "--------------------------------------------------------" -ForegroundColor Green
Write-Host "Setup Completed Successfully!" -ForegroundColor Green
Write-Host "--------------------------------------------------------" -ForegroundColor Green
Write-Host "1. Scheduled Task: Runs daily at 12:05 AM (with missed run catchup)."
Write-Host "2. Startup Shortcut: Runs automatically whenever you log into Windows."
Write-Host ""
Write-Host "To test the script manually now, run:"
Write-Host "  python generate_wallpaper.py" -ForegroundColor Cyan
Write-Host ""
