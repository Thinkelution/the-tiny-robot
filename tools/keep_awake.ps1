# Keeps Windows from idle-sleeping while Blender renders. It asks for "system required" through the same
# Windows API media players use (SetThreadExecutionState); no power settings are changed. Exits after Blender
# has not been running for 10 minutes, and Windows drops the request when this process ends.
Add-Type -Namespace Win32 -Name Power -MemberDefinition @'
[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);
'@
$ES_CONTINUOUS = [uint32]"0x80000000"
$ES_SYSTEM_REQUIRED = [uint32]"0x00000001"
[void][Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
$idle = 0
while ($idle -lt 10) {
    Start-Sleep -Seconds 60
    if (Get-Process blender -ErrorAction SilentlyContinue) { $idle = 0 } else { $idle++ }
    [void][Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
}
[void][Win32.Power]::SetThreadExecutionState($ES_CONTINUOUS)
"render finished: keep-awake released"
