<#
.SYNOPSIS
    ACMS Plugin Validator.
.VERSION
    1.0.0
.DATE
    2025-11-02
.OWNER
    Platform.Engineering
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [string]$Contract = "./core/OPERATING_CONTRACT.md"
)

$ErrorActionPreference = 'Stop'
$requiredFiles = @(
    'plugin.spec.json',
    'manifest.json',
    'policy_snapshot.json',
    'ledger_contract.json',
    'handler.py',
    'README_PLUGIN.md',
    'healthcheck.md'
)
$dangPatterns = @(
    '^\s*import\s+subprocess',
    'os\.system\(',
    'Popen\(',
    '^\s*import\s+requests',
    '^\s*import\s+urllib',
    '^\s*import\s+http\.',
    '^\s*import\s+socket',
    'curl\s',
    'wget\s',
    'git\s'
)

function Resolve-YamlBlock {
    param(
        [string]$Content,
        [string]$Pattern,
        [string]$Key
    )
    $match = [regex]::Match($Content, $Pattern, [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if (-not $match.Success) {
        throw "Cannot locate YAML block '$Key' in contract"
    }
    $yaml = "$Key:$($match.Groups[1].Value)"
    return ConvertFrom-Yaml -Yaml $yaml
}

function Read-Json([string]$FilePath) {
    return Get-Content -Raw -Path $FilePath | ConvertFrom-Json -AsHashtable
}

function Assert-SemVer([string]$Value) {
    if ($Value -notmatch '^\d+\.\d+\.\d+$') {
        throw "Value '$Value' is not valid SemVer (X.Y.Z)"
    }
}

function Assert-Kebab([string]$Value) {
    if ($Value -notmatch '^[a-z0-9-]+$') {
        throw "Value '$Value' must be kebab-case [a-z0-9-]+"
    }
}

$pluginDir = Resolve-Path -Path $Path
foreach ($req in $requiredFiles) {
    $candidate = Join-Path -Path $pluginDir -ChildPath $req
    if (-not (Test-Path -Path $candidate)) {
        throw "Missing file '$req' in plugin directory"
    }
}

$specPath = Join-Path -Path $pluginDir -ChildPath 'plugin.spec.json'
$manifestPath = Join-Path -Path $pluginDir -ChildPath 'manifest.json'
$handlerPath = Join-Path -Path $pluginDir -ChildPath 'handler.py'

$spec = Read-Json -FilePath $specPath
$manifest = Read-Json -FilePath $manifestPath
foreach ($key in @('name', 'version', 'handles_event')) {
    if (-not $spec.ContainsKey($key)) {
        throw "Spec missing required field: $key"
    }
    if (-not $manifest.ContainsKey($key)) {
        throw "Manifest missing required field: $key"
    }
}

Assert-Kebab -Value $spec['name']
Assert-SemVer -Value $spec['version']
if ($spec['name'] -ne $manifest['name']) {
    throw "Spec/manifest name mismatch: $($spec['name']) vs $($manifest['name'])"
}
if ($spec['version'] -ne $manifest['version']) {
    throw "Spec/manifest version mismatch: $($spec['version']) vs $($manifest['version'])"
}
if ($spec['handles_event'] -ne $manifest['handles_event']) {
    throw "Spec/manifest handles_event mismatch: $($spec['handles_event']) vs $($manifest['handles_event'])"
}

if (-not (Test-Path -Path $Contract)) {
    throw "Contract file not found: $Contract"
}
$contractContent = Get-Content -Raw -Path $Contract
$events = Resolve-YamlBlock -Content $contractContent -Pattern '```yaml\s*lifecycle_events:(.*?)```' -Key 'lifecycle_events'
$actions = Resolve-YamlBlock -Content $contractContent -Pattern '```yaml\s*allowed_actions_contract:(.*?)```' -Key 'allowed_actions_contract'
$allowedEvents = @()
foreach ($evt in $events.lifecycle_events) {
    $allowedEvents += $evt.name
}
if ($allowedEvents -notcontains $spec['handles_event']) {
    throw "handles_event '$($spec['handles_event'])' not allowed by contract"
}
$allowedActionNames = $actions.PSObject.Properties.Name

$handlerSource = Get-Content -Raw -Path $handlerPath
if ($handlerSource -notmatch 'BEGIN AUTO SECTION') {
    throw "handler.py missing BEGIN AUTO SECTION marker"
}
if ($handlerSource -notmatch 'END AUTO SECTION') {
    throw "handler.py missing END AUTO SECTION marker"
}
foreach ($pattern in $dangPatterns) {
    if ($handlerSource -match $pattern) {
        throw "Forbidden pattern found in handler.py: $pattern"
    }
}

$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    Write-Warning 'Python interpreter not found; skipping execution smoke test.'
} else {
    $tempFile = [System.IO.Path]::GetTempFileName()
    $script = @"
import importlib.util
import json
import sys
from pathlib import Path

handler_path = Path(r"$handlerPath")
spec_path = Path(r"$specPath")
spec = json.loads(spec_path.read_text())
module_spec = importlib.util.spec_from_file_location("acms_plugin_runtime", handler_path)
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)
if not hasattr(module, "handle"):
    raise SystemExit("missing handle()")

event = {
    "name": spec["handles_event"],
    "inputs": {"path": "__test__", "size": 1, "sha256": "deadbeef", "mime": "text/plain"}
}
result = module.handle(event)
if result is None:
    result = []
if not isinstance(result, list):
    raise SystemExit("handle() must return a list")
for item in result:
    if not isinstance(item, dict):
        raise SystemExit("proposal items must be dicts")
json.dump(result, sys.stdout)
"@
    Set-Content -Path $tempFile -Value $script -Encoding utf8
    try {
        $output = & $python.Path $tempFile 2>&1
        $exitCode = $LASTEXITCODE
    }
    finally {
        Remove-Item -Path $tempFile -Force -ErrorAction SilentlyContinue
    }
    if ($exitCode -ne 0) {
        throw "Handler execution failed: $($output -join ' ')"
    }
    $joined = $output -join [Environment]::NewLine
    if ([string]::IsNullOrWhiteSpace($joined)) {
        $proposals = @()
    } else {
        $proposals = $joined | ConvertFrom-Json
    }
    foreach ($proposal in $proposals) {
        if (-not $proposal.ContainsKey('action')) {
            throw "Proposal missing 'action' field"
        }
        if ($allowedActionNames -notcontains $proposal.action) {
            throw "Proposal contains disallowed action: $($proposal.action)"
        }
        if (-not $proposal.ContainsKey('payload') -or -not ($proposal.payload -is [Collections.IDictionary])) {
            throw "Proposal payload must be an object"
        }
    }
}

Write-Host "Validation passed for plugin at '$pluginDir'"
