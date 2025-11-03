# Claude Code & Codex CLI Installer

A robust PowerShell build script using Invoke-Build to install Claude Code CLI and Codex CLI with all prerequisites.

## 🎯 What This Installs

1. **Git Bash** (required for Claude Code on Windows)
2. **Node.js LTS** (required for Codex)
3. **Claude Code CLI** - Anthropic's command-line AI coding assistant
4. **Codex CLI** - OpenAI's code generation tool

## 📋 Prerequisites

- **Windows 10/11**
- **PowerShell 7+** ([Download here](https://github.com/PowerShell/PowerShell/releases))
- **Administrator privileges** (for winget installations)
- **App Installer** (winget) from Microsoft Store

## 🚀 Quick Start

### Step 1: Install InvokeBuild Module

Open PowerShell 7 as Administrator and run:

```powershell
Install-Module InvokeBuild -Scope CurrentUser
```

### Step 2: Run the Installer

```powershell
# Install everything (recommended)
pwsh -NoLogo -ExecutionPolicy Bypass -File .\install-claude-codex.ps1 Install
```

### Step 3: Test Installation

**IMPORTANT:** Close PowerShell completely and open a **NEW** terminal window, then:

```powershell
# Test Claude Code
claude --version

# Test Codex
codex --version

# Check environment variable
echo $env:CLAUDE_CODE_GIT_BASH_PATH
```

## 📖 Advanced Usage

### Install Only Claude Code

```powershell
pwsh -File .\install-claude-codex.ps1 Claude
```

### Install Only Codex

```powershell
pwsh -File .\install-claude-codex.ps1 Codex
```

### Verify Existing Installation

```powershell
pwsh -File .\install-claude-codex.ps1 Verify
```

### Re-run Specific Tasks

```powershell
# Re-install Git Bash
pwsh -File .\install-claude-codex.ps1 GitBash

# Re-install Node.js
pwsh -File .\install-claude-codex.ps1 Node
```

## 🏗️ How It Works

This script uses **Invoke-Build** patterns for:

- ✅ **Incremental installs** - Skips completed steps (uses `.state/` directory)
- ✅ **Strict error handling** - Fails fast on errors
- ✅ **Dependency tracking** - Ensures prerequisites install first
- ✅ **Idempotent** - Safe to run multiple times
- ✅ **Deterministic** - Same inputs = same outputs

### Task Dependency Tree

```
Install
├── Init (checks prerequisites)
├── GitBash (installs Git for Windows)
│   └── Sets CLAUDE_CODE_GIT_BASH_PATH
├── Node (installs Node.js LTS)
├── Claude (installs Claude Code CLI)
│   └── Requires: GitBash
└── Codex (installs Codex CLI)
    └── Requires: Node
```

## 🔍 Troubleshooting

### Claude Command Not Found

**Problem:** After installation, `claude --version` says command not found.

**Solutions:**

1. **Close and reopen your terminal completely** (this is the most common fix)
2. Check if Claude was installed:
   ```powershell
   Test-Path "$env:LOCALAPPDATA\Claude\claude.exe"
   ```
3. Manually add to PATH if needed:
   ```powershell
   $env:PATH += ";$env:LOCALAPPDATA\Claude"
   ```

### Git Bash Not Found

**Problem:** Script says "Unable to locate Git Bash"

**Solutions:**

1. Install Git manually: https://git-scm.com/download/win
2. Verify installation:
   ```powershell
   Get-Command git.exe
   Test-Path "C:\Program Files\Git\bin\bash.exe"
   ```

### Codex Installation Fails

**Problem:** npm install fails or Codex is experimental

**Solution:** Codex is known to have issues on Windows. Use WSL instead:

```bash
# In WSL (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs
npm install -g @openai/codex
```

### Need Administrator Rights

**Problem:** "This script must run as Administrator"

**Solution:**

1. Right-click PowerShell 7
2. Select "Run as Administrator"
3. Re-run the script

### winget Not Found

**Problem:** "winget not found"

**Solution:**

1. Open Microsoft Store
2. Search for "App Installer"
3. Install/Update it
4. Restart terminal

### Installer Hangs

**Problem:** Claude Code installer opens but hangs

**Solutions:**

1. Close any Overwolf processes from system tray
2. Disable antivirus temporarily
3. Check `%TEMP%\claude_install_*.cmd` logs

## 🧹 Cleanup

### Remove Marker Files (Force Reinstall)

```powershell
Remove-Item .\.state\* -Force
```

### Uninstall Everything

```powershell
# Uninstall Claude Code (manual)
# Check: $env:LOCALAPPDATA\Claude

# Uninstall Codex
npm uninstall -g @openai/codex

# Uninstall Node.js
winget uninstall OpenJS.NodeJS.LTS

# Uninstall Git
winget uninstall Git.Git
```

## 📁 Project Structure

```
.
├── install-claude-codex.ps1   # Main installation script
├── README.md                   # This file
└── .state/                     # Marker files (auto-created)
    ├── git-bash.ok
    ├── node-lts.ok
    ├── claude-code.ok
    └── codex-cli.ok
```

## 🔐 Environment Variables Set

- `CLAUDE_CODE_GIT_BASH_PATH` - Points to `bash.exe` (User scope)

## 🛠️ Requirements Installed

| Tool | Purpose | Installed Via |
|------|---------|---------------|
| Git Bash | Shell environment for Claude Code | winget (Git.Git) |
| Node.js LTS | Runtime for Codex | winget (OpenJS.NodeJS.LTS) |
| Claude Code | AI coding assistant CLI | claude.ai/install.cmd |
| Codex | Code generation tool | npm (@openai/codex) |

## ⚙️ Configuration Options

You can customize by editing the script:

```powershell
# Skip verification step
pwsh -File .\install-claude-codex.ps1 Install -SkipVerify
```

## 📚 Learn More

- [Claude Code Documentation](https://docs.claude.com/en/docs/claude-code)
- [Invoke-Build on GitHub](https://github.com/nightroman/Invoke-Build)
- [Git for Windows](https://git-scm.com/download/win)
- [Node.js Official Site](https://nodejs.org/)

## 🐛 Reporting Issues

If you encounter problems:

1. Check the `.state/` directory for which steps completed
2. Review error messages carefully
3. Try running individual tasks: `pwsh -File .\install-claude-codex.ps1 <TaskName>`
4. Check Windows Event Viewer for installer logs

## 📝 License

This script is provided as-is for convenience. Individual tools have their own licenses.

---

**Created:** November 2, 2025  
**PowerShell Version Required:** 7+  
**Platform:** Windows 10/11
