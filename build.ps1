param(
    [string] $ToolchainBin,
    [string] $OutputDirectory = (Join-Path $PSScriptRoot 'payloads')
)

$ErrorActionPreference = 'Stop'

if ($ToolchainBin) {
    $gcc = Join-Path $ToolchainBin 'arm-none-eabi-gcc.exe'
    $objcopy = Join-Path $ToolchainBin 'arm-none-eabi-objcopy.exe'
} else {
    $gcc = (Get-Command arm-none-eabi-gcc -CommandType Application).Source
    $objcopy = (Get-Command arm-none-eabi-objcopy -CommandType Application).Source
}

$sourceDir = Join-Path $PSScriptRoot 'src'
$buildDir = Join-Path $PSScriptRoot '.build'
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
$common = @('-mcpu=cortex-a7', '-mthumb', '-O2', '-nostdlib',
            '-ffreestanding', '-Wl,-e,_start')
$targets = @(
    @{ name = 'payload_pin_packet'; source = 'payload_pin_packet.S';
       address = '0x86370000'; define = '-DPIN_ISO_TRACE' },
    @{ name = 'payload_exposure_preview'; source = 'payload_iso_preview.S';
       address = '0x86373d00'; define = '-DISO_INPUT_PREVIEW' },
    @{ name = 'payload_dispatcher_exposure'; source = 'payload_dispatcher_install.S';
       address = '0x86373580'; define = '-DSETTINGS_CAVE=0x86373d00' }
)

foreach ($target in $targets) {
    $elf = Join-Path $buildDir ($target.name + '.elf')
    $binary = Join-Path $buildDir ($target.name + '.bin')
    & $gcc @common "-Ttext=$($target.address)" $target.define '-o' $elf (Join-Path $sourceDir $target.source)
    if ($LASTEXITCODE -ne 0) { throw "Failed to link $($target.name)" }
    & $objcopy '-O' 'binary' $elf $binary
    if ($LASTEXITCODE -ne 0) { throw "Failed to extract $($target.name)" }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
foreach ($target in $targets) {
    $filename = $target.name + '.bin'
    Copy-Item -LiteralPath (Join-Path $buildDir $filename) -Destination (Join-Path $OutputDirectory $filename)
    Get-Item -LiteralPath (Join-Path $OutputDirectory $filename) | Select-Object Name,Length
}
