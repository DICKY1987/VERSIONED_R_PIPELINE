# Quick Start Guide - Claude Code & Codex CLI Installer

## 🚀 Installation in 3 Steps

### Step 1: Install InvokeBuild
Open PowerShell 7 **as Administrator**:
```powershell
Install-Module InvokeBuild -Scope CurrentUser
```

### Step 2: Run the Installer
```powershell
pwsh -ExecutionPolicy Bypass -File .\install-claude-codex.ps1 Install
```

Wait for installation to complete (2-5 minutes).

### Step 3: Test in a NEW Terminal
**Close PowerShell completely**, then open a new one:
```powershell
claude --version
codex --version
```

## ✅ Success Indicators

You should see:
```
claude --version
> claude version X.X.X

codex --version  
> @openai/codex vX.X.X
```

## ❌ Common Issues & Quick Fixes

### "claude: command not found"
**Fix:** Did you open a **NEW** terminal? Old terminals don't see new PATH entries.

### "Must run as Administrator"
**Fix:** Right-click PowerShell → "Run as Administrator"

### "winget not found"
**Fix:** Install "App Installer" from Microsoft Store, then retry

### Installer hangs
**Fix:** 
1. Close Overwolf from system tray
2. Temporarily disable antivirus
3. Retry installation

## 🔍 Need Help?

Run the diagnostic script:
```powershell
pwsh -File .\diagnose.ps1
```

Read full README.md for detailed troubleshooting.

## 📚 What Got Installed?

- ✅ Git Bash (for Claude Code)
- ✅ Node.js + npm (for Codex)
- ✅ Claude Code CLI
- ✅ Codex CLI

## 🎯 Next Steps

Try Claude Code:
```powershell
claude --help
claude auth login
```

Try Codex:
```powershell
codex --help
```

---
**Remember:** Always use a **NEW** terminal after installation!
