param(
    [Parameter(Mandatory=$true,Position=0)][string]$Compiler,
    [Parameter(Mandatory=$true,Position=1)][string]$OutputDirectory,
    [Parameter(Position=2)][string]$Manifest
)
# Shell orchestration only. All test assertions and inputs are .sotlas sources.
$ErrorActionPreference='Stop'
$repository=Split-Path -Parent $PSScriptRoot
$compilerPath=(Resolve-Path -LiteralPath $Compiler).Path
if (!$Manifest) { $Manifest=Join-Path $repository 'tests/native/contracts/manifest.txt' }
$manifestPath=(Resolve-Path -LiteralPath $Manifest).Path
$suite=Split-Path -Parent $manifestPath
$output=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) { throw 'Choose a fresh test output directory.' }
New-Item -ItemType Directory -Path (Join-Path $output 'src/sotlas/runtime') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $output 'logs') | Out-Null
Copy-Item -Path (Join-Path $repository 'runtime/native/*.sotlas') -Destination (Join-Path $output 'src/sotlas/runtime')
$encoding=New-Object Text.UTF8Encoding($false)

# Suppress OS crash dialogs in the launcher and its native children. P/Invoke
# metadata is emitted by the shell; no C/C# source or host compiler is involved.
$name=New-Object Reflection.AssemblyName('SotlasTestErrorMode')
if ($PSVersionTable.PSEdition -eq 'Core') {
    $assembly=[Reflection.Emit.AssemblyBuilder]::DefineDynamicAssembly($name,[Reflection.Emit.AssemblyBuilderAccess]::Run)
} else {
    $assembly=[AppDomain]::CurrentDomain.DefineDynamicAssembly($name,[Reflection.Emit.AssemblyBuilderAccess]::Run)
}
$module=$assembly.DefineDynamicModule('Native')
$type=$module.DefineType('ErrorMode',[Reflection.TypeAttributes]::Public)
$method=$type.DefinePInvokeMethod('SetErrorMode','kernel32.dll',
    [Reflection.MethodAttributes]'Public,Static,PinvokeImpl',[Reflection.CallingConventions]::Standard,
    [uint32],[Type[]]@([uint32]),[Runtime.InteropServices.CallingConvention]::Winapi,[Runtime.InteropServices.CharSet]::Auto)
$method.SetImplementationFlags([Reflection.MethodImplAttributes]::PreserveSig)
$nativeType=$type.CreateType()
$setter=$nativeType.GetMethod('SetErrorMode')
$previousMode=$setter.Invoke($null,@([uint32]32771))

function Invoke-Native([string]$Executable,[string[]]$Arguments,[string]$Log) {
    $info=New-Object Diagnostics.ProcessStartInfo
    $info.FileName=$Executable
    $info.Arguments=($Arguments | ForEach-Object { if ($_.Contains('"')) {throw 'Quotes are not valid test paths.'}; '"'+$_+'"' }) -join ' '
    $info.UseShellExecute=$false
    $info.CreateNoWindow=$true
    $info.WindowStyle=[Diagnostics.ProcessWindowStyle]::Hidden
    $info.RedirectStandardOutput=$true
    $info.RedirectStandardError=$true
    $info.EnvironmentVariables.Clear()
    $info.EnvironmentVariables['PATH']=Join-Path $output 'no-host-tools'
    $info.EnvironmentVariables['SystemRoot']=$env:SystemRoot
    $process=New-Object Diagnostics.Process
    $process.StartInfo=$info
    try {
        if (!$process.Start()) {throw 'Native process did not start.'}
        $stdout=$process.StandardOutput.ReadToEndAsync()
        $stderr=$process.StandardError.ReadToEndAsync()
        if (!$process.WaitForExit(60000)) { $process.Kill();throw 'Native test process timed out.' }
        [IO.File]::AppendAllText($Log,$stdout.Result+$stderr.Result,$encoding)
        return $process.ExitCode
    } finally { $process.Dispose() }
}
function Native-Hash([string]$Path) {
    $stream=[IO.File]::OpenRead($Path);$hash=[Security.Cryptography.SHA256]::Create()
    try { return [Convert]::ToBase64String($hash.ComputeHash($stream)) }
    finally { $stream.Dispose();$hash.Dispose() }
}
$results=New-Object Collections.Generic.List[object]
$seen=@{}
try {
    foreach ($line in [IO.File]::ReadAllLines($manifestPath)) {
        if (!$line.Trim() -or $line.TrimStart().StartsWith('#')) {continue}
        $parts=$line.Trim() -split '\s+'
        if ($parts.Count -ne 3) {throw 'Invalid native test manifest row.'}
        $mode,$id,$source=$parts
        if ($id -notmatch '^[a-z0-9_]+$' -or $source -cne "cases/$id.sotlas" -or $seen.ContainsKey($id)) {throw 'Invalid or duplicate test identifier.'}
        if ($mode -cnotin @('pass','reject','syntax','fault')) {throw 'Unknown native test mode.'}
        $seen[$id]=$true
        $original=Join-Path $suite $source
        if (!(Test-Path -LiteralPath $original -PathType Leaf)) {throw "Missing Sotlas test: $source"}
        $entry=Join-Path $output "src/$id.sotlas"
        Copy-Item -LiteralPath $original -Destination $entry
        $sourceRoot=Join-Path $output 'src'
        $image=Join-Path $output "$id.exe"
        $log=Join-Path $output "logs/$id.log"
        $failure=''
        $rejection=@()
        if ($mode -ceq 'reject') { $rejection=@(6,7) }
        if ($mode -ceq 'syntax') { $rejection=@(5) }
        $checked=Invoke-Native $compilerPath @('--check-build',$sourceRoot,$entry) $log
        if ($rejection.Count -ne 0) {
            if ($checked -notin $rejection) { $failure="check returned $checked; expected $($rejection -join ' or ')" }
            Copy-Item -LiteralPath $compilerPath -Destination $image
        } elseif ($checked -ne 0) { $failure="check returned $checked" }
        if (!$failure) {
            $compiled=Invoke-Native $compilerPath @('--build-win',$image,$sourceRoot,$entry) $log
            if ($rejection.Count -ne 0) {
                if ($compiled -notin $rejection) { $failure="build returned $compiled; expected $($rejection -join ' or ')" }
                elseif ((Native-Hash $image) -ne (Native-Hash $compilerPath)) { $failure='rejected build changed existing output' }
            } elseif ($compiled -ne 0) { $failure="build returned $compiled" }
            else {
                $actual=Invoke-Native $image @() $log
                if ($mode -ceq 'fault') {
                    $status=[BitConverter]::ToUInt32([BitConverter]::GetBytes([int32]$actual),0)
                    if ($status -ne 3221225620) { $failure="execution returned $actual; expected integer divide by zero" }
                } elseif ($actual -ne 0) { $failure="execution returned $actual; expected 0" }
            }
        }
        $results.Add([pscustomobject]@{Name=$id;Source=$source;Mode=$mode;Failure=$failure})
        if ($failure) {
            Write-Output "::error file=tests/native/contracts/$source,title=Sotlas ${id}::${failure}"
            Write-Output ([IO.File]::ReadAllText($log))
        } else { Write-Output "PASS $id ($mode)" }
    }
    if ($results.Count -eq 0) {throw 'An empty Sotlas suite cannot pass.'}
    $failures=@($results | Where-Object {$_.Failure}).Count
    $settings=New-Object Xml.XmlWriterSettings
    $settings.Encoding=$encoding;$settings.Indent=$true
    $xml=[Xml.XmlWriter]::Create((Join-Path $output 'junit.xml'),$settings)
    try {
        $xml.WriteStartDocument();$xml.WriteStartElement('testsuite')
        $xml.WriteAttributeString('name','Sotlas native contracts')
        $xml.WriteAttributeString('tests',[string]$results.Count);$xml.WriteAttributeString('failures',[string]$failures)
        foreach ($result in $results) {
            $xml.WriteStartElement('testcase');$xml.WriteAttributeString('classname','Sotlas.Native')
            $xml.WriteAttributeString('name',$result.Name);$xml.WriteAttributeString('file',"tests/native/contracts/$($result.Source)")
            if ($result.Failure) {$xml.WriteStartElement('failure');$xml.WriteAttributeString('message',$result.Failure);$xml.WriteEndElement()}
            $xml.WriteEndElement()
        }
        $xml.WriteEndElement();$xml.WriteEndDocument()
    } finally {$xml.Dispose()}
    $summary="# Sotlas native contracts`n`n| Case | Result |`n| --- | --- |`n"
    foreach ($result in $results) {
        $status='PASS ('+$result.Mode+')';if ($result.Failure) {$status='FAIL: '+$result.Failure}
        $summary+='| '+$result.Name+' | '+$status+" |`n"
    }
    $summary+="`n**$($results.Count) Sotlas tests, $failures failures.** Compiler and programs ran with host tools absent from PATH.`n"
    [IO.File]::WriteAllText((Join-Path $output 'summary.md'),$summary,$encoding)
    if ($env:GITHUB_STEP_SUMMARY) {[IO.File]::AppendAllText($env:GITHUB_STEP_SUMMARY,$summary,$encoding)}
    Write-Output "Sotlas tests: $($results.Count) total, $failures failures. Reports: $output"
    if ($failures -ne 0) {exit 1}
} finally { [void]$setter.Invoke($null,@([uint32]$previousMode)) }
