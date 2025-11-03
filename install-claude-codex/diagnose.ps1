<# =====================================================================
 Diagnostic Script for Claude Code & Codex CLI Installation
 
 PURPOSE:
   Quickly diagnose installation issues and check system configuration
   
 USAGE:
   pwsh -File .\diagnose.ps1
===================================================================== #>

$ErrorActionPreference = 'Continue'
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Claude Code & Codex CLI Diagnostics" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Helper function
function Test-Tool {
    param(
        [string]$Name,
        [string]$Command,
        [string]$ExpectedPath = $null
    )
    
    Write-Host "[$Name]" -ForegroundColor Yellow
    
    # Check command availability
    $cmd = Get-Command $Command -ErrorAction SilentlyContinue
    if ($cmd) {
        Write-Host "  ✓ Command found: $($cmd.Path)" -ForegroundColor Green
        try {
            $version = & $Command --version 2>&1
            Write-Host "  ✓ Version: $version" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠ Could not get version" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ✗ Command '$Command' not found in PATH" -ForegroundColor Red
    }
    
    # Check expected path if provided
    if ($ExpectedPath) {
        if (Test-Path $ExpectedPath) {
            Write-Host "  ✓ File exists: $ExpectedPath" -ForegroundColor Green
        } else {
            Write-Host "  ✗ File not found: $ExpectedPath" -ForegroundColor Red
        }
    }
    Write-Host ""
}

# System Information
Write-Host "[System Information]" -ForegroundColor Yellow
Write-Host "  OS: $([System.Environment]::OSVersion.VersionString)" -ForegroundColor Gray
Write-Host "  PowerShell: $($PSVersionTable.PSVersion)" -ForegroundColor Gray
Write-Host "  User: $env:USERNAME" -ForegroundColor Gray
Write-Host "  Computer: $env:COMPUTERNAME" -ForegroundColor Gray

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host "  Administrator: $(if($isAdmin){'Yes'}else{'No'})" -ForegroundColor $(if($isAdmin){'Green'}else{'Yellow'})
Write-Host ""

# Check InvokeBuild
Write-Host "[InvokeBuild Module]" -ForegroundColor Yellow
$ib = Get-Module -ListAvailable -Name InvokeBuild
if ($ib) {
    Write-Host "  ✓ Installed: Version $($ib.Version)" -ForegroundColor Green
} else {
    Write-Host "  ✗ Not installed" -ForegroundColor Red
    Write-Host "  → Install with: Install-Module InvokeBuild -Scope CurrentUser" -ForegroundColor Yellow
}
Write-Host ""

# Check winget
Write-Host "[Windows Package Manager (winget)]" -ForegroundColor Yellow
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
    Write-Host "  ✓ Available: $($winget.Path)" -ForegroundColor Green
    try {
        $wingetVer = winget --version 2>&1
        Write-Host "  ✓ Version: $wingetVer" -ForegroundColor Green
    } catch { }
} else {
    Write-Host "  ✗ Not found" -ForegroundColor Red
    Write-Host "  → Install 'App Installer' from Microsoft Store" -ForegroundColor Yellow
}
Write-Host ""

# Check environment variables
Write-Host "[Environment Variables]" -ForegroundColor Yellow
$gitBashEnv = $env:CLAUDE_CODE_GIT_BASH_PATH
if ($gitBashEnv) {
    Write-Host "  ✓ CLAUDE_CODE_GIT_BASH_PATH = $gitBashEnv" -ForegroundColor Green
    if (Test-Path $gitBashEnv) {
        Write-Host "    ✓ File exists" -ForegroundColor Green
    } else {
        Write-Host "    ✗ File does not exist!" -ForegroundColor Red
    }
} else {
    Write-Host "  ✗ CLAUDE_CODE_GIT_BASH_PATH not set" -ForegroundColor Red
}
Write-Host ""

# Check PATH
Write-Host "[PATH Contents (filtered)]" -ForegroundColor Yellow
$pathEntries = $env:PATH -split ';' | Where-Object { 
    $_ -match 'Claude|Node|npm|Git' 
} | Select-Object -Unique

if ($pathEntries) {
    foreach ($entry in $pathEntries) {
        $exists = Test-Path $entry -ErrorAction SilentlyContinue
        $symbol = if ($exists) { '✓' } else { '✗' }
        $color = if ($exists) { 'Green' } else { 'Red' }
        Write-Host "  $symbol $entry" -ForegroundColor $color
    }
} else {
    Write-Host "  ⚠ No relevant paths found" -ForegroundColor Yellow
}
Write-Host ""

# Check installation markers
Write-Host "[Installation State]" -ForegroundColor Yellow
$stateDir = Join-Path $PSScriptRoot '.state'
if (Test-Path $stateDir) {
    Write-Host "  State directory: $stateDir" -ForegroundColor Gray
    $markers = Get-ChildItem $stateDir -Filter *.ok -ErrorAction SilentlyContinue
    if ($markers) {
        foreach ($marker in $markers) {
            Write-Host "  ✓ $($marker.Name) (completed)" -ForegroundColor Green
        }
    } else {
        Write-Host "  ⚠ No completion markers found" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠ State directory not found (script not run yet)" -ForegroundColor Yellow
}
Write-Host ""

# Test individual tools
Test-Tool -Name "Git" -Command "git" -ExpectedPath "C:\Program Files\Git\cmd\git.exe"
Test-Tool -Name "Git Bash" -Command "bash" -ExpectedPath "$env:ProgramFiles\Git\bin\bash.exe"
Test-Tool -Name "Node.js" -Command "node"
Test-Tool -Name "npm" -Command "npm"
Test-Tool -Name "Claude Code" -Command "claude" -ExpectedPath "$env:LOCALAPPDATA\Claude\claude.exe"
Test-Tool -Name "Codex" -Command "codex"

# Check common Claude locations
Write-Host "[Claude Code Installation Locations]" -ForegroundColor Yellow
$claudeLocations = @(
    "$env:LOCALAPPDATA\Claude\claude.exe",
    "$env:USERPROFILE\.claude\claude.exe",
    "$env:APPDATA\Claude\claude.exe",
    "$env:ProgramFiles\Claude\claude.exe"
)

$found = $false
foreach ($loc in $claudeLocations) {
    if (Test-Path $loc) {
        Write-Host "  ✓ Found: $loc" -ForegroundColor Green
        $found = $true
    }
}

if (-not $found) {
    Write-Host "  ✗ Claude executable not found in any standard location" -ForegroundColor Red
    Write-Host "  → Check if installation completed successfully" -ForegroundColor Yellow
}
Write-Host ""

# Final recommendations
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Recommendations" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$issues = @()

if (-not $ib) {
    $issues += "Install InvokeBuild: Install-Module InvokeBuild -Scope CurrentUser"
}

if (-not $winget) {
    $issues += "Install winget (App Installer) from Microsoft Store"
}

if (-not $gitBashEnv) {
    $issues += "Run the installer to set up CLAUDE_CODE_GIT_BASH_PATH"
}

if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    $issues += "Claude Code not in PATH - may need to open a NEW terminal window"
}

if ($issues.Count -eq 0) {
    Write-Host "✓ All checks passed! Your system looks good." -ForegroundColor Green
} else {
    Write-Host "Issues found:" -ForegroundColor Yellow
    foreach ($issue in $issues) {
        Write-Host "  • $issue" -ForegroundColor Yellow
    }
}

Write-Host "`nRun installer with: pwsh -File .\install-claude-codex.ps1 Install`n" -ForegroundColor Cyan
