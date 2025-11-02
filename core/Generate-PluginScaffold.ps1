<#
.SYNOPSIS
    ACMS Plugin Scaffold Generator.
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
    [string]$Spec,

    [string]$Contract = "./core/OPERATING_CONTRACT.md"
)

$ErrorActionPreference = 'Stop'

function Resolve-ContractFrontMatter {
    param([string]$Content)
    $match = [regex]::Match($Content, '^---\s*(.*?)\s*---', [System.Text.RegularExpressions.RegexOptions]::Singleline)
    if ($match.Success) {
        return ConvertFrom-Yaml -Yaml $match.Groups[1].Value
    }
    return $null
}

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

$specPath = Resolve-Path -Path $Spec
$pluginDir = Split-Path -Parent $specPath
if (-not (Test-Path -Path $pluginDir)) {
    New-Item -ItemType Directory -Path $pluginDir | Out-Null
}

$specContent = Get-Content -Raw -Path $specPath | ConvertFrom-Json
foreach ($prop in @('name', 'version', 'handles_event')) {
    if (-not $specContent.$prop) {
        throw "Spec missing required field: $prop"
    }
}
if ($specContent.name -notmatch '^[a-z0-9-]+$') {
    throw "spec.name must be kebab-case [a-z0-9-]+"
}
if ($specContent.version -notmatch '^\d+\.\d+\.\d+$') {
    throw "spec.version must be SemVer X.Y.Z"
}

if (-not (Test-Path -Path $Contract)) {
    throw "Contract file not found: $Contract"
}
$contractContent = Get-Content -Raw -Path $Contract
$frontMatter = Resolve-ContractFrontMatter -Content $contractContent
$events = Resolve-YamlBlock -Content $contractContent -Pattern '```yaml\s*lifecycle_events:(.*?)```' -Key 'lifecycle_events'
$actions = Resolve-YamlBlock -Content $contractContent -Pattern '```yaml\s*allowed_actions_contract:(.*?)```' -Key 'allowed_actions_contract'

$allowedEvents = @()
foreach ($evt in $events.lifecycle_events) {
    $allowedEvents += $evt.name
}
if ($allowedEvents -notcontains $specContent.handles_event) {
    throw "handles_event '$($specContent.handles_event)' not allowed by contract"
}

$allowedActionNames = $actions.PSObject.Properties.Name

$generatedAt = [DateTime]::UtcNow.ToString('o')
$manifest = [ordered]@{
    name = $specContent.name
    version = $specContent.version
    handles_event = $specContent.handles_event
    generated_at = $generatedAt
}
if ($frontMatter -and $frontMatter.contract_version) {
    $manifest.contract_version = $frontMatter.contract_version
}

$policySnapshot = [ordered]@{
    policy = $null
    contract_allowed_actions = $allowedActionNames
    contract_allowed_events = $allowedEvents
}
if ($specContent.PSObject.Properties.Match('policy')) {
    $policySnapshot.policy = $specContent.policy
} else {
    $policySnapshot.policy = @{}
}

$ledgerContract = [ordered]@{
    required = @('ulid', 'ts', 'event', 'policy_version', 'inputs', 'actions', 'status')
}

$manifestPath = Join-Path -Path $pluginDir -ChildPath 'manifest.json'
$policyPath = Join-Path -Path $pluginDir -ChildPath 'policy_snapshot.json'
$ledgerPath = Join-Path -Path $pluginDir -ChildPath 'ledger_contract.json'
$handlerPath = Join-Path -Path $pluginDir -ChildPath 'handler.py'
$readmePath = Join-Path -Path $pluginDir -ChildPath 'README_PLUGIN.md'
$healthPath = Join-Path -Path $pluginDir -ChildPath 'healthcheck.md'

Set-Content -Path $manifestPath -Value (ConvertTo-Json -InputObject $manifest -Depth 8) -Encoding utf8
Set-Content -Path $policyPath -Value (ConvertTo-Json -InputObject $policySnapshot -Depth 8) -Encoding utf8
Set-Content -Path $ledgerPath -Value (ConvertTo-Json -InputObject $ledgerContract -Depth 4) -Encoding utf8

$contractVersion = if ($manifest.Contains('contract_version')) { $manifest.contract_version } else { 'unknown' }
$handlerTemplate = @'
"""
Plugin handler for {0} ({1}).
Only edit code between BEGIN/END AUTO SECTION markers.
Contract version at generation: {2}
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List

# BEGIN AUTO SECTION

def handle(event: dict) -> List[Dict[str, Any]]:
    """Return a list of proposals: {{"action": <str>, "payload": <dict>}}."""
    return []

# END AUTO SECTION
'@
$handlerContent = [string]::Format($handlerTemplate, $specContent.name, $specContent.version, $contractVersion)
Set-Content -Path $handlerPath -Value $handlerContent -Encoding utf8

$inputs = @()
if ($specContent.PSObject.Properties.Match('inputs')) {
    $inputs = $specContent.inputs
}
$outputs = @()
if ($specContent.PSObject.Properties.Match('outputs')) {
    $outputs = $specContent.outputs
}

function Join-Lines {
    param([object[]]$Items)
    if (-not $Items -or $Items.Count -eq 0) {
        return '- (none specified)'
    }
    return ($Items | ForEach-Object { "- $_" }) -join "`n"
}

$readmeTemplate = @'
# Plugin: {0}

*Handles*: `{1}`
*Version*: `{2}`

## Development
- Edit only between **BEGIN AUTO SECTION** and **END AUTO SECTION** in `handler.py`.
- Run `python scripts/validate_plugin.py --path {3}` before committing.

## Inputs
{4}
## Outputs
{5}
'@
$readmeContent = [string]::Format(
    $readmeTemplate,
    $specContent.name,
    $specContent.handles_event,
    $specContent.version,
    (Split-Path -Leaf $pluginDir),
    (Join-Lines -Items $inputs),
    (Join-Lines -Items $outputs)
)
Set-Content -Path $readmePath -Value $readmeContent -Encoding utf8

$escapedHandlerPath = $handlerPath.Replace('\', '\\')
$healthTemplate = @'
# Healthcheck for {0}

- Validate contract compatibility
- Dry-run with sample event payload

```python
from importlib import util
import json
spec = util.spec_from_file_location("{0}_handler", r"{1}")
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(json.dumps(mod.handle({{"name": "{2}", "inputs": {{"path": "README.md", "size": 12, "sha256": "deadbeef", "mime": "text/markdown"}}}}), indent=2))
```
'@
$healthContent = [string]::Format($healthTemplate, $specContent.name, $escapedHandlerPath, $specContent.handles_event)
Set-Content -Path $healthPath -Value $healthContent -Encoding utf8

Write-Host "Scaffold generated for plugin '$($specContent.name)' at '$pluginDir'"
