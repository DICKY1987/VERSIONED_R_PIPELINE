# install-claude-codex.ps1
# Purpose:
#   - Ensure prerequisites for Claude Code CLI and Codex CLI on Windows
#   - Uses Invoke-Build task model with resumable state markers
#   - Safe to re-run (idempotent-ish)
#
# Requirements to run:
#   - PowerShell 7+ (pwsh)
#   - Elevated session (Run as Administrator)
#   - InvokeBuild module installed: Install-Module InvokeBuild -Scope CurrentUser
#
# Usage:
#   Invoke-Build Install .\install-claude-codex.ps1
#
# After success:
#   Open a NEW non-admin PowerShell 7 window and run:
#       claude --version
#       codex --version

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# --- state directory -------------------------------------------------
$StateDir = Join-Path $PSScriptRoot ".state"
if (-not (Test-Path $StateDir)) {
    New-Item -ItemType Directory -Path $StateDir | Out-Null
}

function MarkerPath {
    param([string]$Name)
    return (Join-Path $StateDir $Name)
}

function New-StateMarker {
    param([string]$Name)
    New-Item -ItemType File -Force (MarkerPath $Name) | Out-Null
}

# --- helpers ---------------------------------------------------------

function Require-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal] `
        [Security.Principal.WindowsIdentity]::GetCurrent() `
    ).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)

    if (-not $isAdmin) {
        throw "This must be run in PowerShell 7 as Administrator."
    }
}

function Add-UserPathIfMissing {
    param([string]$Dir)

    if (-not (Test-Path $Dir)) { return }

    $userPath = [Environment]::GetEnvironmentVariable('Path','User')
    $parts    = $userPath -split ';' | Where-Object { $_ -ne '' }

    if ($parts -notcontains $Dir) {
        Write-Host "   -> Adding $Dir to User PATH"
        $newPath = ($parts + $Dir) -join ';'
        [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    } else {
        Write-Host "   -> $Dir already on PATH (user scope)"
    }
}

function Get-GitBashPath {
    $candidates = @(
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files\Git\usr\bin\bash.exe",
        "C:\Program Files (x86)\Git\bin\bash.exe",
        "C:\Program Files (x86)\Git\usr\bin\bash.exe"
    )

    foreach ($c in $candidates) {
        if (Test-Path $c) {
            return $c
        }
    }

    # try to infer from git.exe
    $gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($gitCmd) {
        $gitDir  = Split-Path $gitCmd.Path -Parent
        $parent  = Split-Path $gitDir -Parent
        $possible = Join-Path $parent "bin\bash.exe"
        if (Test-Path $possible) {
            return $possible
        }
    }

    return $null
}

function Ensure-GitBash {
    # returns bash.exe path
    $bash = Get-GitBashPath
    if (-not $bash) {
        Write-Host "   -> Git Bash not found. Installing Git via winget..."
        # silent install of Git for Windows
        winget install --id Git.Git -e --source winget --silent
        Start-Sleep -Seconds 3
        $bash = Get-GitBashPath
        if (-not $bash) {
            throw "Git Bash still not found after winget install."
        }
    } else {
        Write-Host "   -> Git Bash already present: $bash"
    }

    # persist env var needed by Claude installer
    [Environment]::SetEnvironmentVariable(
        'CLAUDE_CODE_GIT_BASH_PATH',
        $bash,
        'User'
    )
    # also expose it in *this* session
    $env:CLAUDE_CODE_GIT_BASH_PATH = $bash

    return $bash
}

function Ensure-NodeLTS {
    # ensures Node.js LTS is installed and on PATH
    $nodeCmd = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($nodeCmd) {
        Write-Host "   -> Node already installed at $($nodeCmd.Path)"
        return
    }

    Write-Host "   -> Installing Node.js LTS via winget..."
    winget install --id OpenJS.NodeJS.LTS -e --source winget --silent
    Start-Sleep -Seconds 3

    $nodeCmd = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $nodeCmd) {
        throw "Node.js LTS did not install (node.exe still not found)."
    }

    Write-Host "   -> Node installed at $($nodeCmd.Path)"
}

function Get-ClaudeCandidatePaths {
    @(
        (Join-Path $env:USERPROFILE    ".local\bin\claude.exe"),
        (Join-Path $env:LOCALAPPDATA   "Claude\claude.exe"),
        (Join-Path $env:ProgramFiles   "Claude\claude.exe")
    )
}

function Find-Claude {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Path }

    foreach ($p in Get-ClaudeCandidatePaths) {
        if (Test-Path $p) { return $p }
    }

    return $null
}

function Install-ClaudeCodeCLI {
    param(
        [string]$GitBashPath
    )

    if (-not (Test-Path $GitBashPath)) {
        throw "Git Bash path '$GitBashPath' not found. Cannot continue Claude install."
    }

    # The Claude Code Windows bootstrapper expects CLAUDE_CODE_GIT_BASH_PATH
    $env:CLAUDE_CODE_GIT_BASH_PATH = $GitBashPath

    $tempInstaller = Join-Path $env:TEMP "claude_install.cmd"
    Write-Host "   -> Downloading Claude Code installer..."
    Invoke-WebRequest -UseBasicParsing -Uri "https://claude.ai/install.cmd" -OutFile $tempInstaller

    Write-Host "   -> Running Claude Code installer..."
    & cmd.exe /c $tempInstaller
}

function Ensure-ClaudeCode {
    # returns path to claude.exe if found
    $existing = Find-Claude
    if ($existing) {
        Write-Host "   -> Claude Code already present at $existing"
        Add-UserPathIfMissing (Split-Path $existing -Parent)
        return $existing
    }

    # no existing install, try to install
    $gitBashPath = $env:CLAUDE_CODE_GIT_BASH_PATH
    if (-not $gitBashPath -or -not (Test-Path $gitBashPath)) {
        $gitBashPath = Get-GitBashPath
    }
    if (-not $gitBashPath) {
        throw "Cannot install Claude Code CLI: Git Bash was not located."
    }

    Install-ClaudeCodeCLI -GitBashPath $gitBashPath
    Start-Sleep -Seconds 2

    $installed = Find-Claude
    if ($installed) {
        Write-Host "   -> Claude Code now appears at $installed"
        Add-UserPathIfMissing (Split-Path $installed -Parent)
        return $installed
    }

    Write-Warning @"
Claude installer ran, but claude.exe is still not detectable in this session.
This is sometimes just PATH refresh delay.
Try:
  1. Close this PowerShell window
  2. Open a NEW PowerShell 7 window (non-admin)
  3. Run: claude --version
If that prints a version, Claude Code CLI is installed successfully.
"@

    return $null
}

function Show-Version {
    param([string]$CmdName)

    $cmd = Get-Command $CmdName -ErrorAction SilentlyContinue
    if (-not $cmd) {
        return @{
            found   = $false
            path    = $null
            version = $null
        }
    }

    $verOut = & $cmd.Path --version 2>$null
    if (-not $verOut) { $verOut = "(no version output)" }

    return @{
        found   = $true
        path    = $cmd.Path
        version = $verOut
    }
}

function Show-Summary {
    $claudeInfo = Show-Version "claude"
    $codexInfo  = Show-Version "codex"

    Write-Host ""
    Write-Host "==========================================="
    Write-Host " Install Verification Summary"
    Write-Host "==========================================="

    if ($claudeInfo.found) {
        Write-Host "Claude Code CLI : OK" -ForegroundColor Green
        Write-Host "    Path    : $($claudeInfo.path)"
        Write-Host "    Version : $($claudeInfo.version)"
    } else {
        Write-Host "Claude Code CLI : NOT FOUND in this session" -ForegroundColor Yellow
    }

    if ($codexInfo.found) {
        Write-Host "Codex CLI       : OK" -ForegroundColor Green
        Write-Host "    Path    : $($codexInfo.path)"
        Write-Host "    Version : $($codexInfo.version)"
    } else {
        Write-Host "Codex CLI       : NOT FOUND in this session" -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "If Claude is 'NOT FOUND':"
    Write-Host "  Close this window, open a NEW PowerShell 7 window (non-admin), run: claude --version"
    Write-Host ""
}

# --- Invoke-Build tasks ------------------------------------------------
# Syntax pattern:
#   task <TaskName> [Dependencies] [-Inputs {...}] [-Outputs {...}] { scriptblock }

task Init {
    Write-Host "`n[STEP 0] Init / Preconditions" -ForegroundColor Cyan
    Require-Admin

    if (-not (Test-Path $StateDir)) {
        New-Item -ItemType Directory -Path $StateDir | Out-Null
    }

    New-StateMarker 'init.ok'
}

task GitBash Init -Outputs { MarkerPath 'git-bash.ok' } {
    Write-Host "`n[STEP 1/4] Git Bash / Environment Prep" -ForegroundColor Cyan
    Write-Host "---------------------------------------" -ForegroundColor Cyan

    $bashPath = Ensure-GitBash
    Write-Host "   -> Using Git Bash: $bashPath"

    New-StateMarker 'git-bash.ok'
}

task Node Init -Outputs { MarkerPath 'node-lts.ok' } {
    Write-Host "`n[STEP 2/4] Node.js LTS" -ForegroundColor Cyan
    Write-Host "------------------------" -ForegroundColor Cyan

    Ensure-NodeLTS
    $nodeCmd = Get-Command node.exe -ErrorAction SilentlyContinue
    if ($nodeCmd) {
        Write-Host "   -> Node OK at $($nodeCmd.Path)"
    }

    New-StateMarker 'node-lts.ok'
}

task Claude GitBash -Inputs { MarkerPath 'git-bash.ok' } -Outputs { MarkerPath 'claude-code.ok' } {
    Write-Host "`n[STEP 3/4] Claude Code CLI" -ForegroundColor Cyan
    Write-Host "--------------------------" -ForegroundColor Cyan

    $path = Ensure-ClaudeCode
    if ($path) {
        Write-Host "   -> Claude path: $path"
    } else {
        Write-Host "   -> Claude not yet visible in this session (may require new shell)" -ForegroundColor Yellow
    }

    New-StateMarker 'claude-code.ok'
}

task Codex Node -Inputs { MarkerPath 'node-lts.ok' } -Outputs { MarkerPath 'codex-cli.ok' } {
    Write-Host "`n[STEP 4/4] Codex CLI" -ForegroundColor Cyan
    Write-Host "--------------------" -ForegroundColor Cyan

    $codexCmd = Get-Command codex -ErrorAction SilentlyContinue
    if ($codexCmd) {
        Write-Host "   -> Codex CLI already installed at $($codexCmd.Path)"
    } else {
        Write-Warning "   Codex CLI auto-install is not implemented in this script yet."
        Write-Warning "   If you already have a Codex CLI installer / npm global, install it manually,"
        Write-Warning "   then open a NEW shell and run: codex --version"
    }

    New-StateMarker 'codex-cli.ok'
}

task Verify.Final Claude,Codex -Inputs { @(MarkerPath 'claude-code.ok'); @(MarkerPath 'codex-cli.ok') } {
    Write-Host "`n[VERIFY] Final tool check" -ForegroundColor Cyan
    Write-Host "-------------------------" -ForegroundColor Cyan

    Show-Summary
}

# Main entrypoint task graph
task Install Init,GitBash,Node,Claude,Codex,Verify.Final

# Default task = Install
task . Install
