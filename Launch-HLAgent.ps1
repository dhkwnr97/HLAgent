$ErrorActionPreference = 'Stop'
$taskArguments = @('-d', 'Ubuntu-22.04', '--cd', ('"{0}"' -f $PSScriptRoot), '--', 'bash', 'scripts/start.sh')
Start-Process -FilePath 'wsl.exe' -ArgumentList $taskArguments -WindowStyle Hidden
