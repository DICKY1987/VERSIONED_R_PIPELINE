<#
.SYNOPSIS
    Validate ACMS plugin scaffolds ensuring contract compliance.
.DESCRIPTION
    Windows-friendly wrapper around the Python validator that verifies plugin
    directories include the required artifacts and that generated metadata is
    consistent with the authoritative plugin.spec.json file.
.PARAMETER Path
    Path to the plugin directory that should be validated.
.EXAMPLE
    ./core/Validate-Plugin.ps1 -Path plugins/example
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $Path
)

$script = Join-Path $PSScriptRoot '..' 'scripts' 'validate_plugin.py'
if (-not (Test-Path $script)) {
    throw "Unable to locate validate_plugin.py at $script"
}

& python $script --path $Path
if ($LASTEXITCODE -ne 0) {
    throw "Plugin validation failed with exit code $LASTEXITCODE"
}
