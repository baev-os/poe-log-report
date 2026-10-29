# Shared committed-memory limit for PowerShell and all child processes.
# JOBOBJECT_EXTENDED_LIMIT_INFORMATION layout follows the Win64 Windows SDK.
Set-StrictMode -Version Latest

Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

public static class WindowsMemoryBudget
{
    private const int ExtendedLimitInformation = 9;
    private const int InformationSize = 144;
    private const int FlagsOffset = 16;
    private const int JobLimitOffset = 120;
    private const int PeakOffset = 136;
    private static IntPtr job;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
    private static extern IntPtr CreateJobObjectW(IntPtr attributes, string name);

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetCurrentProcess();

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetInformationJobObject(IntPtr handle, int type,
        byte[] information, uint length);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryInformationJobObject(IntPtr handle, int type,
        [Out] byte[] information, uint length, IntPtr returnedLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool AssignProcessToJobObject(IntPtr handle, IntPtr process);

    public static void Apply(long bytes)
    {
        if (IntPtr.Size != 8 || job != IntPtr.Zero || bytes <= 0)
            throw new InvalidOperationException("A new Windows x64 process is required");
        job = CreateJobObjectW(IntPtr.Zero, null);

        if (job == IntPtr.Zero)
            throw new Win32Exception(Marshal.GetLastWin32Error());
        byte[] information = new byte[InformationSize];
        // JOB_OBJECT_LIMIT_JOB_MEMORY; child processes cannot break out of the job.
        BitConverter.GetBytes(0x00000200u).CopyTo(information, FlagsOffset);
        BitConverter.GetBytes(bytes).CopyTo(information, JobLimitOffset);

        if (!SetInformationJobObject(job, ExtendedLimitInformation, information, InformationSize)
            || !AssignProcessToJobObject(job, GetCurrentProcess()))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        // The handle lives until PowerShell exits; the OS closes it automatically.
        // The job retains its limits until all member processes exit.
    }

    private static byte[] Read()
    {
        byte[] information = new byte[InformationSize];

        if (!QueryInformationJobObject(job, ExtendedLimitInformation, information,
                                      InformationSize, IntPtr.Zero))
            throw new Win32Exception(Marshal.GetLastWin32Error());

        return information;
    }

    public static long LimitBytes()
    {
        return BitConverter.ToInt64(Read(), JobLimitOffset);
    }

    public static long PeakCommitBytes()
    {
        return BitConverter.ToInt64(Read(), PeakOffset);
    }
}
'@

[WindowsMemoryBudget]::Apply(8589934592)

if ([WindowsMemoryBudget]::LimitBytes() -ne 8589934592) {
    throw 'The shared 8 GiB memory limit was not applied'
}
