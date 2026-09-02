$script:ThermoGarP3Role = 'SBOM'
$script:ThermoGarP3Arguments = [object[]]@($args)
$script:ThermoGarP3CommandPath = $PSCommandPath
. ([IO.Path]::Combine($PSScriptRoot, 'verify_distribution_evidence.ps1'))
exit $LASTEXITCODE