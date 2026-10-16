param(
    [Parameter(Mandatory=$true,Position=0)][string]$Compiler,
    [Parameter(Mandatory=$true,Position=1)][string]$OutputDirectory
)
$ErrorActionPreference='Stop'
$compilerPath=(Resolve-Path -LiteralPath $Compiler).Path
$output=[IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $output | Out-Null
$image=Join-Path $output 'large-program.exe'
$utf8=New-Object Text.UTF8Encoding($false)

# Generate test inputs, not compiler code or intermediate representations.
$main=New-Object Text.StringBuilder
[void]$main.AppendLine('module app::main; import app::library::*; pub fn main_entry()->u32{let mut total:u32=0;')
$library=New-Object Text.StringBuilder
[void]$library.AppendLine('module app::library;')
for($index=0;$index -lt 1023;$index++) {
    $name='f'+$index.ToString('D4')
    [void]$main.AppendLine("total += ${name}(1);")
    [void]$library.AppendLine("pub fn ${name}(value:u32)->u32{return value+$index;}")
}
[void]$main.AppendLine('if total!=523776 || f0511(1)!=512 || f0512(1)!=513 || f1022(1)!=1023{return 1;}return 42;}')
foreach($limit in @(1024,1025)) {
    $directory=Join-Path $output "functions-$limit/app"
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
    [IO.File]::WriteAllText((Join-Path $directory 'main.sotlas'),$main.ToString(),$utf8)
    $text=$library.ToString()
    if($limit -eq 1025){$text+='pub fn extra()->u32{return 0;}'}
    [IO.File]::WriteAllText((Join-Path $directory 'library.sotlas'),$text,$utf8)
}
foreach($limit in @(2048,2049)) {
    $text=New-Object Text.StringBuilder
    [void]$text.AppendLine('module strings; fn digit(data:*const u8)->u32{return unsafe{*(data+4)} as u32;}')
    for($chunk=0;$chunk -lt 32;$chunk++) {
        [void]$text.AppendLine("fn chunk$chunk()->u32{let mut total:u32=0;")
        for($offset=0;$offset -lt 64;$offset++) {
            [void]$text.AppendLine(('total += digit("s{0:D4}");' -f ($chunk*64+$offset)))
        }
        [void]$text.AppendLine('return total;}')
    }
    [void]$text.AppendLine('pub fn main_entry()->u32{let mut total:u32=0;')
    for($chunk=0;$chunk -lt 32;$chunk++){[void]$text.AppendLine("total += chunk$chunk();")}
    if($limit -eq 2049){[void]$text.AppendLine('total += digit("s2048");')}
    [void]$text.AppendLine('if total!=107512{return 1;}return 42;}')
    [IO.File]::WriteAllText((Join-Path $output "strings-$limit.sotlas"),$text.ToString(),$utf8)
}
foreach($length in @(65535,65536)) {
    $text='module bytes; pub fn main_entry()->u32{let data:*const u8="'+('a'*$length)+'";if unsafe{*data}!=97{return 1;}return 42;}'
    [IO.File]::WriteAllText((Join-Path $output "bytes-$length.sotlas"),$text,$utf8)
}

function Invoke-Case([string[]]$Arguments,[int]$Expected) {
    $preference=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    try{$lines=& $compilerPath @Arguments 2>&1;$status=$LASTEXITCODE}
    finally{$ErrorActionPreference=$preference}
    if($status -ne $Expected){throw "Exit $status, expected $Expected`: $Arguments`n$lines"}
}
function Verify-Program([string]$Source,[int]$Expected,[string]$Root='') {
    $before=''
    if($Expected -ne 0){$before=[Convert]::ToBase64String([IO.File]::ReadAllBytes($image))}
    if($Root) {
        Invoke-Case @('--check-build',$Root,$Source) $Expected
        Invoke-Case @('--build-win',$image,$Root,$Source) $Expected
    } else {
        Invoke-Case @('--check',$Source) $Expected
        Invoke-Case @($Source,$image) $Expected
    }
    if($Expected -eq 0) {
        & $image
        if($LASTEXITCODE -ne 42){throw "Program returned $LASTEXITCODE; expected 42"}
    } elseif([Convert]::ToBase64String([IO.File]::ReadAllBytes($image)) -ne $before) {
        throw 'Rejected compilation modified the previous executable.'
    }
    Write-Output "Passed: $Source (compiler exit $Expected)"
}
$savedPath=$env:PATH
try {
    $env:PATH=Join-Path $output 'no-host-tools'
    Verify-Program (Join-Path $output 'functions-1024/app/main.sotlas') 0 (Join-Path $output 'functions-1024')
    Verify-Program (Join-Path $output 'functions-1025/app/main.sotlas') 8 (Join-Path $output 'functions-1025')
    Verify-Program (Join-Path $output 'strings-2048.sotlas') 0
    Verify-Program (Join-Path $output 'strings-2049.sotlas') 7
    Verify-Program (Join-Path $output 'bytes-65535.sotlas') 0
    Verify-Program (Join-Path $output 'bytes-65536.sotlas') 7
} finally {$env:PATH=$savedPath}
