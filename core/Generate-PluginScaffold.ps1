<#
.SYNOPSIS
    Generate ACMS plugin scaffolding from a plugin.spec.json file.
.DESCRIPTION
    Wrapper script that invokes the Python-based scaffold generator ensuring
    a consistent interface for developers working on Windows workstations.
.PARAMETER Spec
    Path to the plugin.spec.json file that should be used as the source of
    truth for generating plugin artifacts.
.PARAMETER OutDir
    Optional path where the scaffold should be written. Defaults to the
    directory containing the specification file.
.EXAMPLE
    ./core/Generate-PluginScaffold.ps1 -Spec plugins/example/plugin.spec.json
#>
param(
    [Parameter(Mandatory = $true)]
    [string] $Spec,

    [Parameter(Mandatory = $false)]
    [string] $OutDir
)

$script = Join-Path $PSScriptRoot '..' 'scripts' 'generate_plugin_scaffold.py'
if (-not (Test-Path $script)) {
    throw "Unable to locate generate_plugin_scaffold.py at $script"
}

$arguments = @('--spec', $Spec)
if ($OutDir) {
    $arguments += @('--out', $OutDir)
}

& python $script @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Plugin scaffold generation failed with exit code $LASTEXITCODE"
}
