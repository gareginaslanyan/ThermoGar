#requires -Version 5.1
$RawCliArguments = @($args)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$ProgramFiles64 = if (-not [string]::IsNullOrWhiteSpace($env:ProgramW6432)) { $env:ProgramW6432 } else { $env:ProgramFiles }
$InstallRoot = [System.IO.Path]::GetFullPath((Join-Path $ProgramFiles64 'ThermoGar')).TrimEnd('\')
$ProfileRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'ThermoGar')).TrimEnd('\')
$ShortcutPath = [System.IO.Path]::GetFullPath((Join-Path $env:ProgramData 'Microsoft\Windows\Start Menu\Programs\ThermoGar\ThermoGar.lnk'))
$UninstallKey = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ThermoGar'
$Sequence = 0
$script:EvidenceRoot = $null

function Get-Sha256Hex {
    param([byte[]]$Bytes)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return -join ($algorithm.ComputeHash($Bytes) | ForEach-Object { $_.ToString('X2') }) }
    finally { $algorithm.Dispose() }
}

function Read-StableFile {
    param([string]$Path, [string]$ExpectedSha256 = '')
    if ([string]::IsNullOrWhiteSpace($Path) -or -not [System.IO.Path]::IsPathRooted($Path)) { throw 'PATH_NOT_ABSOLUTE' }
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $cursor = Split-Path -Parent $full
    while (-not [string]::IsNullOrEmpty($cursor)) {
        $ancestor = Get-Item -LiteralPath $cursor -Force
        if (($ancestor.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'REPARSE_ANCESTOR' }
        $parent = Split-Path -Parent $cursor
        if ([string]::Equals($parent, $cursor, [System.StringComparison]::OrdinalIgnoreCase)) { break }
        $cursor = $parent
    }
    $item = Get-Item -LiteralPath $full -Force
    if (-not ($item -is [System.IO.FileInfo]) -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'NOT_PLAIN_FILE' }
    $alternateStreams = @(Get-Item -LiteralPath $full -Stream * -ErrorAction Stop | Where-Object { $_.Stream -cne ':$DATA' })
    if ($alternateStreams.Count -ne 0) { throw 'ALTERNATE_DATA_STREAM' }
    $first = [System.IO.File]::ReadAllBytes($item.FullName)
    $firstHash = Get-Sha256Hex $first
    $second = [System.IO.File]::ReadAllBytes($item.FullName)
    if ($first.LongLength -ne $second.LongLength -or $firstHash -cne (Get-Sha256Hex $second)) { throw 'UNSTABLE_FILE' }
    if (-not [string]::IsNullOrEmpty($ExpectedSha256) -and $firstHash -cne $ExpectedSha256.ToUpperInvariant()) { throw 'HASH_MISMATCH' }
    return [pscustomobject]@{ Path = $item.FullName; Bytes = $first.LongLength; Sha256 = $firstHash }
}

function Assert-PlainDirectory {
    param([string]$Path)
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $cursor = $full
    while (-not [string]::IsNullOrEmpty($cursor)) {
        $item = Get-Item -LiteralPath $cursor -Force
        if (-not ($item -is [System.IO.DirectoryInfo]) -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'DIRECTORY_INVALID' }
        $parent = Split-Path -Parent $cursor
        if ([string]::Equals($parent, $cursor, [System.StringComparison]::OrdinalIgnoreCase)) { break }
        $cursor = $parent
    }
    return $full
}

function Write-NewUtf8NoBom {
    param([string]$Path, [string]$Text)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Text)
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

function Invoke-CapturedProcess {
    param([string]$Name, [string]$FilePath, [string]$Arguments, [bool]$RequireZero)
    $script:Sequence++
    $prefix = ('{0:D3}-{1}' -f $script:Sequence, $Name)
    $stdoutPath = Join-Path $script:EvidenceRoot ($prefix + '.stdout.txt')
    $stderrPath = Join-Path $script:EvidenceRoot ($prefix + '.stderr.txt')
    # Capture executable identity before launch; uninstall may remove its own source path.
    $executable = Read-StableFile $FilePath
    $started = [DateTime]::UtcNow
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $ended = [DateTime]::UtcNow
    $stdout = if (Test-Path -LiteralPath $stdoutPath) { [System.IO.File]::ReadAllText($stdoutPath, [System.Text.UTF8Encoding]::new($false, $true)) } else { '' }
    $stderr = if (Test-Path -LiteralPath $stderrPath) { [System.IO.File]::ReadAllText($stderrPath, [System.Text.UTF8Encoding]::new($false, $true)) } else { '' }
    $record = [ordered]@{
        schema = 1; name = $Name; file_sha256 = $executable.Sha256; arguments = $Arguments
        started_utc = $started.ToString('yyyy-MM-ddTHH:mm:ss.fffZ'); ended_utc = $ended.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        duration_ms = [long]($ended - $started).TotalMilliseconds; exit_code = $process.ExitCode
        stdout_sha256 = Get-Sha256Hex ([System.Text.UTF8Encoding]::new($false).GetBytes($stdout))
        stderr_sha256 = Get-Sha256Hex ([System.Text.UTF8Encoding]::new($false).GetBytes($stderr))
    }
    Write-NewUtf8NoBom -Path (Join-Path $script:EvidenceRoot ($prefix + '.result.json')) -Text ($record | ConvertTo-Json -Compress -Depth 6)
    if ($RequireZero -and $process.ExitCode -ne 0) { throw ($Name + '_EXIT_' + $process.ExitCode) }
    return [pscustomobject]@{ ExitCode = $process.ExitCode; Stdout = $stdout; Stderr = $stderr }
}

function Initialize-LinkedTokenLauncher {
    if ($null -ne ('ThermoGar.P4.LinkedTokenLauncher' -as [type])) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;

namespace ThermoGar.P4 {
    public sealed class LinkedTokenLaunchReceipt {
        public int ProcessId { get; private set; }
        public int SourceElevationType { get; private set; }
        public int TargetElevationType { get; private set; }
        public string SourceUserSid { get; private set; }
        public string TargetUserSid { get; private set; }
        public int SourceSessionId { get; private set; }
        public int TargetSessionId { get; private set; }
        public string TargetIntegritySid { get; private set; }
        public int TargetIntegrityRid { get; private set; }
        public int ExitCode { get; private set; }

        internal LinkedTokenLaunchReceipt(int processId, int sourceElevationType, int targetElevationType,
                string sourceUserSid, string targetUserSid, int sourceSessionId, int targetSessionId,
                string targetIntegritySid, int targetIntegrityRid, int exitCode) {
            ProcessId = processId;
            SourceElevationType = sourceElevationType;
            TargetElevationType = targetElevationType;
            SourceUserSid = sourceUserSid;
            TargetUserSid = targetUserSid;
            SourceSessionId = sourceSessionId;
            TargetSessionId = targetSessionId;
            TargetIntegritySid = targetIntegritySid;
            TargetIntegrityRid = targetIntegrityRid;
            ExitCode = exitCode;
        }
    }

    public sealed class ProcessTokenReceipt {
        public int ProcessId { get; private set; }
        public string CreationFileTime { get; private set; }
        public int ElevationType { get; private set; }
        public string UserSid { get; private set; }
        public int SessionId { get; private set; }
        public string IntegritySid { get; private set; }
        public int IntegrityRid { get; private set; }

        internal ProcessTokenReceipt(int processId, string creationFileTime, int elevationType, string userSid,
                int sessionId, string integritySid, int integrityRid) {
            ProcessId = processId;
            CreationFileTime = creationFileTime;
            ElevationType = elevationType;
            UserSid = userSid;
            SessionId = sessionId;
            IntegritySid = integritySid;
            IntegrityRid = integrityRid;
        }
    }

    public sealed class DirectoryIdentityReceipt {
        public string FinalPath { get; private set; }
        public uint Attributes { get; private set; }
        public string CreationFileTime { get; private set; }
        public string LastWriteFileTime { get; private set; }
        public uint VolumeSerialNumber { get; private set; }
        public string FileIndex { get; private set; }

        internal DirectoryIdentityReceipt(string finalPath, uint attributes, string creationFileTime,
                string lastWriteFileTime, uint volumeSerialNumber, string fileIndex) {
            FinalPath = finalPath;
            Attributes = attributes;
            CreationFileTime = creationFileTime;
            LastWriteFileTime = lastWriteFileTime;
            VolumeSerialNumber = volumeSerialNumber;
            FileIndex = fileIndex;
        }
    }

    public static class LinkedTokenLauncher {
        const uint TOKEN_ASSIGN_PRIMARY = 0x0001;
        const uint TOKEN_DUPLICATE = 0x0002;
        const uint TOKEN_QUERY = 0x0008;
        const uint TOKEN_ADJUST_DEFAULT = 0x0080;
        const uint TOKEN_ADJUST_SESSIONID = 0x0100;
        const int TokenUser = 1;
        const int TokenSessionId = 12;
        const int TokenElevationType = 18;
        const int TokenLinkedToken = 19;
        const int TokenIntegrityLevel = 25;
        const int TokenPrimary = 1;
        const int SecurityImpersonation = 2;
        const int TokenElevationTypeFull = 2;
        const int TokenElevationTypeLimited = 3;
        const int MediumIntegrityRid = 0x2000;
        const uint LOGON_WITH_PROFILE = 0x00000001;
        const uint CREATE_SUSPENDED = 0x00000004;
        const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;
        const uint CREATE_NO_WINDOW = 0x08000000;
        const uint WAIT_OBJECT_0 = 0;
        const uint WAIT_TIMEOUT = 258;
        const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
        const uint SYNCHRONIZE = 0x00100000;
        const uint FILE_READ_ATTRIBUTES = 0x00000080;
        const uint FILE_SHARE_READ = 0x00000001;
        const uint FILE_SHARE_WRITE = 0x00000002;
        const uint FILE_SHARE_DELETE = 0x00000004;
        const uint OPEN_EXISTING = 3;
        const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
        const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
        const uint FILE_ATTRIBUTE_DIRECTORY = 0x00000010;
        const uint FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400;
        const int ERROR_INSUFFICIENT_BUFFER = 122;

        [StructLayout(LayoutKind.Sequential)]
        struct TOKEN_LINKED_TOKEN { public IntPtr LinkedToken; }

        [StructLayout(LayoutKind.Sequential)]
        struct STARTUPINFO {
            public uint cb;
            public IntPtr lpReserved;
            public IntPtr lpDesktop;
            public IntPtr lpTitle;
            public uint dwX;
            public uint dwY;
            public uint dwXSize;
            public uint dwYSize;
            public uint dwXCountChars;
            public uint dwYCountChars;
            public uint dwFillAttribute;
            public uint dwFlags;
            public ushort wShowWindow;
            public ushort cbReserved2;
            public IntPtr lpReserved2;
            public IntPtr hStdInput;
            public IntPtr hStdOutput;
            public IntPtr hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct PROCESS_INFORMATION {
            public IntPtr hProcess;
            public IntPtr hThread;
            public uint dwProcessId;
            public uint dwThreadId;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct FILETIME {
            public uint dwLowDateTime;
            public uint dwHighDateTime;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct BY_HANDLE_FILE_INFORMATION {
            public uint FileAttributes;
            public FILETIME CreationTime;
            public FILETIME LastAccessTime;
            public FILETIME LastWriteTime;
            public uint VolumeSerialNumber;
            public uint FileSizeHigh;
            public uint FileSizeLow;
            public uint NumberOfLinks;
            public uint FileIndexHigh;
            public uint FileIndexLow;
        }

        [DllImport("kernel32.dll")]
        static extern IntPtr GetCurrentProcess();

        [DllImport("kernel32.dll")]
        static extern uint GetCurrentProcessId();

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool ProcessIdToSessionId(uint processId, out uint sessionId);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern IntPtr OpenProcess(uint desiredAccess, bool inheritHandle, uint processId);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern IntPtr CreateFileW(string fileName, uint desiredAccess, uint shareMode, IntPtr securityAttributes,
            uint creationDisposition, uint flagsAndAttributes, IntPtr templateFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetFileInformationByHandle(IntPtr file, out BY_HANDLE_FILE_INFORMATION information);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern uint GetFinalPathNameByHandleW(IntPtr file, StringBuilder path, uint pathLength, uint flags);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetProcessTimes(IntPtr process, out FILETIME creation, out FILETIME exit,
            out FILETIME kernel, out FILETIME user);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool CloseHandle(IntPtr handle);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern uint ResumeThread(IntPtr thread);

        [DllImport("kernel32.dll")]
        static extern IntPtr LocalFree(IntPtr memory);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool TerminateProcess(IntPtr process, uint exitCode);

        [DllImport("advapi32.dll", SetLastError = true)]
        static extern bool OpenProcessToken(IntPtr process, uint desiredAccess, out IntPtr token);

        [DllImport("advapi32.dll", EntryPoint = "GetTokenInformation", SetLastError = true)]
        static extern bool GetTokenElevationType(IntPtr token, int informationClass, out int information, int informationLength, out int returnLength);

        [DllImport("advapi32.dll", EntryPoint = "GetTokenInformation", SetLastError = true)]
        static extern bool GetLinkedToken(IntPtr token, int informationClass, out TOKEN_LINKED_TOKEN information, int informationLength, out int returnLength);

        [DllImport("advapi32.dll", EntryPoint = "GetTokenInformation", SetLastError = true)]
        static extern bool GetTokenInformationBuffer(IntPtr token, int informationClass, IntPtr information, int informationLength, out int returnLength);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool ConvertSidToStringSidW(IntPtr sid, out IntPtr stringSid);

        [DllImport("advapi32.dll", SetLastError = true)]
        static extern IntPtr GetSidSubAuthorityCount(IntPtr sid);

        [DllImport("advapi32.dll", SetLastError = true)]
        static extern IntPtr GetSidSubAuthority(IntPtr sid, uint subAuthority);

        [DllImport("advapi32.dll", SetLastError = true)]
        static extern bool DuplicateTokenEx(IntPtr existingToken, uint desiredAccess, IntPtr tokenAttributes,
            int impersonationLevel, int tokenType, out IntPtr newToken);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool CreateProcessWithTokenW(IntPtr token, uint logonFlags, string applicationName,
            StringBuilder commandLine, uint creationFlags, IntPtr environment, string currentDirectory,
            ref STARTUPINFO startupInfo, out PROCESS_INFORMATION processInformation);

        [DllImport("userenv.dll", SetLastError = true)]
        static extern bool CreateEnvironmentBlock(out IntPtr environment, IntPtr token, bool inherit);

        [DllImport("userenv.dll", SetLastError = true)]
        static extern bool DestroyEnvironmentBlock(IntPtr environment);

        static void RequireWin32(bool result, string operation) {
            if (!result) throw new Win32Exception(Marshal.GetLastWin32Error(), operation);
        }

        static int ReadElevationType(IntPtr token) {
            int value;
            int returned;
            RequireWin32(GetTokenElevationType(token, TokenElevationType, out value, sizeof(int), out returned), "GetTokenInformation(TokenElevationType)");
            if (returned != sizeof(int)) throw new InvalidOperationException("TOKEN_ELEVATION_TYPE_SIZE");
            return value;
        }

        static IntPtr ReadTokenInformation(IntPtr token, int informationClass) {
            int required;
            if (GetTokenInformationBuffer(token, informationClass, IntPtr.Zero, 0, out required) ||
                Marshal.GetLastWin32Error() != ERROR_INSUFFICIENT_BUFFER || required <= 0 || required > 65536) {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "GetTokenInformation(size)");
            }
            IntPtr buffer = Marshal.AllocHGlobal(required);
            try {
                int returned;
                RequireWin32(GetTokenInformationBuffer(token, informationClass, buffer, required, out returned), "GetTokenInformation(data)");
                if (returned <= 0 || returned > required) throw new InvalidOperationException("TOKEN_INFORMATION_SIZE");
                return buffer;
            } catch {
                Marshal.FreeHGlobal(buffer);
                throw;
            }
        }

        static string SidToString(IntPtr sid) {
            if (sid == IntPtr.Zero) throw new InvalidOperationException("TOKEN_SID_NULL");
            IntPtr text = IntPtr.Zero;
            try {
                RequireWin32(ConvertSidToStringSidW(sid, out text), "ConvertSidToStringSidW");
                string value = Marshal.PtrToStringUni(text);
                if (String.IsNullOrWhiteSpace(value)) throw new InvalidOperationException("TOKEN_SID_EMPTY");
                return value;
            } finally {
                if (text != IntPtr.Zero) LocalFree(text);
            }
        }

        static string ReadUserSid(IntPtr token) {
            IntPtr buffer = ReadTokenInformation(token, TokenUser);
            try { return SidToString(Marshal.ReadIntPtr(buffer)); }
            finally { Marshal.FreeHGlobal(buffer); }
        }

        static int ReadSessionId(IntPtr token) {
            IntPtr buffer = ReadTokenInformation(token, TokenSessionId);
            try { return Marshal.ReadInt32(buffer); }
            finally { Marshal.FreeHGlobal(buffer); }
        }

        static string ReadIntegritySid(IntPtr token, out int integrityRid) {
            IntPtr buffer = ReadTokenInformation(token, TokenIntegrityLevel);
            try {
                IntPtr sid = Marshal.ReadIntPtr(buffer);
                IntPtr countPointer = GetSidSubAuthorityCount(sid);
                if (countPointer == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetSidSubAuthorityCount");
                byte count = Marshal.ReadByte(countPointer);
                if (count == 0) throw new InvalidOperationException("TOKEN_INTEGRITY_SID_EMPTY");
                IntPtr ridPointer = GetSidSubAuthority(sid, checked((uint)(count - 1)));
                if (ridPointer == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetSidSubAuthority");
                integrityRid = Marshal.ReadInt32(ridPointer);
                return SidToString(sid);
            } finally { Marshal.FreeHGlobal(buffer); }
        }

        static void ProveLimitedUserToken(IntPtr token, string expectedUserSid, int expectedSessionId,
                out int elevationType, out string userSid, out int sessionId, out string integritySid, out int integrityRid) {
            elevationType = ReadElevationType(token);
            userSid = ReadUserSid(token);
            sessionId = ReadSessionId(token);
            integritySid = ReadIntegritySid(token, out integrityRid);
            if (elevationType != TokenElevationTypeLimited) throw new InvalidOperationException("TARGET_TOKEN_NOT_LIMITED");
            if (!String.Equals(userSid, expectedUserSid, StringComparison.Ordinal)) throw new InvalidOperationException("TARGET_TOKEN_USER_MISMATCH");
            if (sessionId != expectedSessionId) throw new InvalidOperationException("TARGET_TOKEN_SESSION_MISMATCH");
            if (integrityRid != MediumIntegrityRid || !String.Equals(integritySid, "S-1-16-8192", StringComparison.Ordinal)) {
                throw new InvalidOperationException("TARGET_TOKEN_NOT_MEDIUM_INTEGRITY");
            }
        }

        static string ReadCreationFileTime(IntPtr process) {
            FILETIME creation;
            FILETIME exit;
            FILETIME kernel;
            FILETIME user;
            RequireWin32(GetProcessTimes(process, out creation, out exit, out kernel, out user), "GetProcessTimes(app)");
            ulong value = ((ulong)creation.dwHighDateTime << 32) | (ulong)creation.dwLowDateTime;
            return value.ToString(CultureInfo.InvariantCulture);
        }

        static string FileTimeString(FILETIME value) {
            ulong number = ((ulong)value.dwHighDateTime << 32) | (ulong)value.dwLowDateTime;
            return number.ToString(CultureInfo.InvariantCulture);
        }

        static string NormalizeFinalPath(string value) {
            if (value.StartsWith(@"\\?\UNC\", StringComparison.OrdinalIgnoreCase)) return @"\\" + value.Substring(8);
            if (value.StartsWith(@"\\?\", StringComparison.OrdinalIgnoreCase)) return value.Substring(4);
            return value;
        }

        public static DirectoryIdentityReceipt InspectPlainDirectory(string expectedPath) {
            if (String.IsNullOrWhiteSpace(expectedPath) || expectedPath.IndexOf('\0') >= 0) {
                throw new ArgumentException("DIRECTORY_RECEIPT_ARGUMENT");
            }
            string expected = System.IO.Path.GetFullPath(expectedPath).TrimEnd('\\');
            IntPtr directory = CreateFileW(expected, FILE_READ_ATTRIBUTES,
                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, IntPtr.Zero, OPEN_EXISTING,
                FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS, IntPtr.Zero);
            if (directory == new IntPtr(-1)) throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateFileW(directory no-follow)");
            try {
                BY_HANDLE_FILE_INFORMATION information;
                RequireWin32(GetFileInformationByHandle(directory, out information), "GetFileInformationByHandle(directory)");
                if ((information.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) == 0 ||
                    (information.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
                    throw new InvalidOperationException("DIRECTORY_RECEIPT_NOT_PLAIN");
                }
                StringBuilder finalPath = new StringBuilder(32768);
                uint length = GetFinalPathNameByHandleW(directory, finalPath, checked((uint)finalPath.Capacity), 0);
                if (length == 0 || length >= finalPath.Capacity) throw new Win32Exception(Marshal.GetLastWin32Error(), "GetFinalPathNameByHandleW(directory)");
                string normalized = System.IO.Path.GetFullPath(NormalizeFinalPath(finalPath.ToString())).TrimEnd('\\');
                if (!String.Equals(normalized, expected, StringComparison.OrdinalIgnoreCase)) {
                    throw new InvalidOperationException("DIRECTORY_RECEIPT_PATH_MISMATCH");
                }
                string fileIndex = information.FileIndexHigh.ToString("X8", CultureInfo.InvariantCulture) +
                    information.FileIndexLow.ToString("X8", CultureInfo.InvariantCulture);
                return new DirectoryIdentityReceipt(normalized, information.FileAttributes,
                    FileTimeString(information.CreationTime), FileTimeString(information.LastWriteTime),
                    information.VolumeSerialNumber, fileIndex);
            } finally {
                CloseHandle(directory);
            }
        }

        public static ProcessTokenReceipt InspectLimitedProcess(int processId, string expectedCreationFileTime,
                string expectedUserSid, int expectedSessionId) {
            ulong parsedCreation;
            if (processId <= 0 || expectedSessionId < 0 || String.IsNullOrWhiteSpace(expectedUserSid) ||
                String.IsNullOrWhiteSpace(expectedCreationFileTime) ||
                !UInt64.TryParse(expectedCreationFileTime, NumberStyles.None, CultureInfo.InvariantCulture, out parsedCreation) ||
                parsedCreation.ToString(CultureInfo.InvariantCulture) != expectedCreationFileTime) {
                throw new ArgumentException("APP_TOKEN_PROOF_ARGUMENT");
            }
            IntPtr process = IntPtr.Zero;
            IntPtr token = IntPtr.Zero;
            try {
                process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, false, checked((uint)processId));
                if (process == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error(), "OpenProcess(app)");
                if (WaitForSingleObject(process, 0) != WAIT_TIMEOUT) throw new InvalidOperationException("APP_PROCESS_NOT_LIVE");
                string creationFileTime = ReadCreationFileTime(process);
                if (!String.Equals(creationFileTime, expectedCreationFileTime, StringComparison.Ordinal)) {
                    throw new InvalidOperationException("APP_PROCESS_IDENTITY_MISMATCH");
                }
                RequireWin32(OpenProcessToken(process, TOKEN_QUERY, out token), "OpenProcessToken(app)");
                int elevationType;
                string userSid;
                int sessionId;
                string integritySid;
                int integrityRid;
                ProveLimitedUserToken(token, expectedUserSid, expectedSessionId, out elevationType, out userSid,
                    out sessionId, out integritySid, out integrityRid);
                if (WaitForSingleObject(process, 0) != WAIT_TIMEOUT) throw new InvalidOperationException("APP_PROCESS_CHANGED_DURING_TOKEN_PROOF");
                return new ProcessTokenReceipt(processId, creationFileTime, elevationType, userSid, sessionId, integritySid, integrityRid);
            } finally {
                if (token != IntPtr.Zero) CloseHandle(token);
                if (process != IntPtr.Zero) CloseHandle(process);
            }
        }

        public static LinkedTokenLaunchReceipt RunLimitedAndWait(string applicationPath, string arguments, string workingDirectory, int timeoutMilliseconds) {
            if (String.IsNullOrWhiteSpace(applicationPath) || String.IsNullOrWhiteSpace(workingDirectory) ||
                applicationPath.IndexOf('\0') >= 0 || workingDirectory.IndexOf('\0') >= 0 ||
                applicationPath.IndexOf('"') >= 0 || timeoutMilliseconds < 1000 || timeoutMilliseconds > 30000) {
                throw new ArgumentException("UNELEVATED_LAUNCH_ARGUMENT");
            }

            IntPtr sourceToken = IntPtr.Zero;
            IntPtr linkedToken = IntPtr.Zero;
            IntPtr primaryToken = IntPtr.Zero;
            IntPtr processToken = IntPtr.Zero;
            IntPtr environment = IntPtr.Zero;
            PROCESS_INFORMATION process = new PROCESS_INFORMATION();
            bool processCompleted = false;
            try {
                RequireWin32(OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, out sourceToken), "OpenProcessToken");
                int sourceElevation = ReadElevationType(sourceToken);
                if (sourceElevation != TokenElevationTypeFull) throw new InvalidOperationException("SOURCE_TOKEN_NOT_ELEVATED_FULL");
                string sourceUserSid = ReadUserSid(sourceToken);
                int sourceSessionId = ReadSessionId(sourceToken);
                uint processSessionId;
                RequireWin32(ProcessIdToSessionId(GetCurrentProcessId(), out processSessionId), "ProcessIdToSessionId");
                if (sourceSessionId < 0 || checked((uint)sourceSessionId) != processSessionId) {
                    throw new InvalidOperationException("SOURCE_TOKEN_SESSION_MISMATCH");
                }

                TOKEN_LINKED_TOKEN linked;
                int returned;
                RequireWin32(GetLinkedToken(sourceToken, TokenLinkedToken, out linked, Marshal.SizeOf(typeof(TOKEN_LINKED_TOKEN)), out returned),
                    "GetTokenInformation(TokenLinkedToken)");
                linkedToken = linked.LinkedToken;
                if (linkedToken == IntPtr.Zero || returned != Marshal.SizeOf(typeof(TOKEN_LINKED_TOKEN))) {
                    throw new InvalidOperationException("LINKED_TOKEN_INVALID");
                }

                uint requiredAccess = TOKEN_ASSIGN_PRIMARY | TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ADJUST_DEFAULT | TOKEN_ADJUST_SESSIONID;
                RequireWin32(DuplicateTokenEx(linkedToken, requiredAccess, IntPtr.Zero, SecurityImpersonation, TokenPrimary, out primaryToken), "DuplicateTokenEx");
                int targetElevation;
                string targetUserSid;
                int targetSessionId;
                string targetIntegritySid;
                int targetIntegrityRid;
                ProveLimitedUserToken(primaryToken, sourceUserSid, sourceSessionId, out targetElevation, out targetUserSid,
                    out targetSessionId, out targetIntegritySid, out targetIntegrityRid);
                RequireWin32(CreateEnvironmentBlock(out environment, primaryToken, false), "CreateEnvironmentBlock");

                STARTUPINFO startup = new STARTUPINFO();
                startup.cb = (uint)Marshal.SizeOf(typeof(STARTUPINFO));
                StringBuilder command = new StringBuilder("\"" + applicationPath + "\" " + (arguments ?? String.Empty));
                RequireWin32(CreateProcessWithTokenW(primaryToken, LOGON_WITH_PROFILE, applicationPath, command,
                    CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW, environment, workingDirectory, ref startup, out process),
                    "CreateProcessWithTokenW");

                RequireWin32(OpenProcessToken(process.hProcess, TOKEN_QUERY, out processToken), "OpenProcessToken(unelevated helper)");
                ProveLimitedUserToken(processToken, sourceUserSid, sourceSessionId, out targetElevation, out targetUserSid,
                    out targetSessionId, out targetIntegritySid, out targetIntegrityRid);
                uint previousSuspendCount = ResumeThread(process.hThread);
                if (previousSuspendCount != 1) throw new Win32Exception(Marshal.GetLastWin32Error(), "ResumeThread(unelevated helper)");

                uint wait = WaitForSingleObject(process.hProcess, (uint)timeoutMilliseconds);
                if (wait == WAIT_TIMEOUT) {
                    RequireWin32(TerminateProcess(process.hProcess, 9), "TerminateProcess(unelevated helper)");
                    WaitForSingleObject(process.hProcess, 5000);
                    throw new TimeoutException("UNELEVATED_SHORTCUT_HELPER_TIMEOUT");
                }
                if (wait != WAIT_OBJECT_0) throw new Win32Exception(Marshal.GetLastWin32Error(), "WaitForSingleObject(unelevated helper)");
                processCompleted = true;
                uint exitCode;
                RequireWin32(GetExitCodeProcess(process.hProcess, out exitCode), "GetExitCodeProcess(unelevated helper)");
                if (exitCode != 0) throw new InvalidOperationException("UNELEVATED_SHORTCUT_HELPER_EXIT_" + exitCode.ToString());
                return new LinkedTokenLaunchReceipt(checked((int)process.dwProcessId), sourceElevation, targetElevation,
                    sourceUserSid, targetUserSid, sourceSessionId, targetSessionId, targetIntegritySid, targetIntegrityRid,
                    checked((int)exitCode));
            } finally {
                if (process.hProcess != IntPtr.Zero && !processCompleted) {
                    TerminateProcess(process.hProcess, 9);
                    WaitForSingleObject(process.hProcess, 5000);
                }
                if (process.hThread != IntPtr.Zero) CloseHandle(process.hThread);
                if (process.hProcess != IntPtr.Zero) CloseHandle(process.hProcess);
                if (environment != IntPtr.Zero) DestroyEnvironmentBlock(environment);
                if (processToken != IntPtr.Zero) CloseHandle(processToken);
                if (primaryToken != IntPtr.Zero) CloseHandle(primaryToken);
                if (linkedToken != IntPtr.Zero) CloseHandle(linkedToken);
                if (sourceToken != IntPtr.Zero) CloseHandle(sourceToken);
            }
        }
    }
}
'@ -Language CSharp -ErrorAction Stop
}

function Start-ShortcutUnelevated {
    param([string]$Name)
    $shortcut = Read-StableFile -Path $ShortcutPath
    $powershell = Read-StableFile -Path (Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe')
    Initialize-LinkedTokenLauncher

    $shortcutLiteral = $shortcut.Path.Replace("'", "''")
    $helperCommand = "`$ErrorActionPreference = 'Stop'`r`nStart-Process -FilePath '$shortcutLiteral'"
    $encodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($helperCommand))
    $arguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand ' + $encodedCommand

    $script:Sequence++
    $prefix = ('{0:D3}-{1}' -f $script:Sequence, $Name)
    $started = [DateTime]::UtcNow
    $result = [ThermoGar.P4.LinkedTokenLauncher]::RunLimitedAndWait($powershell.Path, $arguments, $InstallRoot, 15000)
    $ended = [DateTime]::UtcNow
    $record = [ordered]@{
        schema = 1; name = $Name; launch_method = 'linked_token_start_menu_shortcut'
        shortcut_sha256 = $shortcut.Sha256; helper_sha256 = $powershell.Sha256
        helper_pid = $result.ProcessId; helper_exit_code = $result.ExitCode
        source_elevation_type = $result.SourceElevationType; target_elevation_type = $result.TargetElevationType
        source_user_sid = $result.SourceUserSid; target_user_sid = $result.TargetUserSid
        source_session_id = $result.SourceSessionId; target_session_id = $result.TargetSessionId
        target_integrity_sid = $result.TargetIntegritySid; target_integrity_rid = $result.TargetIntegrityRid
        started_utc = $started.ToString('yyyy-MM-ddTHH:mm:ss.fffZ'); ended_utc = $ended.ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        duration_ms = [long]($ended - $started).TotalMilliseconds
    }
    Write-NewUtf8NoBom -Path (Join-Path $script:EvidenceRoot ($prefix + '.result.json')) -Text ($record | ConvertTo-Json -Compress -Depth 6)
    return [pscustomobject]@{
        ProcessId = $result.ProcessId; TargetElevationType = $result.TargetElevationType
        TargetUserSid = $result.TargetUserSid; TargetSessionId = $result.TargetSessionId
        TargetIntegritySid = $result.TargetIntegritySid; TargetIntegrityRid = $result.TargetIntegrityRid
    }
}

function Get-TreeReceipt {
    param([string]$Root, [bool]$AllowAbsent)
    if (-not (Test-Path -LiteralPath $Root)) {
        if ($AllowAbsent) { return [pscustomobject]@{ Present = $false; Rows = @(); RootSha256 = (Get-Sha256Hex ([byte[]]@())); FileCount = 0; DirectoryCount = 0; TotalBytes = 0L } }
        throw 'TREE_MISSING'
    }
    $normal = Assert-PlainDirectory $Root
    Initialize-LinkedTokenLauncher
    $stack = [System.Collections.Generic.Stack[string]]::new()
    $stack.Push($normal)
    $rows = [System.Collections.Generic.List[object]]::new()
    while ($stack.Count -gt 0) {
        $directory = $stack.Pop()
        $directoryIdentity = [ThermoGar.P4.LinkedTokenLauncher]::InspectPlainDirectory($directory)
        $directoryRelative = if ([string]::Equals($directory, $normal, [System.StringComparison]::OrdinalIgnoreCase)) {
            '.'
        } else {
            $directory.Substring($normal.TrimEnd('\').Length + 1).Replace('\', '/')
        }
        $rows.Add([pscustomobject]@{
            kind = 'directory'; path = $directoryRelative; attributes = [uint32]$directoryIdentity.Attributes
            creation_filetime = $directoryIdentity.CreationFileTime; last_write_filetime = $directoryIdentity.LastWriteFileTime
            volume_serial = [uint32]$directoryIdentity.VolumeSerialNumber; file_index = $directoryIdentity.FileIndex
        })
        foreach ($entry in [System.IO.Directory]::EnumerateFileSystemEntries($directory)) {
            $attributes = [System.IO.File]::GetAttributes($entry)
            if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'TREE_REPARSE' }
            if (($attributes -band [System.IO.FileAttributes]::Directory) -ne 0) { $stack.Push($entry); continue }
            $prefix = $normal.TrimEnd('\') + '\'
            if (-not $entry.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'TREE_ESCAPE' }
            $relative = $entry.Substring($prefix.Length).Replace('\', '/')
            $file = Read-StableFile $entry
            $rows.Add([pscustomobject]@{ kind = 'file'; path = $relative; bytes = $file.Bytes; sha256 = $file.Sha256 })
        }
    }
    $ordered = @($rows | Sort-Object path)
    $literals = @($ordered | ForEach-Object {
        if ($_.kind -ceq 'directory') {
            'D|{0}|{1}|{2}|{3}|{4}|{5}' -f $_.path, $_.attributes, $_.creation_filetime, $_.last_write_filetime, $_.volume_serial, $_.file_index
        } else {
            'F|{0}|{1}|{2}' -f $_.path, $_.bytes, $_.sha256
        }
    })
    $rootHash = Get-Sha256Hex ([System.Text.UTF8Encoding]::new($false).GetBytes([string]::Join("`r`n", $literals)))
    $totalBytes = [long]0
    $fileCount = 0
    $directoryCount = 0
    foreach ($row in $ordered) {
        if ($row.kind -ceq 'file') { $fileCount++; $totalBytes = [long]($totalBytes + [long]$row.bytes) }
        else { $directoryCount++ }
    }
    return [pscustomobject]@{ Present = $true; Rows = $ordered; RootSha256 = $rootHash; FileCount = $fileCount; DirectoryCount = $directoryCount; TotalBytes = $totalBytes }
}

function Save-TreeReceipt {
    param([string]$Name, [object]$Receipt)
    $object = [ordered]@{ schema = 2; root = $Name; present = $Receipt.Present; file_count = $Receipt.FileCount; directory_count = $Receipt.DirectoryCount; total_bytes = $Receipt.TotalBytes; root_sha256 = $Receipt.RootSha256; rows = $Receipt.Rows }
    Write-NewUtf8NoBom -Path (Join-Path $script:EvidenceRoot ($Name + '.json')) -Text ($object | ConvertTo-Json -Compress -Depth 8)
}

function Invoke-InstalledVerifier {
    param([string]$Name)
    $arguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -InstallRoot "{1}" -ExpectedPayloadManifestSha256 "{2}" -ExpectedDistributionEvidenceReceiptSha256 "{3}" -ExpectedPayloadRowCount {4} -ExpectedPayloadTotalBytes {5} -ExpectedPayloadRootSha256 "{6}" -ExpectedProductVersionSha256 "{7}" -ExpectedIconSha256 "{8}" -AllowInstallerControlFile' -f
        $script:Verifier.Path, $InstallRoot, $ExpectedPayloadManifestSha256.ToUpperInvariant(), $ExpectedDistributionEvidenceReceiptSha256.ToUpperInvariant(),
        $ExpectedPayloadRowCount, $ExpectedPayloadTotalBytes, $ExpectedPayloadRootSha256.ToUpperInvariant(), $ExpectedProductVersionSha256.ToUpperInvariant(), $ExpectedIconSha256.ToUpperInvariant()
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $result = Invoke-CapturedProcess -Name $Name -FilePath $powershell -Arguments $arguments -RequireZero $true
    $parsed = $result.Stdout | ConvertFrom-Json
    if ($parsed.status -cne 'INSTALLED_PAYLOAD_VERIFIED') { throw 'VERIFIER_STATUS' }
}

function Assert-OneShortcut {
    $shortcutDirectory = Split-Path -Parent $ShortcutPath
    $candidateRoots = @(
        [Environment]::GetFolderPath('CommonPrograms'), [Environment]::GetFolderPath('Programs'),
        [Environment]::GetFolderPath('CommonDesktopDirectory'), [Environment]::GetFolderPath('DesktopDirectory')
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) -and (Test-Path -LiteralPath $_ -PathType Container) } | Select-Object -Unique
    $shortcuts = @($candidateRoots | ForEach-Object { Get-ChildItem -LiteralPath $_ -Filter '*ThermoGar*.lnk' -File -Force -Recurse })
    if ($shortcuts.Count -ne 1 -or -not [string]::Equals($shortcuts[0].FullName, $ShortcutPath, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'SHORTCUT_COUNT' }
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $null
    try {
        $shortcut = $shell.CreateShortcut($ShortcutPath)
        $targetPath = [string]$shortcut.TargetPath
        $arguments = [string]$shortcut.Arguments
        $workingDirectory = [string]$shortcut.WorkingDirectory
        $iconLocation = [string]$shortcut.IconLocation
    } finally {
        if ($null -ne $shortcut) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shortcut) }
        if ($null -ne $shell) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($shell) }
    }
    $expectedTarget = Join-Path $InstallRoot 'runtime\pythonw.exe'
    $expectedArguments = '-I -B -X utf8 "' + (Join-Path $InstallRoot 'launcher.pyw') + '"'
    if (-not [string]::Equals([System.IO.Path]::GetFullPath($targetPath), $expectedTarget, [System.StringComparison]::OrdinalIgnoreCase) -or
        $arguments -cne $expectedArguments -or
        -not [string]::Equals([System.IO.Path]::GetFullPath($workingDirectory), $InstallRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $iconLocation.StartsWith((Join-Path $InstallRoot 'assets\ThermoGar.ico'), [System.StringComparison]::OrdinalIgnoreCase)) { throw 'SHORTCUT_IDENTITY' }
}

function Wait-ForOwnedHealth {
    param([object]$LaunchReceipt)
    if ($null -eq $LaunchReceipt) { throw 'LAUNCH_RECEIPT_MISSING' }
    $python = Join-Path $InstallRoot 'runtime\python.exe'
    $health = Join-Path $InstallRoot 'healthcheck.py'
    $deadline = [DateTime]::UtcNow.AddSeconds($HealthTimeoutSeconds)
    do {
        $arguments = '-I -B -X utf8 "' + $health + '" --json'
        $result = Invoke-CapturedProcess -Name 'health' -FilePath $python -Arguments $arguments -RequireZero $false
        if ($result.ExitCode -eq 0) {
            $parsed = $result.Stdout | ConvertFrom-Json
            if ($parsed.status -cne 'HEALTHY') { throw 'HEALTH_STATUS' }
            $supervisor = [ThermoGar.P4.LinkedTokenLauncher]::InspectLimitedProcess(
                [int]$parsed.supervisor_pid, [string]$parsed.supervisor_creation_filetime,
                [string]$LaunchReceipt.TargetUserSid, [int]$LaunchReceipt.TargetSessionId
            )
            $child = [ThermoGar.P4.LinkedTokenLauncher]::InspectLimitedProcess(
                [int]$parsed.child_pid, [string]$parsed.child_creation_filetime,
                [string]$LaunchReceipt.TargetUserSid, [int]$LaunchReceipt.TargetSessionId
            )
            $script:Sequence++
            $prefix = ('{0:D3}-app-token-proof' -f $script:Sequence)
            $tokenProof = [ordered]@{
                schema = 1; status = 'APP_TOKENS_MEDIUM_USER_BOUND'
                expected_user_sid = [string]$LaunchReceipt.TargetUserSid
                expected_session_id = [int]$LaunchReceipt.TargetSessionId
                helper_integrity_sid = [string]$LaunchReceipt.TargetIntegritySid
                helper_integrity_rid = [int]$LaunchReceipt.TargetIntegrityRid
                supervisor = [ordered]@{
                    pid = $supervisor.ProcessId; creation_filetime = $supervisor.CreationFileTime
                    elevation_type = $supervisor.ElevationType; user_sid = $supervisor.UserSid
                    session_id = $supervisor.SessionId; integrity_sid = $supervisor.IntegritySid; integrity_rid = $supervisor.IntegrityRid
                }
                child = [ordered]@{
                    pid = $child.ProcessId; creation_filetime = $child.CreationFileTime
                    elevation_type = $child.ElevationType; user_sid = $child.UserSid
                    session_id = $child.SessionId; integrity_sid = $child.IntegritySid; integrity_rid = $child.IntegrityRid
                }
            }
            Write-NewUtf8NoBom -Path (Join-Path $script:EvidenceRoot ($prefix + '.result.json')) -Text ($tokenProof | ConvertTo-Json -Compress -Depth 6)
            return $parsed
        }
        Start-Sleep -Seconds 1
    } while ([DateTime]::UtcNow -lt $deadline)
    throw 'HEALTH_TIMEOUT'
}

function Stop-OwnedProduct {
    $python = Join-Path $InstallRoot 'runtime\python.exe'
    $stop = Join-Path $InstallRoot 'stop.pyw'
    $arguments = '-I -B -X utf8 "' + $stop + '" --json'
    $result = Invoke-CapturedProcess -Name 'stop' -FilePath $python -Arguments $arguments -RequireZero $true
    $parsed = $result.Stdout | ConvertFrom-Json
    if ($parsed.status -cne 'STOPPED') { throw 'STOP_STATUS' }
}

function Stop-SmokeCli {
    param([string]$Detail)
    [Console]::Out.Write((([ordered]@{ schema = 1; status = 'USAGE'; detail_code = $Detail }) | ConvertTo-Json -Compress))
    exit 2
}

$InstallerPath = ''
$ExpectedInstallerSha256 = ''
$InstalledVerifierPath = ''
$ExpectedInstalledVerifierSha256 = ''
$EvidenceDirectory = ''
$ExpectedPayloadManifestSha256 = ''
$ExpectedDistributionEvidenceReceiptSha256 = ''
$ExpectedPayloadRowCount = 0
$ExpectedPayloadTotalBytes = 0L
$ExpectedPayloadRootSha256 = ''
$ExpectedProductVersionSha256 = ''
$ExpectedIconSha256 = ''
$UpgradeInstallerPath = ''
$ExpectedUpgradeInstallerSha256 = ''
$RollbackFailpointInstallerPath = ''
$ExpectedRollbackFailpointInstallerSha256 = ''
$HealthTimeoutSeconds = 30
$allowedCliNames = @(
    'InstallerPath','ExpectedInstallerSha256','InstalledVerifierPath','ExpectedInstalledVerifierSha256','EvidenceDirectory',
    'ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedPayloadRowCount','ExpectedPayloadTotalBytes',
    'ExpectedPayloadRootSha256','ExpectedProductVersionSha256','ExpectedIconSha256','UpgradeInstallerPath',
    'ExpectedUpgradeInstallerSha256','RollbackFailpointInstallerPath','ExpectedRollbackFailpointInstallerSha256','HealthTimeoutSeconds'
)
$seenCliNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
for ($cliIndex = 0; $cliIndex -lt $RawCliArguments.Count; $cliIndex++) {
    $token = [string]$RawCliArguments[$cliIndex]
    if ($token.Length -lt 2 -or $token[0] -cne '-') { Stop-SmokeCli 'POSITIONAL_ARGUMENT_REJECTED' }
    $name = $token.Substring(1)
    if (-not ($allowedCliNames -ccontains $name)) { Stop-SmokeCli 'UNKNOWN_OR_ABBREVIATED_PARAMETER' }
    if (-not $seenCliNames.Add($name)) { Stop-SmokeCli 'DUPLICATE_PARAMETER' }
    $cliIndex++
    if ($cliIndex -ge $RawCliArguments.Count) { Stop-SmokeCli ('MISSING_VALUE_' + $name.ToUpperInvariant()) }
    $value = [string]$RawCliArguments[$cliIndex]
    if ($value.StartsWith('-', [System.StringComparison]::Ordinal)) { Stop-SmokeCli ('MISSING_VALUE_' + $name.ToUpperInvariant()) }
    if ($name -ceq 'ExpectedPayloadRowCount') {
        $parsedInt = 0
        if (-not [int]::TryParse($value, [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsedInt) -or
            $parsedInt -lt 1 -or $parsedInt -gt 1000000) { Stop-SmokeCli 'INVALID_EXPECTEDPAYLOADROWCOUNT' }
        $ExpectedPayloadRowCount = $parsedInt
    } elseif ($name -ceq 'ExpectedPayloadTotalBytes') {
        $parsedLong = 0L
        if (-not [long]::TryParse($value, [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsedLong) -or
            $parsedLong -lt 1) { Stop-SmokeCli 'INVALID_EXPECTEDPAYLOADTOTALBYTES' }
        $ExpectedPayloadTotalBytes = $parsedLong
    } elseif ($name -ceq 'HealthTimeoutSeconds') {
        $parsedHealth = 0
        if (-not [int]::TryParse($value, [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsedHealth) -or
            $parsedHealth -lt 5 -or $parsedHealth -gt 60) { Stop-SmokeCli 'INVALID_HEALTHTIMEOUTSECONDS' }
        $HealthTimeoutSeconds = $parsedHealth
    } else {
        Set-Variable -Name $name -Value $value
    }
}
$requiredCliNames = @(
    'InstallerPath','ExpectedInstallerSha256','InstalledVerifierPath','ExpectedInstalledVerifierSha256','EvidenceDirectory',
    'ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedPayloadRootSha256',
    'ExpectedProductVersionSha256','ExpectedIconSha256'
)
foreach ($requiredName in $requiredCliNames) {
    if ([string]::IsNullOrWhiteSpace([string](Get-Variable -Name $requiredName -ValueOnly))) {
        Stop-SmokeCli ('MISSING_' + $requiredName.ToUpperInvariant())
    }
}
if ($ExpectedPayloadRowCount -lt 1 -or $ExpectedPayloadTotalBytes -lt 1) { Stop-SmokeCli 'PAYLOAD_PINS_REQUIRED' }
foreach ($hashName in @(
    'ExpectedInstallerSha256','ExpectedInstalledVerifierSha256','ExpectedPayloadManifestSha256',
    'ExpectedDistributionEvidenceReceiptSha256','ExpectedPayloadRootSha256','ExpectedProductVersionSha256','ExpectedIconSha256'
)) {
    if ([string](Get-Variable -Name $hashName -ValueOnly) -notmatch '^[0-9A-Fa-f]{64}$') {
        Stop-SmokeCli ('INVALID_' + $hashName.ToUpperInvariant())
    }
}
foreach ($optionalHashName in @('ExpectedUpgradeInstallerSha256','ExpectedRollbackFailpointInstallerSha256')) {
    $optionalHash = [string](Get-Variable -Name $optionalHashName -ValueOnly)
    if (-not [string]::IsNullOrEmpty($optionalHash) -and $optionalHash -notmatch '^[0-9A-Fa-f]{64}$') {
        Stop-SmokeCli ('INVALID_' + $optionalHashName.ToUpperInvariant())
    }
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'ELEVATION_REQUIRED' }

    $installer = Read-StableFile -Path $InstallerPath -ExpectedSha256 $ExpectedInstallerSha256
    $script:Verifier = Read-StableFile -Path $InstalledVerifierPath -ExpectedSha256 $ExpectedInstalledVerifierSha256
    if (-not [string]::IsNullOrWhiteSpace($UpgradeInstallerPath) -and [string]::IsNullOrWhiteSpace($ExpectedUpgradeInstallerSha256)) { throw 'UPGRADE_INSTALLER_PIN_REQUIRED' }
    if (-not [string]::IsNullOrWhiteSpace($RollbackFailpointInstallerPath) -and [string]::IsNullOrWhiteSpace($ExpectedRollbackFailpointInstallerSha256)) { throw 'ROLLBACK_INSTALLER_PIN_REQUIRED' }
    $upgradeInstaller = if ([string]::IsNullOrWhiteSpace($UpgradeInstallerPath)) { $installer } else { Read-StableFile -Path $UpgradeInstallerPath -ExpectedSha256 $ExpectedUpgradeInstallerSha256 }
    $rollbackInstaller = if ([string]::IsNullOrWhiteSpace($RollbackFailpointInstallerPath)) { $null } else { Read-StableFile -Path $RollbackFailpointInstallerPath -ExpectedSha256 $ExpectedRollbackFailpointInstallerSha256 }
    if ((Test-Path -LiteralPath $InstallRoot) -or (Test-Path -LiteralPath $ShortcutPath) -or (Test-Path -LiteralPath $UninstallKey)) {
        throw 'INSTALL_TARGET_NOT_CLEAN'
    }

    $evidenceParent = Split-Path -Parent ([System.IO.Path]::GetFullPath($EvidenceDirectory))
    [void](Assert-PlainDirectory $evidenceParent)
    if (Test-Path -LiteralPath $EvidenceDirectory) { throw 'EVIDENCE_EXISTS' }
    $script:EvidenceRoot = [System.IO.Path]::GetFullPath($EvidenceDirectory)
    [void][System.IO.Directory]::CreateDirectory($script:EvidenceRoot)
    [void](Assert-PlainDirectory $script:EvidenceRoot)
    if ([string]::Equals($script:EvidenceRoot, $InstallRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals($script:EvidenceRoot, $ProfileRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $script:EvidenceRoot.StartsWith($InstallRoot + '\', [System.StringComparison]::OrdinalIgnoreCase) -or
        $script:EvidenceRoot.StartsWith($ProfileRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'EVIDENCE_SCOPE' }

    $preProfile = Get-TreeReceipt -Root $ProfileRoot -AllowAbsent $true
    Save-TreeReceipt 'profile-before-install' $preProfile

    [void](Invoke-CapturedProcess -Name 'install-v1' -FilePath $installer.Path -Arguments '/S' -RequireZero $true)
    Invoke-InstalledVerifier 'verify-after-install'
    Assert-OneShortcut
    $installBaseline = Get-TreeReceipt -Root $InstallRoot -AllowAbsent $false
    Save-TreeReceipt 'install-baseline' $installBaseline

    $installLaunch = Start-ShortcutUnelevated -Name 'launch-after-install'
    [void](Wait-ForOwnedHealth -LaunchReceipt $installLaunch)

    $runningUpgrade = Invoke-CapturedProcess -Name 'upgrade-running-refusal' -FilePath $upgradeInstaller.Path -Arguments '/S' -RequireZero $false
    if ($runningUpgrade.ExitCode -eq 0) { throw 'RUNNING_UPGRADE_NOT_REFUSED' }
    $runningSnapshot = Get-TreeReceipt -Root $InstallRoot -AllowAbsent $false
    Save-TreeReceipt 'install-after-running-upgrade-refusal' $runningSnapshot
    if ($runningSnapshot.RootSha256 -cne $installBaseline.RootSha256) { throw 'RUNNING_UPGRADE_MUTATED_INSTALL' }
    [void](Wait-ForOwnedHealth -LaunchReceipt $installLaunch)

    Stop-OwnedProduct
    $afterStop = Get-TreeReceipt -Root $InstallRoot -AllowAbsent $false
    Save-TreeReceipt 'install-after-stop' $afterStop
    if ($afterStop.RootSha256 -cne $installBaseline.RootSha256) { throw 'PROGRAM_FILES_MUTATED' }

    if ($null -ne $rollbackInstaller) {
        $profileBeforeRollback = Get-TreeReceipt -Root $ProfileRoot -AllowAbsent $false
        $rollbackResult = Invoke-CapturedProcess -Name 'upgrade-controlled-rollback' -FilePath $rollbackInstaller.Path -Arguments '/S' -RequireZero $false
        if ($rollbackResult.ExitCode -eq 0) { throw 'ROLLBACK_FAILPOINT_DID_NOT_FAIL' }
        Invoke-InstalledVerifier 'verify-after-controlled-rollback'
        $afterRollback = Get-TreeReceipt -Root $InstallRoot -AllowAbsent $false
        Save-TreeReceipt 'install-after-controlled-rollback' $afterRollback
        if ($afterRollback.RootSha256 -cne $installBaseline.RootSha256) { throw 'ROLLBACK_DID_NOT_RESTORE_INSTALL' }
        $profileAfterRollback = Get-TreeReceipt -Root $ProfileRoot -AllowAbsent $false
        if ($profileAfterRollback.RootSha256 -cne $profileBeforeRollback.RootSha256) { throw 'ROLLBACK_MUTATED_PROFILE' }
    }

    [void](Invoke-CapturedProcess -Name 'upgrade-stopped' -FilePath $upgradeInstaller.Path -Arguments '/S' -RequireZero $true)
    Invoke-InstalledVerifier 'verify-after-stopped-upgrade'
    Assert-OneShortcut
    $afterUpgrade = Get-TreeReceipt -Root $InstallRoot -AllowAbsent $false
    Save-TreeReceipt 'install-after-stopped-upgrade' $afterUpgrade

    $upgradeLaunch = Start-ShortcutUnelevated -Name 'launch-after-upgrade'
    [void](Wait-ForOwnedHealth -LaunchReceipt $upgradeLaunch)
    Stop-OwnedProduct

    $profileBeforeUninstall = Get-TreeReceipt -Root $ProfileRoot -AllowAbsent $false
    Save-TreeReceipt 'profile-before-uninstall' $profileBeforeUninstall
    $uninstaller = Read-StableFile -Path (Join-Path $InstallRoot 'uninstall.exe')
    [void](Invoke-CapturedProcess -Name 'uninstall' -FilePath $uninstaller.Path -Arguments '/S' -RequireZero $true)
    if ((Test-Path -LiteralPath $InstallRoot) -or (Test-Path -LiteralPath $ShortcutPath) -or (Test-Path -LiteralPath $UninstallKey)) { throw 'UNINSTALL_SCOPE_INCOMPLETE' }
    $profileAfterUninstall = Get-TreeReceipt -Root $ProfileRoot -AllowAbsent $false
    Save-TreeReceipt 'profile-after-uninstall' $profileAfterUninstall
    if ($profileAfterUninstall.RootSha256 -cne $profileBeforeUninstall.RootSha256 -or
        $profileAfterUninstall.FileCount -ne $profileBeforeUninstall.FileCount -or
        $profileAfterUninstall.DirectoryCount -ne $profileBeforeUninstall.DirectoryCount) { throw 'PROFILE_MUTATED_BY_UNINSTALL' }

    [void](Invoke-CapturedProcess -Name 'reinstall' -FilePath $upgradeInstaller.Path -Arguments '/S' -RequireZero $true)
    Invoke-InstalledVerifier 'verify-after-reinstall'
    Assert-OneShortcut
    if (-not (Test-Path -LiteralPath $ProfileRoot -PathType Container)) { throw 'PROFILE_NOT_RECOVERED' }
    $reinstallLaunch = Start-ShortcutUnelevated -Name 'launch-after-reinstall'
    [void](Wait-ForOwnedHealth -LaunchReceipt $reinstallLaunch)
    Stop-OwnedProduct

    $summary = [ordered]@{
        schema = 1; status = 'P4_LOCAL_CLEAN_SMOKE_PASSED'; installer_sha256 = $installer.Sha256; upgrade_installer_sha256 = $upgradeInstaller.Sha256
        payload_manifest_sha256 = $ExpectedPayloadManifestSha256.ToUpperInvariant(); payload_root_sha256 = $ExpectedPayloadRootSha256.ToUpperInvariant()
        one_shortcut = $true; running_upgrade_refused = $true; controlled_rollback_tested = ($null -ne $rollbackInstaller)
        program_files_immutable = $true; local_app_data_preserved = $true; profile_directory_identity_preserved = $true
        application_launch_integrity = 'medium_linked_token_and_actual_app_tokens'
        reinstalled = $true; clean_host_claim = $false
    }
    $summaryPath = Join-Path $script:EvidenceRoot 'smoke-summary.json'
    Write-NewUtf8NoBom -Path $summaryPath -Text ($summary | ConvertTo-Json -Compress -Depth 6)
    [Console]::Out.Write(($summary | ConvertTo-Json -Compress -Depth 6))
    exit 0
} catch {
    $detail = [string]$_.Exception.Message
    if ($null -ne $script:EvidenceRoot -and (Test-Path -LiteralPath $script:EvidenceRoot)) {
        try { Write-NewUtf8NoBom -Path (Join-Path $script:EvidenceRoot 'smoke-failure.json') -Text (([ordered]@{ schema = 1; status = 'P4_LOCAL_CLEAN_SMOKE_FAILED'; detail_code = $detail }) | ConvertTo-Json -Compress) }
        catch { }
    }
    [Console]::Out.Write((([ordered]@{ schema = 1; status = 'P4_LOCAL_CLEAN_SMOKE_FAILED'; detail_code = $detail }) | ConvertTo-Json -Compress))
    exit 1
}
