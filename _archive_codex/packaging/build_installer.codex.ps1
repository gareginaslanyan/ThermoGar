#requires -Version 5.1
$RawCliArguments = @($args)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$FixedNsisPath = 'C:\Program Files (x86)\NSIS\makensis.exe'
$FixedNsisBytes = 2560L
$FixedNsisSha256 = 'B043E554AFEFBFC56315669D0B4779793AEAE67F0F2A7A790E2EA91F05298EFF'
$FixedProductVersionBytes = 586L
$FixedProductVersionSha256 = '5FFD94AD3CC5A471211A8CC718540E5267D4F9DFA5E345035FBD5780587DF54D'
$FixedIconBytes = 46084L
$FixedIconSha256 = '7D685F896D6BE7D3DB0E16E1B024F58B270F9C48F88C45002CFB2B6C56F38039'
$FixedReleasePolicySha256 = 'E818F1AAA03B2218856E8F75EAD1D864C612B35F7528A7CC98EF6607288B2290'
$IconSizes = @(16, 20, 24, 32, 40, 48, 64, 256)

function Write-CompactJsonAndExit {
    param([Parameter(Mandatory = $true)][System.Collections.IDictionary]$Object, [Parameter(Mandatory = $true)][int]$Code)
    [Console]::Out.Write(($Object | ConvertTo-Json -Compress -Depth 12))
    exit $Code
}

function Stop-Build {
    param([int]$Code, [string]$Status, [string]$Detail)
    Write-CompactJsonAndExit -Object ([ordered]@{ schema = 1; status = $Status; detail_code = $Detail }) -Code $Code
}

function Get-Sha256Hex {
    param([byte[]]$Bytes)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return -join ($algorithm.ComputeHash($Bytes) | ForEach-Object { $_.ToString('X2') }) }
    finally { $algorithm.Dispose() }
}

function Get-NormalAbsolutePath {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path) -or -not [System.IO.Path]::IsPathRooted($Path)) { throw 'PATH_NOT_ABSOLUTE' }
    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    if ($full.IndexOf([char]0) -ge 0) { throw 'PATH_NUL' }
    return $full
}

function Assert-PlainAncestors {
    param([string]$Path, [bool]$RequireLeaf)
    $full = Get-NormalAbsolutePath $Path
    $cursor = if ($RequireLeaf) { $full } else { Split-Path -Parent $full }
    while (-not [string]::IsNullOrEmpty($cursor)) {
        if (-not (Test-Path -LiteralPath $cursor)) { throw 'ANCESTOR_MISSING' }
        $item = Get-Item -LiteralPath $cursor -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'REPARSE_POINT' }
        $parent = Split-Path -Parent $cursor
        if ([string]::Equals($parent, $cursor, [System.StringComparison]::OrdinalIgnoreCase)) { break }
        $cursor = $parent
    }
    return $full
}

function Read-StableBytes {
    param([string]$Path, [long]$ExpectedBytes = -1, [string]$ExpectedSha256 = '')
    $full = Assert-PlainAncestors -Path $Path -RequireLeaf $true
    $item = Get-Item -LiteralPath $full -Force
    if (-not ($item -is [System.IO.FileInfo]) -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'NOT_PLAIN_FILE' }
    $alternateStreams = @(Get-Item -LiteralPath $full -Stream * -ErrorAction Stop | Where-Object { $_.Stream -cne ':$DATA' })
    if ($alternateStreams.Count -ne 0) { throw 'ALTERNATE_DATA_STREAM' }
    if ($ExpectedBytes -ge 0 -and $item.Length -ne $ExpectedBytes) { throw 'BYTE_COUNT' }
    $first = [System.IO.File]::ReadAllBytes($full)
    $firstHash = Get-Sha256Hex $first
    $second = [System.IO.File]::ReadAllBytes($full)
    $secondHash = Get-Sha256Hex $second
    if ($first.LongLength -ne $second.LongLength -or $firstHash -cne $secondHash) { throw 'UNSTABLE_FILE' }
    if (-not [string]::IsNullOrEmpty($ExpectedSha256) -and $firstHash -cne $ExpectedSha256.ToUpperInvariant()) { throw 'HASH_MISMATCH' }
    return [pscustomobject]@{ Path = $full; Bytes = $first; Length = $first.LongLength; Sha256 = $firstHash }
}

function Write-NewUtf8NoBom {
    param([string]$Path, [string]$Text)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Text)
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
}

function Initialize-OwnedPathType {
    if ('ThermoGar.P4.OwnedPath' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace ThermoGar.P4 {
    // A live instance is the authority for the exact filesystem object. Public
    // rollback never reopens a mutable path after publication.
    public sealed class OwnedPath : IDisposable {
        const uint DELETE_ACCESS = 0x00010000;
        const uint SYNCHRONIZE = 0x00100000;
        const uint FILE_LIST_DIRECTORY = 0x00000001;
        const uint FILE_ADD_FILE = 0x00000002;
        const uint FILE_ADD_SUBDIRECTORY = 0x00000004;
        const uint FILE_TRAVERSE = 0x00000020;
        const uint FILE_READ_ATTRIBUTES = 0x00000080;
        const uint GENERIC_READ = 0x80000000;
        const uint FILE_SHARE_READ = 0x00000001;
        const uint FILE_SHARE_WRITE = 0x00000002;
        const uint OPEN_EXISTING = 3;
        const uint FILE_ATTRIBUTE_NORMAL = 0x00000080;
        const uint FILE_ATTRIBUTE_DIRECTORY = 0x00000010;
        const uint FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400;
        const uint FILE_FLAG_BACKUP_SEMANTICS = 0x02000000;
        const uint FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000;
        const uint OBJ_CASE_INSENSITIVE = 0x00000040;
        const uint FILE_CREATE = 2;
        const uint FILE_OPEN = 1;
        const uint FILE_DIRECTORY_FILE = 0x00000001;
        const uint FILE_NON_DIRECTORY_FILE = 0x00000040;
        const uint FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020;
        const int FileAttributeTagInfo = 9;
        const int FileRenameInfo = 3;
        const int FileDispositionInfo = 4;

        [StructLayout(LayoutKind.Sequential)]
        struct UNICODE_STRING {
            public ushort Length;
            public ushort MaximumLength;
            public IntPtr Buffer;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct OBJECT_ATTRIBUTES {
            public int Length;
            public IntPtr RootDirectory;
            public IntPtr ObjectName;
            public uint Attributes;
            public IntPtr SecurityDescriptor;
            public IntPtr SecurityQualityOfService;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct IO_STATUS_BLOCK {
            public IntPtr Status;
            public UIntPtr Information;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct FILE_ATTRIBUTE_TAG_INFO {
            public uint FileAttributes;
            public uint ReparseTag;
        }

        [DllImport("ntdll.dll")]
        static extern int NtCreateFile(out IntPtr fileHandle, uint desiredAccess,
            ref OBJECT_ATTRIBUTES objectAttributes, out IO_STATUS_BLOCK ioStatusBlock,
            IntPtr allocationSize, uint fileAttributes, uint shareAccess,
            uint createDisposition, uint createOptions, IntPtr eaBuffer, uint eaLength);

        [DllImport("ntdll.dll")]
        static extern int NtSetInformationFile(SafeFileHandle file,
            out IO_STATUS_BLOCK ioStatusBlock, IntPtr information,
            uint bufferSize, int informationClass);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern SafeFileHandle CreateFileW(string fileName, uint desiredAccess,
            uint shareMode, IntPtr securityAttributes, uint creationDisposition,
            uint flagsAndAttributes, IntPtr templateFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool SetFileInformationByHandle(SafeFileHandle file,
            int informationClass, IntPtr information, uint bufferSize);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetFileInformationByHandleEx(SafeFileHandle file,
            int informationClass, out FILE_ATTRIBUTE_TAG_INFO information,
            uint bufferSize);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetFileSizeEx(SafeFileHandle file, out long size);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool ReadFile(SafeFileHandle file, byte[] buffer,
            uint bytesToRead, out uint bytesRead, IntPtr overlapped);

        SafeFileHandle handle;
        bool released;
        bool directory;

        public long Length { get; private set; }
        public string Sha256 { get; private set; }

        OwnedPath(SafeFileHandle ownedHandle, bool isDirectory) {
            handle = ownedHandle;
            directory = isDirectory;
            Length = -1;
            Sha256 = String.Empty;
        }

        public static OwnedPath OpenDirectoryGuard(string path) {
            SafeFileHandle opened = CreateFileW(Path.GetFullPath(path),
                SYNCHRONIZE | FILE_LIST_DIRECTORY | FILE_ADD_FILE |
                FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE | FILE_READ_ATTRIBUTES,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                IntPtr.Zero, OPEN_EXISTING,
                FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
                IntPtr.Zero);
            if (opened.IsInvalid) {
                int error = Marshal.GetLastWin32Error();
                opened.Dispose();
                throw new Win32Exception(error, "OPEN_OUTPUT_DIRECTORY");
            }
            try {
                ValidateKind(opened, true);
                return new OwnedPath(opened, true);
            } catch { opened.Dispose(); throw; }
        }

        public static OwnedPath CreateDirectoryNew(OwnedPath parent, string leaf) {
            parent.EnsureDirectory();
            ValidateLeaf(leaf);
            IntPtr text = IntPtr.Zero;
            IntPtr unicodePointer = IntPtr.Zero;
            try {
                text = Marshal.StringToHGlobalUni(leaf);
                UNICODE_STRING unicode = new UNICODE_STRING {
                    Length = checked((ushort)(leaf.Length * 2)),
                    MaximumLength = checked((ushort)((leaf.Length + 1) * 2)),
                    Buffer = text
                };
                unicodePointer = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(UNICODE_STRING)));
                Marshal.StructureToPtr(unicode, unicodePointer, false);
                OBJECT_ATTRIBUTES attributes = new OBJECT_ATTRIBUTES {
                    Length = Marshal.SizeOf(typeof(OBJECT_ATTRIBUTES)),
                    RootDirectory = parent.handle.DangerousGetHandle(),
                    ObjectName = unicodePointer, Attributes = OBJ_CASE_INSENSITIVE,
                    SecurityDescriptor = IntPtr.Zero, SecurityQualityOfService = IntPtr.Zero
                };
                IO_STATUS_BLOCK io;
                IntPtr raw;
                int status = NtCreateFile(out raw,
                    DELETE_ACCESS | SYNCHRONIZE | FILE_LIST_DIRECTORY |
                    FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE |
                    FILE_READ_ATTRIBUTES,
                    ref attributes, out io, IntPtr.Zero, FILE_ATTRIBUTE_NORMAL,
                    FILE_SHARE_READ | FILE_SHARE_WRITE, FILE_CREATE,
                    FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT,
                    IntPtr.Zero, 0);
                GC.KeepAlive(parent);
                if (status != 0 || io.Information.ToUInt64() != 2 ||
                    raw == IntPtr.Zero || raw == new IntPtr(-1)) {
                    if (raw != IntPtr.Zero && raw != new IntPtr(-1)) {
                        new SafeFileHandle(raw, true).Dispose();
                    }
                    throw new IOException("NT_CREATE_DIRECTORY_0x" + unchecked((uint)status).ToString("X8"));
                }
                SafeFileHandle created = new SafeFileHandle(raw, true);
                try {
                    ValidateKind(created, true);
                    return new OwnedPath(created, true);
                } catch { created.Dispose(); throw; }
            } finally {
                if (unicodePointer != IntPtr.Zero) Marshal.FreeHGlobal(unicodePointer);
                if (text != IntPtr.Zero) Marshal.FreeHGlobal(text);
            }
        }

        public static OwnedPath OpenVerifiedFileForRename(OwnedPath parent,
            string leaf, long expectedLength, string expectedSha256, bool requireMz) {
            parent.EnsureDirectory();
            ValidateLeaf(leaf);
            IntPtr text = IntPtr.Zero;
            IntPtr unicodePointer = IntPtr.Zero;
            try {
                text = Marshal.StringToHGlobalUni(leaf);
                UNICODE_STRING unicode = new UNICODE_STRING {
                    Length = checked((ushort)(leaf.Length * 2)),
                    MaximumLength = checked((ushort)((leaf.Length + 1) * 2)),
                    Buffer = text
                };
                unicodePointer = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(UNICODE_STRING)));
                Marshal.StructureToPtr(unicode, unicodePointer, false);
                OBJECT_ATTRIBUTES attributes = new OBJECT_ATTRIBUTES {
                    Length = Marshal.SizeOf(typeof(OBJECT_ATTRIBUTES)),
                    RootDirectory = parent.handle.DangerousGetHandle(),
                    ObjectName = unicodePointer, Attributes = OBJ_CASE_INSENSITIVE,
                    SecurityDescriptor = IntPtr.Zero, SecurityQualityOfService = IntPtr.Zero
                };
                IO_STATUS_BLOCK io;
                IntPtr raw;
                int status = NtCreateFile(out raw,
                    GENERIC_READ | DELETE_ACCESS | SYNCHRONIZE | FILE_READ_ATTRIBUTES,
                    ref attributes, out io, IntPtr.Zero, FILE_ATTRIBUTE_NORMAL,
                    0, FILE_OPEN,
                    FILE_NON_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT |
                    FILE_FLAG_OPEN_REPARSE_POINT,
                    IntPtr.Zero, 0);
                GC.KeepAlive(parent);
                if (status != 0 || io.Information.ToUInt64() != 1 ||
                    raw == IntPtr.Zero || raw == new IntPtr(-1)) {
                    if (raw != IntPtr.Zero && raw != new IntPtr(-1)) {
                        new SafeFileHandle(raw, true).Dispose();
                    }
                    throw new IOException("NT_OPEN_FILE_0x" + unchecked((uint)status).ToString("X8"));
                }
                SafeFileHandle opened = new SafeFileHandle(raw, true);
                try {
                    ValidateKind(opened, false);
                    OwnedPath owned = new OwnedPath(opened, false);
                    owned.ReadAndVerify(expectedLength, expectedSha256, requireMz);
                    return owned;
                } catch { opened.Dispose(); throw; }
            } finally {
                if (unicodePointer != IntPtr.Zero) Marshal.FreeHGlobal(unicodePointer);
                if (text != IntPtr.Zero) Marshal.FreeHGlobal(text);
            }
        }

        public void RenameNoReplace(OwnedPath destinationDirectory, string leaf) {
            EnsureLive();
            if (directory) throw new InvalidOperationException("SOURCE_IS_DIRECTORY");
            destinationDirectory.EnsureDirectory();
            ValidateLeaf(leaf);
            byte[] name = Encoding.Unicode.GetBytes(leaf);
            int rootOffset = IntPtr.Size == 8 ? 8 : 4;
            int lengthOffset = rootOffset + IntPtr.Size;
            int nameOffset = lengthOffset + 4;
            int total = checked(nameOffset + name.Length + 2);
            IntPtr buffer = Marshal.AllocHGlobal(total);
            try {
                for (int index = 0; index < total; index++) Marshal.WriteByte(buffer, index, 0);
                Marshal.WriteIntPtr(buffer, rootOffset, destinationDirectory.handle.DangerousGetHandle());
                Marshal.WriteInt32(buffer, lengthOffset, name.Length);
                Marshal.Copy(name, 0, IntPtr.Add(buffer, nameOffset), name.Length);
                IO_STATUS_BLOCK io;
                int status = NtSetInformationFile(handle, out io, buffer, (uint)total, 10);
                GC.KeepAlive(destinationDirectory);
                if (status != 0) {
                    throw new IOException("NT_RENAME_0x" + unchecked((uint)status).ToString("X8"));
                }
            } finally { Marshal.FreeHGlobal(buffer); }
        }

        public void DeleteExact() {
            EnsureLive();
            IntPtr disposition = Marshal.AllocHGlobal(1);
            try {
                Marshal.WriteByte(disposition, 0, 1);
                if (!SetFileInformationByHandle(handle, FileDispositionInfo, disposition, 1)) {
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "DELETE_EXACT");
                }
            } finally { Marshal.FreeHGlobal(disposition); }
            Release();
        }

        public void Release() {
            if (released) return;
            handle.Dispose();
            released = true;
        }

        void EnsureLive() {
            if (released || handle == null || handle.IsInvalid || handle.IsClosed) {
                throw new ObjectDisposedException("OwnedPath");
            }
        }

        void EnsureDirectory() {
            EnsureLive();
            if (!directory) throw new InvalidOperationException("NOT_DIRECTORY_HANDLE");
        }

        static void ValidateLeaf(string leaf) {
            if (String.IsNullOrWhiteSpace(leaf) || leaf == "." || leaf == ".." ||
                leaf.IndexOfAny(new char[] { '\\', '/', ':', '\0' }) >= 0 ||
                !String.Equals(Path.GetFileName(leaf), leaf, StringComparison.Ordinal)) {
                throw new ArgumentException("INVALID_RELATIVE_LEAF");
            }
        }

        static void ValidateKind(SafeFileHandle file, bool expectDirectory) {
            FILE_ATTRIBUTE_TAG_INFO info;
            if (!GetFileInformationByHandleEx(file, FileAttributeTagInfo, out info,
                (uint)Marshal.SizeOf(typeof(FILE_ATTRIBUTE_TAG_INFO)))) {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "FILE_ATTRIBUTE_TAG_INFO");
            }
            bool isDirectory = (info.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0;
            if ((info.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0 ||
                isDirectory != expectDirectory) {
                throw new IOException("REPARSE_OR_KIND_MISMATCH");
            }
        }

        void ReadAndVerify(long expectedLength, string expectedSha256, bool requireMz) {
            long size;
            if (!GetFileSizeEx(handle, out size) || size < 0) {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "GET_FILE_SIZE");
            }
            if (expectedLength >= 0 && size != expectedLength) throw new IOException("BYTE_COUNT");
            byte[] buffer = new byte[65536];
            long remaining = size;
            long offset = 0;
            byte first = 0, second = 0;
            using (SHA256 hash = SHA256.Create()) {
                while (remaining > 0) {
                    uint requested = (uint)Math.Min((long)buffer.Length, remaining);
                    uint read;
                    if (!ReadFile(handle, buffer, requested, out read, IntPtr.Zero) || read == 0) {
                        throw new Win32Exception(Marshal.GetLastWin32Error(), "READ_EXACT_FILE");
                    }
                    if (offset == 0) {
                        first = buffer[0];
                        if (read > 1) second = buffer[1];
                    } else if (offset == 1) { second = buffer[0]; }
                    hash.TransformBlock(buffer, 0, (int)read, null, 0);
                    offset += read;
                    remaining -= read;
                }
                hash.TransformFinalBlock(new byte[0], 0, 0);
                Sha256 = BitConverter.ToString(hash.Hash).Replace("-", String.Empty);
            }
            Length = size;
            if (!String.IsNullOrEmpty(expectedSha256) &&
                !String.Equals(Sha256, expectedSha256, StringComparison.OrdinalIgnoreCase)) {
                throw new IOException("HASH_MISMATCH");
            }
            if (requireMz && (size < 2 || first != 0x4D || second != 0x5A)) {
                throw new IOException("INSTALLER_NOT_PE");
            }
        }

        public void Dispose() { Release(); }
    }
}
'@
}

function Get-RootSha256 {
    param([string[]]$Rows)
    return Get-Sha256Hex ([System.Text.UTF8Encoding]::new($false).GetBytes([string]::Join("`r`n", $Rows)))
}

function Convert-ToNsisLiteral {
    param([string]$Value)
    if ($Value.IndexOfAny([char[]]"`0`r`n") -ge 0) { throw 'NSIS_LITERAL_CONTROL' }
    return $Value.Replace('$', '$$').Replace('"', '$\"')
}

function Assert-IcoStructure {
    param([byte[]]$Bytes)
    if ($Bytes.Length -lt 6) { throw 'ICO_SHORT' }
    $reserved = [BitConverter]::ToUInt16($Bytes, 0)
    $type = [BitConverter]::ToUInt16($Bytes, 2)
    $count = [BitConverter]::ToUInt16($Bytes, 4)
    if ($reserved -ne 0 -or $type -ne 1 -or $count -ne $IconSizes.Count -or $Bytes.Length -lt (6 + 16 * $count)) { throw 'ICO_HEADER' }
    $ranges = [System.Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $count; $index++) {
        $offset = 6 + 16 * $index
        $width = if ($Bytes[$offset] -eq 0) { 256 } else { [int]$Bytes[$offset] }
        $height = if ($Bytes[$offset + 1] -eq 0) { 256 } else { [int]$Bytes[$offset + 1] }
        $bits = [BitConverter]::ToUInt16($Bytes, $offset + 6)
        $size = [BitConverter]::ToUInt32($Bytes, $offset + 8)
        $imageOffset = [BitConverter]::ToUInt32($Bytes, $offset + 12)
        if ($width -ne $IconSizes[$index] -or $height -ne $IconSizes[$index] -or $bits -ne 32 -or $size -eq 0 -or
            $imageOffset -lt (6 + 16 * $count) -or ([long]$imageOffset + [long]$size) -gt $Bytes.LongLength) { throw 'ICO_ENTRY' }
        $ranges.Add([pscustomobject]@{ Start = [long]$imageOffset; End = [long]$imageOffset + [long]$size })
    }
    $ordered = @($ranges | Sort-Object Start)
    for ($index = 1; $index -lt $ordered.Count; $index++) {
        if ($ordered[$index].Start -lt $ordered[$index - 1].End) { throw 'ICO_OVERLAP' }
    }
}

function Invoke-UpgradePreflight {
    param([string]$Root)
    try {
        $normalRoot = Get-NormalAbsolutePath $Root
        if (Test-Path -LiteralPath $normalRoot) { [void](Assert-PlainAncestors -Path $normalRoot -RequireLeaf $true) }
    } catch {
        Write-CompactJsonAndExit -Object ([ordered]@{ schema = 1; status = 'REFUSE_UPGRADE'; detail_code = 20 }) -Code 20
    }

    if (-not ('ThermoGar.P4.ProcessGuard' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;

namespace ThermoGar.P4 {
    public static class ProcessGuard {
        const uint TH32CS_SNAPPROCESS = 0x00000002;
        const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
        const uint SYNCHRONIZE = 0x00100000;
        static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        struct PROCESSENTRY32 {
            public uint dwSize;
            public uint cntUsage;
            public uint th32ProcessID;
            public IntPtr th32DefaultHeapID;
            public uint th32ModuleID;
            public uint cntThreads;
            public uint th32ParentProcessID;
            public int pcPriClassBase;
            public uint dwFlags;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szExeFile;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct FILETIME { public uint Low; public uint High; }

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern IntPtr CreateToolhelp32Snapshot(uint flags, uint processId);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool Process32FirstW(IntPtr snapshot, ref PROCESSENTRY32 entry);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool Process32NextW(IntPtr snapshot, ref PROCESSENTRY32 entry);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool GetProcessTimes(IntPtr process, out FILETIME created, out FILETIME exited, out FILETIME kernel, out FILETIME user);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        static extern bool QueryFullProcessImageNameW(IntPtr process, uint flags, StringBuilder image, ref uint size);
        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool CloseHandle(IntPtr handle);

        static ulong FileTime(FILETIME value) { return ((ulong)value.High << 32) | value.Low; }

        // 0 = no matching process, 20 = matching or uncertain Python process, 21 = census failure.
        public static int Check(string installRoot) {
            string root;
            try { root = Path.GetFullPath(installRoot).TrimEnd(Path.DirectorySeparatorChar); }
            catch { return 21; }
            string python = Path.Combine(root, "runtime", "python.exe");
            string pythonw = Path.Combine(root, "runtime", "pythonw.exe");
            IntPtr snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (snapshot == INVALID_HANDLE_VALUE) return 21;
            try {
                PROCESSENTRY32 entry = new PROCESSENTRY32();
                entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
                if (!Process32FirstW(snapshot, ref entry)) return 21;
                for (;;) {
                    string imageName = entry.szExeFile ?? String.Empty;
                    if (String.Equals(imageName, "python.exe", StringComparison.OrdinalIgnoreCase) ||
                        String.Equals(imageName, "pythonw.exe", StringComparison.OrdinalIgnoreCase)) {
                        IntPtr process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, false, entry.th32ProcessID);
                        if (process == IntPtr.Zero) return 20;
                        try {
                            FILETIME created, exited, kernel, user;
                            if (!GetProcessTimes(process, out created, out exited, out kernel, out user) || FileTime(created) == 0) return 20;
                            uint capacity = 32768;
                            StringBuilder path = new StringBuilder((int)capacity);
                            if (!QueryFullProcessImageNameW(process, 0, path, ref capacity)) return 20;
                            string observed;
                            try { observed = Path.GetFullPath(path.ToString()); }
                            catch { return 20; }
                            // A changed image name means the snapshot PID raced with process exit/reuse.
                            if (!String.Equals(Path.GetFileName(observed), imageName, StringComparison.OrdinalIgnoreCase)) return 20;
                            if (String.Equals(observed, python, StringComparison.OrdinalIgnoreCase) ||
                                String.Equals(observed, pythonw, StringComparison.OrdinalIgnoreCase)) return 20;
                        } finally { CloseHandle(process); }
                    }
                    entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
                    if (!Process32NextW(snapshot, ref entry)) {
                        int error = Marshal.GetLastWin32Error();
                        if (error != 18) return 21;
                        break;
                    }
                }
                return 0;
            } finally { CloseHandle(snapshot); }
        }
    }
}
'@
    }
    $result = [ThermoGar.P4.ProcessGuard]::Check($normalRoot)
    if ($result -eq 0) {
        Write-CompactJsonAndExit -Object ([ordered]@{ schema = 1; status = 'NO_ACTIVE_INSTALLED_RUNTIME'; detail_code = 0 }) -Code 0
    }
    if ($result -eq 20) {
        Write-CompactJsonAndExit -Object ([ordered]@{ schema = 1; status = 'REFUSE_UPGRADE'; detail_code = 20 }) -Code 20
    }
    Write-CompactJsonAndExit -Object ([ordered]@{ schema = 1; status = 'PROCESS_CENSUS_FAILED'; detail_code = 21 }) -Code 21
}

$Mode = 'Build'
$InstallRoot = ''
$StageRoot = ''
$OutputDirectory = ''
$PayloadManifestPath = ''
$DistributionEvidenceReceiptPath = ''
$ProductVersionPath = ''
$IconPath = ''
$VersionAuthorityPath = ''
$DistributionVerifierPath = ''
$DistributionVerifierArgumentsJsonPath = ''
$NsisSourcePath = ''
$InstalledVerifierPath = ''
$ExpectedPayloadManifestSha256 = ''
$ExpectedDistributionEvidenceReceiptSha256 = ''
$ExpectedProductVersionSha256 = ''
$ExpectedIconSha256 = ''
$ExpectedVersionAuthoritySha256 = ''
$ExpectedDistributionVerifierSha256 = ''
$ExpectedNsisSourceSha256 = ''
$ExpectedBuildScriptSha256 = ''
$ExpectedInstalledVerifierSha256 = ''
$ExpectedPayloadRowCount = 0
$ExpectedPayloadTotalBytes = 0L
$ExpectedPayloadRootSha256 = ''

$allowedCliNames = @(
    'Mode','InstallRoot','StageRoot','OutputDirectory','PayloadManifestPath','DistributionEvidenceReceiptPath',
    'ProductVersionPath','IconPath','VersionAuthorityPath','DistributionVerifierPath','DistributionVerifierArgumentsJsonPath',
    'NsisSourcePath','InstalledVerifierPath','ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256',
    'ExpectedProductVersionSha256','ExpectedIconSha256','ExpectedVersionAuthoritySha256','ExpectedDistributionVerifierSha256',
    'ExpectedNsisSourceSha256','ExpectedBuildScriptSha256','ExpectedInstalledVerifierSha256','ExpectedPayloadRowCount',
    'ExpectedPayloadTotalBytes','ExpectedPayloadRootSha256'
)
$seenCliNames = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
for ($cliIndex = 0; $cliIndex -lt $RawCliArguments.Count; $cliIndex++) {
    $token = [string]$RawCliArguments[$cliIndex]
    if ($token.Length -lt 2 -or $token[0] -cne '-') { Stop-Build 2 'USAGE' 'POSITIONAL_ARGUMENT_REJECTED' }
    $name = $token.Substring(1)
    if (-not ($allowedCliNames -ccontains $name)) { Stop-Build 2 'USAGE' 'UNKNOWN_OR_ABBREVIATED_PARAMETER' }
    if (-not $seenCliNames.Add($name)) { Stop-Build 2 'USAGE' 'DUPLICATE_PARAMETER' }
    $cliIndex++
    if ($cliIndex -ge $RawCliArguments.Count) { Stop-Build 2 'USAGE' ('MISSING_VALUE_' + $name.ToUpperInvariant()) }
    $value = [string]$RawCliArguments[$cliIndex]
    if ($value.StartsWith('-', [System.StringComparison]::Ordinal)) { Stop-Build 2 'USAGE' ('MISSING_VALUE_' + $name.ToUpperInvariant()) }
    if ($name -ceq 'ExpectedPayloadRowCount') {
        $parsedInt = 0
        if (-not [int]::TryParse($value, [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsedInt) -or
            $parsedInt -lt 1 -or $parsedInt -gt 1000000) { Stop-Build 2 'USAGE' 'INVALID_EXPECTEDPAYLOADROWCOUNT' }
        $ExpectedPayloadRowCount = $parsedInt
    } elseif ($name -ceq 'ExpectedPayloadTotalBytes') {
        $parsedLong = 0L
        if (-not [long]::TryParse($value, [Globalization.NumberStyles]::None, [Globalization.CultureInfo]::InvariantCulture, [ref]$parsedLong) -or
            $parsedLong -lt 1) { Stop-Build 2 'USAGE' 'INVALID_EXPECTEDPAYLOADTOTALBYTES' }
        $ExpectedPayloadTotalBytes = $parsedLong
    } else {
        Set-Variable -Name $name -Value $value
    }
}
if ($Mode -cnotin @('Build', 'UpgradePreflight')) { Stop-Build 2 'USAGE' 'INVALID_MODE' }
$hashCliNames = @(
    'ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedProductVersionSha256','ExpectedIconSha256',
    'ExpectedVersionAuthoritySha256','ExpectedDistributionVerifierSha256','ExpectedNsisSourceSha256','ExpectedBuildScriptSha256',
    'ExpectedInstalledVerifierSha256','ExpectedPayloadRootSha256'
)
foreach ($hashName in $hashCliNames) {
    $hashValue = [string](Get-Variable -Name $hashName -ValueOnly)
    if (-not [string]::IsNullOrEmpty($hashValue) -and $hashValue -notmatch '^[0-9A-Fa-f]{64}$') {
        Stop-Build 2 'USAGE' ('INVALID_' + $hashName.ToUpperInvariant())
    }
}

if ($Mode -eq 'UpgradePreflight') {
    if ([string]::IsNullOrWhiteSpace($InstallRoot)) { Stop-Build 2 'USAGE' 'INSTALL_ROOT_REQUIRED' }
    try { Invoke-UpgradePreflight -Root $InstallRoot }
    catch { Stop-Build 21 'PROCESS_CENSUS_FAILED' 'PREFLIGHT_EXCEPTION' }
}

$requiredStrings = @(
    'StageRoot','OutputDirectory','PayloadManifestPath','DistributionEvidenceReceiptPath','ProductVersionPath','IconPath',
    'VersionAuthorityPath','DistributionVerifierPath','DistributionVerifierArgumentsJsonPath','NsisSourcePath','InstalledVerifierPath',
    'ExpectedPayloadManifestSha256','ExpectedDistributionEvidenceReceiptSha256','ExpectedProductVersionSha256','ExpectedIconSha256',
    'ExpectedVersionAuthoritySha256','ExpectedDistributionVerifierSha256','ExpectedNsisSourceSha256','ExpectedBuildScriptSha256',
    'ExpectedInstalledVerifierSha256','ExpectedPayloadRootSha256'
)
foreach ($name in $requiredStrings) {
    if ([string]::IsNullOrWhiteSpace((Get-Variable -Name $name -ValueOnly))) { Stop-Build 2 'USAGE' ("MISSING_" + $name.ToUpperInvariant()) }
}
if ($ExpectedPayloadRowCount -le 0 -or $ExpectedPayloadTotalBytes -le 0) { Stop-Build 2 'USAGE' 'PAYLOAD_PINS_REQUIRED' }

$temporaryRoot = $null
$temporaryLeaf = $null
$outputDirectoryHandle = $null
$temporaryDirectory = $null
$installerPublication = $null
$receiptPublication = $null
$includeCleanup = $null
$logCleanup = $null
$includePath = $null
$tempInstallerPath = $null
$tempReceiptPath = $null
$compileLogPath = $null
try {
    try {
        $stage = Assert-PlainAncestors -Path $StageRoot -RequireLeaf $true
        $output = Assert-PlainAncestors -Path $OutputDirectory -RequireLeaf $true
        $manifestFile = Read-StableBytes -Path $PayloadManifestPath -ExpectedSha256 $ExpectedPayloadManifestSha256
        $receiptFile = Read-StableBytes -Path $DistributionEvidenceReceiptPath -ExpectedSha256 $ExpectedDistributionEvidenceReceiptSha256
        if ($ExpectedProductVersionSha256.ToUpperInvariant() -cne $FixedProductVersionSha256 -or
            $ExpectedIconSha256.ToUpperInvariant() -cne $FixedIconSha256 -or
            $ExpectedVersionAuthoritySha256.ToUpperInvariant() -cne $FixedReleasePolicySha256) { throw 'FROZEN_IDENTITY_PIN' }
        $versionFile = Read-StableBytes -Path $ProductVersionPath -ExpectedBytes $FixedProductVersionBytes -ExpectedSha256 $FixedProductVersionSha256
        $iconFile = Read-StableBytes -Path $IconPath -ExpectedBytes $FixedIconBytes -ExpectedSha256 $FixedIconSha256
        $authorityFile = Read-StableBytes -Path $VersionAuthorityPath -ExpectedSha256 $ExpectedVersionAuthoritySha256
        $p3VerifierFile = Read-StableBytes -Path $DistributionVerifierPath -ExpectedSha256 $ExpectedDistributionVerifierSha256
        $p3ArgumentsFile = Read-StableBytes -Path $DistributionVerifierArgumentsJsonPath
        $nsiFile = Read-StableBytes -Path $NsisSourcePath -ExpectedSha256 $ExpectedNsisSourceSha256
        $buildFile = Read-StableBytes -Path $PSCommandPath -ExpectedSha256 $ExpectedBuildScriptSha256
        $installedVerifierFile = Read-StableBytes -Path $InstalledVerifierPath -ExpectedSha256 $ExpectedInstalledVerifierSha256
        $nsisFile = Read-StableBytes -Path $FixedNsisPath -ExpectedBytes $FixedNsisBytes -ExpectedSha256 $FixedNsisSha256
        if (-not [string]::Equals($manifestFile.Path, (Join-Path $stage 'manifests\payload-manifest.json'), [System.StringComparison]::OrdinalIgnoreCase) -or
            -not [string]::Equals($receiptFile.Path, (Join-Path $stage 'manifests\distribution-evidence-receipt.json'), [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'STAGE_DOCUMENT_LOCATION'
        }
    } catch {
        Stop-Build 3 'INPUT_INVALID' 'INPUT_PIN_OR_PATH_INVALID'
    }

    try {
        Assert-IcoStructure $iconFile.Bytes
        $versionText = [System.Text.UTF8Encoding]::new($false, $true).GetString($versionFile.Bytes)
        $version = $versionText | ConvertFrom-Json
        if ($version.schema -ne 1 -or $version.version -ne 1 -or $version.display_name -cne 'ThermoGar' -or
            $version.description -cne 'ThermoGar Research Desktop — RESEARCH SOFTWARE — NO EXPERIMENTAL VALIDATION' -or
            $version.display_version -cne '0.2.0-ne02' -or $version.vi_product_version -cne '0.2.0.0' -or $version.app_stage -cne 'SWR-NE02' -or
            [string]$version.release_policy_sha256 -cne $FixedReleasePolicySha256 -or
            [long]$version.icon_bytes -ne $iconFile.Length -or [string]$version.icon_sha256 -cne $ExpectedIconSha256.ToUpperInvariant() -or
            [string]$version.icon_source_png_sha256 -cne 'FBC129AE038355C560FF5AACC84647250C89E2C909CDAED821BE73395FC4C8D4' -or
            @($version.icon_sizes).Count -ne $IconSizes.Count) { throw 'VERSION_SCHEMA' }
        for ($index = 0; $index -lt $IconSizes.Count; $index++) { if ([int]$version.icon_sizes[$index] -ne $IconSizes[$index]) { throw 'ICON_SIZES' } }
        $authorityText = [System.Text.UTF8Encoding]::new($false, $true).GetString($authorityFile.Bytes)
        if ($authorityText -notmatch '(?m)^APP_STAGE:\s*Final\s*=\s*["'']SWR-NE02["'']\s*(?:#.*)?$' -or
            $authorityText -notmatch '(?m)^APP_VERSION:\s*Final\s*=\s*["'']0\.2\.0-ne02["'']\s*(?:#.*)?$') { throw 'VERSION_AUTHORITY' }
    } catch {
        Stop-Build 4 'IDENTITY_INVALID' 'VERSION_OR_ICON_INVALID'
    }

    try {
        $manifestText = [System.Text.UTF8Encoding]::new($false, $true).GetString($manifestFile.Bytes)
        $manifest = $manifestText | ConvertFrom-Json
        if ($manifest.schema -ne 1 -or $manifest.version -ne 1 -or $manifest.algorithm -cne 'SHA-256' -or
            [int]$manifest.row_count -ne $ExpectedPayloadRowCount -or [long]$manifest.total_bytes -ne $ExpectedPayloadTotalBytes -or
            [string]$manifest.payload_root_sha256 -cne $ExpectedPayloadRootSha256.ToUpperInvariant() -or $manifest.rows.Count -ne $ExpectedPayloadRowCount) {
            throw 'PAYLOAD_MANIFEST_PINS'
        }
        $receiptText = [System.Text.UTF8Encoding]::new($false, $true).GetString($receiptFile.Bytes)
        $receipt = $receiptText | ConvertFrom-Json
        if ($receipt.schema -ne 1 -or $receipt.version -ne 1 -or $receipt.algorithm -cne 'SHA-256' -or
            [string]$receipt.payload_manifest_sha256 -cne $ExpectedPayloadManifestSha256.ToUpperInvariant() -or
            [string]$receipt.payload_root_sha256 -cne $ExpectedPayloadRootSha256.ToUpperInvariant() -or
            [int]$receipt.payload_row_count -ne $ExpectedPayloadRowCount -or [long]$receipt.payload_total_bytes -ne $ExpectedPayloadTotalBytes -or
            [string]$receipt.product_version_sha256 -cne $ExpectedProductVersionSha256.ToUpperInvariant() -or
            [string]$receipt.icon_sha256 -cne $ExpectedIconSha256.ToUpperInvariant()) { throw 'DISTRIBUTION_RECEIPT_PINS' }
    } catch {
        Stop-Build 5 'DISTRIBUTION_INVALID' 'DISTRIBUTION_DOCUMENT_INVALID'
    }

    try {
        $argumentText = [System.Text.UTF8Encoding]::new($false, $true).GetString($p3ArgumentsFile.Bytes)
        if ((Get-Command ConvertFrom-Json).Parameters.ContainsKey('DateKind')) {
            $argumentObject = $argumentText | ConvertFrom-Json -DateKind String
        } else {
            $argumentObject = $argumentText | ConvertFrom-Json
        }
        $p3Arguments = [System.Collections.Generic.List[string]]::new()
        $p3Arguments.AddRange([string[]]@('-NoLogo','-NoProfile','-NonInteractive','-File',$p3VerifierFile.Path))
        foreach ($property in @($argumentObject.psobject.Properties | Sort-Object Name)) {
            if ($property.Name -notmatch '^[A-Za-z][A-Za-z0-9]*$' -or $property.Value -is [System.Collections.IEnumerable] -and -not ($property.Value -is [string])) {
                throw 'P3_ARGUMENT_GRAMMAR'
            }
            $p3Arguments.Add('-' + $property.Name)
            $p3Arguments.Add([string]$property.Value)
        }
        $pwshPath = (Get-Process -Id $PID).Path
        $p3Output = @(& $pwshPath $p3Arguments.ToArray() 2>&1)
        $p3Exit = $LASTEXITCODE
        if ($p3Exit -ne 0 -or $p3Output.Count -ne 1) { throw 'P3_VERIFIER_EXIT' }
        $p3Result = [string]$p3Output[0] | ConvertFrom-Json
        if ($p3Result.status -cne 'P3_DISTRIBUTION_EVIDENCE_VERIFIED' -or
            [int]$p3Result.payload_row_count -ne $ExpectedPayloadRowCount -or
            [string]$p3Result.payload_root_sha256 -cne $ExpectedPayloadRootSha256.ToUpperInvariant() -or
            [string]$p3Result.payload_manifest_sha256 -cne $ExpectedPayloadManifestSha256.ToUpperInvariant() -or
            [string]$p3Result.distribution_receipt_sha256 -cne $ExpectedDistributionEvidenceReceiptSha256.ToUpperInvariant()) { throw 'P3_VERIFIER_RESULT' }
    } catch {
        Stop-Build 6 'P3_VERIFICATION_FAILED' 'P3_VERIFIER_REJECTED'
    }

    # NtCreateFile(FILE_CREATE|FILE_DIRECTORY_FILE) both proves create-new
    # ownership and returns the exact directory handle atomically. The private
    # scope is a direct child of the output directory, so every later rename is
    # necessarily same-volume on Windows PowerShell 5.1 as well as PowerShell 7.
    Initialize-OwnedPathType
    $outputDirectoryHandle = [ThermoGar.P4.OwnedPath]::OpenDirectoryGuard($output)
    $temporaryLeaf = '.ThermoGar-P4-' + [Guid]::NewGuid().ToString('N')
    $temporaryRoot = Join-Path $output $temporaryLeaf
    $temporaryDirectory = [ThermoGar.P4.OwnedPath]::CreateDirectoryNew($outputDirectoryHandle, $temporaryLeaf)
    $includePath = Join-Path $temporaryRoot 'payload-files.nsh'
    $tempInstallerPath = Join-Path $temporaryRoot 'ThermoGar-0.2.0-ne02-win64.exe'
    $tempReceiptPath = Join-Path $temporaryRoot 'ThermoGar-0.2.0-ne02-win64.build-receipt.json'
    $compileLogPath = Join-Path $temporaryRoot 'makensis.log'

    try {
        $ordinal = [System.StringComparer]::Ordinal
        $caseSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
        $literalRows = [System.Collections.Generic.List[string]]::new()
        $includeLines = [System.Collections.Generic.List[string]]::new()
        $previous = $null
        $total = [long]0
        $stagePrefix = $stage.TrimEnd('\') + '\'
        foreach ($row in $manifest.rows) {
            $relative = [string]$row.path
            $bytes = [long]$row.bytes
            $sha = ([string]$row.sha256).ToUpperInvariant()
            $segments = $relative.Split('/')
            if ($relative -notmatch '^[^\\/:*?"<>|]+(?:/[^\\/:*?"<>|]+)*$' -or @($segments | Where-Object { $_ -in @('.', '..') }).Count -ne 0 -or
                $relative.Normalize([Text.NormalizationForm]::FormC) -cne $relative -or
                $sha -notmatch '^[0-9A-F]{64}$' -or $bytes -lt 0 -or ($null -ne $previous -and $ordinal.Compare($previous, $relative) -ge 0) -or
                -not $caseSet.Add($relative)) { throw 'PAYLOAD_ROW_GRAMMAR' }
            if ([string]::Equals($relative, 'manifests/payload-manifest.json', [System.StringComparison]::OrdinalIgnoreCase) -or
                [string]::Equals($relative, 'manifests/distribution-evidence-receipt.json', [System.StringComparison]::OrdinalIgnoreCase) -or
                [string]::Equals($relative, 'product-version.json', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'PAYLOAD_SELF_OR_EXTERNAL_IDENTITY_ROW' }
            $source = [System.IO.Path]::GetFullPath((Join-Path $stage ($relative.Replace('/', '\'))))
            if (-not $source.StartsWith($stagePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'PAYLOAD_ROW_ESCAPE' }
            $sourceFile = Read-StableBytes -Path $source -ExpectedBytes $bytes -ExpectedSha256 $sha
            $directory = [System.IO.Path]::GetDirectoryName($relative.Replace('/', '\'))
            $name = [System.IO.Path]::GetFileName($relative)
            $outPath = if ([string]::IsNullOrEmpty($directory)) { '$INSTDIR.new' } else { '$INSTDIR.new\' + (Convert-ToNsisLiteral $directory) }
            $includeLines.Add('SetOutPath "' + $outPath + '"')
            $includeLines.Add('File "/oname=' + (Convert-ToNsisLiteral $name) + '" "' + (Convert-ToNsisLiteral $sourceFile.Path) + '"')
            $literalRows.Add("$relative|$bytes|$sha")
            $total += $bytes
            $previous = $relative
        }
        if ($literalRows.Count -ne $ExpectedPayloadRowCount -or $total -ne $ExpectedPayloadTotalBytes -or
            (Get-RootSha256 $literalRows.ToArray()) -cne $ExpectedPayloadRootSha256.ToUpperInvariant()) { throw 'PAYLOAD_ROOT' }
        Write-NewUtf8NoBom -Path $includePath -Text ([string]::Join("`r`n", $includeLines))
        $includeOutput = Read-StableBytes -Path $includePath
    } catch {
        Stop-Build 7 'PAYLOAD_INVALID' 'PAYLOAD_INCLUDE_REJECTED'
    }

    $finalInstallerPath = Join-Path $output 'ThermoGar-0.2.0-ne02-win64.exe'
    $finalReceiptPath = Join-Path $output 'ThermoGar-0.2.0-ne02-win64.build-receipt.json'
    if ((Test-Path -LiteralPath $finalInstallerPath) -or (Test-Path -LiteralPath $finalReceiptPath)) {
        Stop-Build 8 'IO_CONFLICT' 'OUTPUT_ALREADY_EXISTS'
    }

    try {
        $defines = @(
            '/V4',
            ('/DPRODUCT_DISPLAY_NAME=' + [string]$version.display_name),
            ('/DPRODUCT_DESCRIPTION=' + [string]$version.description),
            ('/DPRODUCT_DISPLAY_VERSION=' + [string]$version.display_version),
            ('/DPRODUCT_VI_VERSION=' + [string]$version.vi_product_version),
            ('/DPRODUCT_ICON=' + $iconFile.Path),
            ('/DOUTPUT_FILE=' + $tempInstallerPath),
            ('/DPAYLOAD_INCLUDE=' + $includePath),
            ('/DBUILD_HELPER=' + $buildFile.Path),
            ('/DVERIFY_HELPER=' + $installedVerifierFile.Path),
            ('/DEXPECTED_PAYLOAD_MANIFEST_SHA256=' + $ExpectedPayloadManifestSha256.ToUpperInvariant()),
            ('/DEXPECTED_DISTRIBUTION_RECEIPT_SHA256=' + $ExpectedDistributionEvidenceReceiptSha256.ToUpperInvariant()),
            ('/DEXPECTED_PAYLOAD_ROWS=' + $ExpectedPayloadRowCount),
            ('/DEXPECTED_PAYLOAD_BYTES=' + $ExpectedPayloadTotalBytes),
            ('/DEXPECTED_PAYLOAD_ROOT_SHA256=' + $ExpectedPayloadRootSha256.ToUpperInvariant()),
            ('/DEXPECTED_PRODUCT_VERSION_SHA256=' + $ExpectedProductVersionSha256.ToUpperInvariant()),
            ('/DEXPECTED_ICON_SHA256=' + $ExpectedIconSha256.ToUpperInvariant()),
            ('/DPAYLOAD_MANIFEST_SOURCE=' + $manifestFile.Path),
            ('/DDISTRIBUTION_RECEIPT_SOURCE=' + $receiptFile.Path),
            $nsiFile.Path
        )
        $compileOutput = @(& $nsisFile.Path $defines 2>&1)
        $compileExit = $LASTEXITCODE
        # Pin and verify the exact PE immediately when the producer exits;
        # share mode zero prevents both writers and delete-denying readers.
        if ($compileExit -eq 0) {
            $installerPublication = [ThermoGar.P4.OwnedPath]::OpenVerifiedFileForRename(
                $temporaryDirectory, 'ThermoGar-0.2.0-ne02-win64.exe', -1, '', $true)
        }
        Write-NewUtf8NoBom -Path $compileLogPath -Text ([string]::Join("`r`n", @($compileOutput | ForEach-Object { [string]$_ })))
        $logOutput = Read-StableBytes -Path $compileLogPath
        # Reopen the two generated support leaves against their cached hashes
        # only after makensis has exited, then retain those exact cleanup handles.
        $includeCleanup = [ThermoGar.P4.OwnedPath]::OpenVerifiedFileForRename(
            $temporaryDirectory, 'payload-files.nsh', $includeOutput.Length, $includeOutput.Sha256, $false)
        $logCleanup = [ThermoGar.P4.OwnedPath]::OpenVerifiedFileForRename(
            $temporaryDirectory, 'makensis.log', $logOutput.Length, $logOutput.Sha256, $false)
        if ($compileExit -ne 0) { throw 'NSIS_COMPILE' }
        # PE, size, and SHA-256 are read through this same live, no-write-share
        # handle and remain bound to it through publication or exact rollback.
        $installer = [pscustomobject]@{ Length = $installerPublication.Length; Sha256 = $installerPublication.Sha256 }
        $receiptObject = [ordered]@{
            schema = 1; version = 1; status = 'P4_INSTALLER_BUILT'; display_version = [string]$version.display_version
            installer_path = [System.IO.Path]::GetFullPath($finalInstallerPath); installer_bytes = $installer.Length; installer_sha256 = $installer.Sha256
            payload_manifest_sha256 = $ExpectedPayloadManifestSha256.ToUpperInvariant()
            distribution_receipt_sha256 = $ExpectedDistributionEvidenceReceiptSha256.ToUpperInvariant()
            payload_row_count = $ExpectedPayloadRowCount; payload_total_bytes = $ExpectedPayloadTotalBytes
            payload_root_sha256 = $ExpectedPayloadRootSha256.ToUpperInvariant(); product_version_sha256 = $ExpectedProductVersionSha256.ToUpperInvariant()
            icon_sha256 = $ExpectedIconSha256.ToUpperInvariant(); nsis_bytes = $FixedNsisBytes; nsis_sha256 = $FixedNsisSha256
            nsi_sha256 = $ExpectedNsisSourceSha256.ToUpperInvariant(); build_script_sha256 = $ExpectedBuildScriptSha256.ToUpperInvariant()
            installed_verifier_sha256 = $ExpectedInstalledVerifierSha256.ToUpperInvariant()
        }
        # Prepare and verify both artifacts privately. RenameNoReplace acts on
        # the already-open exact file object; its live handle prevents ABA
        # replacement until either exact rollback or receipt-last commit.
        $receiptText = $receiptObject | ConvertTo-Json -Compress -Depth 8
        $receiptBytes = [System.Text.UTF8Encoding]::new($false).GetBytes($receiptText)
        $receiptExpectedSha256 = Get-Sha256Hex $receiptBytes
        Write-NewUtf8NoBom -Path $tempReceiptPath -Text $receiptText
        $receiptPublication = [ThermoGar.P4.OwnedPath]::OpenVerifiedFileForRename(
            $temporaryDirectory, 'ThermoGar-0.2.0-ne02-win64.build-receipt.json',
            $receiptBytes.LongLength, $receiptExpectedSha256, $false)
        $receiptOutput = [pscustomobject]@{ Length = $receiptPublication.Length; Sha256 = $receiptPublication.Sha256 }
        $installerPublication.RenameNoReplace($outputDirectoryHandle, 'ThermoGar-0.2.0-ne02-win64.exe')
        $receiptPublication.RenameNoReplace($outputDirectoryHandle, 'ThermoGar-0.2.0-ne02-win64.build-receipt.json')
        # The receipt rename is the public commit marker. No fallible operation
        # follows it; handle release cannot mutate or invalidate either file.
        $receiptPublication.Release()
        $receiptPublication = $null
        $installerPublication.Release()
        $installerPublication = $null
        $finalInstaller = $installer
    } catch {
        $publicationRollbackFailed = $false
        if ($null -ne $receiptPublication) {
            try { $receiptPublication.DeleteExact(); $receiptPublication = $null }
            catch { $publicationRollbackFailed = $true }
        }
        if ($null -ne $installerPublication) {
            try { $installerPublication.DeleteExact(); $installerPublication = $null }
            catch { $publicationRollbackFailed = $true }
        }
        if ($publicationRollbackFailed) {
            Stop-Build 8 'PUBLICATION_ROLLBACK_FAILED' 'OWNED_OUTPUT_CLEANUP_FAILED'
        }
        Stop-Build 8 'BUILD_FAILED' ('NSIS_OR_PUBLICATION_FAILED:' + [string]$_.Exception.Message)
    }

    Write-CompactJsonAndExit -Object ([ordered]@{
        schema = 1; status = 'P4_INSTALLER_BUILT'; installer_bytes = $finalInstaller.Length; installer_sha256 = $finalInstaller.Sha256
        build_receipt_sha256 = $receiptOutput.Sha256
    }) -Code 0
} catch {
    Stop-Build 9 'INTERNAL_ERROR' 'UNEXPECTED_EXCEPTION'
} finally {
    # Cleanup uses only retained exact-object handles. If a leaf could not be
    # opened and verified earlier, it is never path-deleted; directory deletion
    # then fails closed and retains the uncertain private scope.
    foreach ($ownedObject in @($receiptPublication, $installerPublication, $includeCleanup, $logCleanup)) {
        if ($null -ne $ownedObject) {
            try { $ownedObject.DeleteExact() }
            catch { $ownedObject.Release() }
        }
    }
    if ($null -ne $temporaryDirectory) {
        try { $temporaryDirectory.DeleteExact() }
        catch { $temporaryDirectory.Release() }
        $temporaryDirectory = $null
    }
    if ($null -ne $outputDirectoryHandle) {
        $outputDirectoryHandle.Release()
        $outputDirectoryHandle = $null
    }
}
