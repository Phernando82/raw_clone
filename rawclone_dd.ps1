param($dd, $src, $dst, $bs, $msg_prep_src, $msg_prep_dst, $msg_lock, $msg_lock_ok, $msg_lock_fail, $msg_handles_open, $msg_dd_done, $msg_handles_closed)
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -TypeDefinition '
    using System;
    using System.Runtime.InteropServices;
    public class RawCloneDisk {
        [DllImport("kernel32.dll", SetLastError=true, CharSet=CharSet.Unicode)]
        public static extern IntPtr CreateFile(string f, uint a, uint s, IntPtr p, uint c, uint fl, IntPtr t);
        [DllImport("kernel32.dll", SetLastError=true)]
        public static extern bool DeviceIoControl(IntPtr h, uint c, IntPtr i, uint il, IntPtr o, uint ol, ref uint r, IntPtr ov);
        [DllImport("kernel32.dll")]
        public static extern bool CloseHandle(IntPtr h);
    }
' 2>$null

$ACCESS   = [uint32]3221225472  # GENERIC_READ | GENERIC_WRITE
$SHARE    = [uint32]3           # FILE_SHARE_READ | FILE_SHARE_WRITE
$CREATE   = [uint32]3           # OPEN_EXISTING
$LOCK     = [uint32]589848      # FSCTL_LOCK_VOLUME
$DISMOUNT = [uint32]589856      # FSCTL_DISMOUNT_VOLUME
$INVALID  = [IntPtr](-1)

function Is-ValidHandle($h) {
    try { $v = $h.ToInt64(); return ($v -ne -1 -and $v -ne 0) } catch { return $false }
}

function Get-DiskNum($path) {
    if ($path -match 'PhysicalDrive([0-9]+)') { return [int]$Matches[1] }
    return $null
}

function Lock-Volumes-For-Disk($diskNum) {
    $handles = [System.Collections.Generic.List[IntPtr]]::new()
    try {
        $letters = @(Get-Partition -DiskNumber $diskNum -ErrorAction Stop |
            Where-Object { $_.DriveLetter } |
            ForEach-Object { $_.DriveLetter })
    } catch { $letters = @() }

    foreach ($l in $letters) {
        $vol = "\\.\$($l):"
        $h = [RawCloneDisk]::CreateFile($vol, $ACCESS, $SHARE, [IntPtr]::Zero, $CREATE, [uint32]0, [IntPtr]::Zero)
        if (Is-ValidHandle $h) {
            $r = [uint32]0
            $lok = [RawCloneDisk]::DeviceIoControl($h, $LOCK,     [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$r, [IntPtr]::Zero)
            $dok = [RawCloneDisk]::DeviceIoControl($h, $DISMOUNT, [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$r, [IntPtr]::Zero)
            [Console]::WriteLine("INFO:" + ($msg_lock    -replace "__LETTER__", "$l"))
            [Console]::WriteLine("INFO:" + ($msg_lock_ok -replace "__LOK__", "$lok" -replace "__DOK__", "$dok"))
            $handles.Add($h)
        }
    }
    return $handles
}

function Open-PhysicalDisk($diskNum) {
    # Abrir o PhysicalDrive directamente para manter acesso exclusivo
    $path = "\\.\PhysicalDrive$diskNum"
    $h = [RawCloneDisk]::CreateFile($path, $ACCESS, $SHARE, [IntPtr]::Zero, $CREATE, [uint32]0, [IntPtr]::Zero)
    if (Is-ValidHandle $h) {
        $r = [uint32]0
        [RawCloneDisk]::DeviceIoControl($h, $DISMOUNT, [IntPtr]::Zero, 0, [IntPtr]::Zero, 0, [ref]$r, [IntPtr]::Zero) | Out-Null
        return $h
    }
    return [IntPtr]::Zero
}

function Clean-Disk($diskNum) {
    [Console]::WriteLine("INFO:Limpando particoes do disco $diskNum...")
    [Console]::Out.Flush()
    Set-Location $env:SystemRoot
    # Passo 1: clean via diskpart
    $dpScript = "select disk $diskNum`r`nclean`r`nexit"
    $dpFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($dpFile, $dpScript)
    & diskpart /s $dpFile | Out-Null
    Remove-Item $dpFile -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 1000
    # Passo 2: online + initialize via PowerShell nativo
    try {
        $disk = Get-Disk -Number $diskNum -ErrorAction Stop
        if ($disk.IsOffline) {
            Set-Disk -Number $diskNum -IsOffline $false
            Start-Sleep -Milliseconds 500
        }
        if ($disk.IsReadOnly) {
            Set-Disk -Number $diskNum -IsReadOnly $false
        }
        if ($disk.PartitionStyle -eq 'RAW') {
            Initialize-Disk -Number $diskNum -PartitionStyle MBR -ErrorAction Stop
            [Console]::WriteLine("INFO:  Disco inicializado (MBR)")
        }
    } catch {
        [Console]::WriteLine("INFO:  Initialize via PS falhou: $($_.Exception.Message)")
    }
    [Console]::WriteLine("INFO:  diskpart clean executado")
    [Console]::Out.Flush()
    Start-Sleep -Milliseconds 1000
}

$allHandles = [System.Collections.Generic.List[IntPtr]]::new()

# Preparar disco fonte
$srcDisk = Get-DiskNum $src
if ($srcDisk -ne $null) {
    [Console]::WriteLine("INFO:" + ($msg_prep_src -replace "__NUM__", $srcDisk))
    [Console]::Out.Flush()
    $srcVolHandles = Lock-Volumes-For-Disk $srcDisk
    foreach ($h in $srcVolHandles) { $allHandles.Add($h) }
}

# Preparar disco destino
$dstDisk = Get-DiskNum $dst
if ($dstDisk -ne $null -and $dstDisk -ne $srcDisk) {
    [Console]::WriteLine("INFO:" + ($msg_prep_dst -replace "__NUM__", $dstDisk))
    [Console]::Out.Flush()
    # 1. Lock+Dismount dos volumes e fechar handles — diskpart precisa do disco livre
    $dstVolHandles = Lock-Volumes-For-Disk $dstDisk
    foreach ($h in $dstVolHandles) {
        try { [RawCloneDisk]::CloseHandle($h) | Out-Null } catch {}
    }
    # 2. Clean + initialize — dd abre o PhysicalDrive sozinho sem handle prévio
    Clean-Disk $dstDisk
    Start-Sleep -Milliseconds 1000
}

[Console]::WriteLine("INFO:" + ($msg_handles_open -replace "__N__", $allHandles.Count))
[Console]::Out.Flush()

try {
    Set-Location $env:SystemRoot

    # Calcular count para disco físico fonte — garante leitura do disco completo
    $countArg = ""
    if ($src -match 'PhysicalDrive([0-9]+)') {
        $srcNum = [int]$Matches[1]
        try {
            $diskSize = (Get-Disk -Number $srcNum -ErrorAction Stop).Size
            $bsBytes = if ($bs -match '^([0-9]+)M$') { [int64]$Matches[1] * 1MB } `
                       elseif ($bs -match '^([0-9]+)K$') { [int64]$Matches[1] * 1KB } `
                       else { [int64]$bs }
            $count = [math]::Ceiling($diskSize / $bsBytes)
            $countArg = "count=$count"
            [Console]::WriteLine("INFO:Tamanho do disco: $diskSize bytes, count=$count")
            [Console]::Out.Flush()
        } catch {
            [Console]::WriteLine("INFO:Nao foi possivel calcular count: $($_.Exception.Message)")
        }
    }

    $ddCmd = "`"$dd`" `"if=$src`" `"of=$dst`" bs=$bs $countArg --progress conv=noerror,sync 2>&1"
    cmd /c $ddCmd | ForEach-Object {
        [Console]::WriteLine("$_")
        [Console]::Out.Flush()
    }
    [Console]::WriteLine("INFO:" + ($msg_dd_done -replace "__CODE__", "$LASTEXITCODE"))
} finally {
    foreach ($h in $allHandles) {
        try { [RawCloneDisk]::CloseHandle($h) | Out-Null } catch {}
    }
    [Console]::WriteLine("INFO:" + $msg_handles_closed)
    [Console]::Out.Flush()
}
