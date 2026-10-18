# Read-only Windows preflight. No installs, updates or configuration changes.
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Run inside the authorised Windows guest.' }
$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$current = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$displays = @(Get-CimInstance Win32_VideoController | Select-Object CurrentHorizontalResolution, CurrentVerticalResolution)
$desktopPath = Join-Path $env:ProgramFiles 'Microsoft Power BI Desktop\bin\PBIDesktop.exe'
$desktopVersion = $null
if (Test-Path -LiteralPath $desktopPath) {
  $desktopVersion = (Get-Item -LiteralPath $desktopPath).VersionInfo.ProductVersion
}
$storeVersions = @(Get-AppxPackage -Name 'Microsoft.MicrosoftPowerBIDesktop' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Version)
[pscustomobject]@{
  Observation = 'Read-only readiness information; not a native acceptance result'
  WindowsCaption = $os.Caption
  WindowsVersion = $os.Version
  Build = $current.CurrentBuildNumber
  UBR = $current.UBR
  OSArchitecture = $os.OSArchitecture
  ProcessArchitecture = $env:PROCESSOR_ARCHITECTURE
  ProcessorArchitectureCode = $cpu.Architecture
  FreePhysicalMemoryKiB = $os.FreePhysicalMemory
  TotalMemoryKiB = $os.TotalVisibleMemorySize
  Displays = $displays
  DesktopExecutableVersion = $desktopVersion
  DesktopStoreVersions = $storeVersions
  NativePowerBIStarted = $false
  SettingsModified = $false
  NextChecks = 'Verify applicable cumulative ARM fixes/superseding build, WebView2, guest tools and an adequate display before installation/native smoke test.'
} | ConvertTo-Json -Depth 5
