#!/usr/bin/env python3
"""Проверка: Job лаунчера охватывает и воркеров пула, а не только Streamlit.

``packaging\\launcher.pyw`` держит дочерний Streamlit в Job-объекте с
``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` и не разрешает выход из Job
(``BREAKAWAY_OK`` не выставлен). Воркеры параллельного движка — внуки
лаунчера, и вся конструкция «остановка убивает всё» держится на том, что
Windows включает потомков в Job автоматически. Скрипт это проверяет
буквально: поднимает Job с теми же флагами, запускает в нём процесс, который
создаёт пул из двух воркеров, читает список процессов Job и закрывает
дескриптор Job — после чего все три процесса обязаны исчезнуть.

Запуск (установленная копия):

    "C:\\Program Files\\ThermoGar\\runtime\\python.exe" -P -s -B -X utf8 ^
        tools\\job_containment_check.py --root "C:\\Program Files\\ThermoGar"
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path


CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
MAX_JOB_PROCESSES = 64
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class JOBOBJECT_BASIC_PROCESS_ID_LIST(ctypes.Structure):
    _fields_ = [
        ("NumberOfAssignedProcesses", wintypes.DWORD),
        ("NumberOfProcessIdsInList", wintypes.DWORD),
        ("ProcessIdList", ctypes.c_size_t * MAX_JOB_PROCESSES),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD),
        ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD),
        ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD),
        ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD),
        ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p),
        ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE),
        ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD),
        ("dwThreadId", wintypes.DWORD),
    ]


# Без явных сигнатур ctypes считает возвращаемое значение 32-битным int и
# режет дескрипторы на 64-битной Windows.
kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = (
    wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
)
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.QueryInformationJobObject.argtypes = (
    wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
)
kernel32.QueryInformationJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.CreateProcessW.argtypes = (
    wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPVOID, wintypes.LPVOID,
    wintypes.BOOL, wintypes.DWORD, wintypes.LPVOID, wintypes.LPCWSTR,
    wintypes.LPVOID, wintypes.LPVOID,
)
kernel32.CreateProcessW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.GetExitCodeProcess.argtypes = (
    wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD),
)
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.ResumeThread.argtypes = (wintypes.HANDLE,)
kernel32.ResumeThread.restype = wintypes.DWORD


def _job_process_ids(job: int) -> list[int]:
    values = JOBOBJECT_BASIC_PROCESS_ID_LIST()
    returned = wintypes.DWORD(0)
    if not kernel32.QueryInformationJobObject(
        wintypes.HANDLE(job),
        JOB_OBJECT_BASIC_PROCESS_ID_LIST,
        ctypes.byref(values),
        ctypes.sizeof(values),
        ctypes.byref(returned),
    ):
        raise OSError(ctypes.get_last_error(), "QueryInformationJobObject")
    return [
        int(values.ProcessIdList[index])
        for index in range(values.NumberOfProcessIdsInList)
    ]


def _process_is_alive(pid: int) -> bool:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD(0)
        if not kernel32.GetExitCodeProcess(wintypes.HANDLE(handle), ctypes.byref(code)):
            return False
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(wintypes.HANDLE(handle))


def hold_pool(root: Path, ready_file: Path) -> int:
    """Дочерний режим: поднять пул из двух воркеров и ждать, пока не убьют."""
    sys.path.insert(0, str(root / "app"))
    import thermogar_parallel as parallel

    database = (
        root / "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb"
    ).resolve()
    sha256 = parallel.file_sha256(database)
    engine = parallel.ParallelEquilibrium(database, sha256, workers=2)
    pool = engine._ensure_pool()  # noqa: SLF001 — нужен именно факт живых воркеров
    # Воркеры поднимаются по мере поступления заданий, поэтому сначала работа.
    futures = [pool.submit(os.getpid) for _ in range(4)]
    [item.result() for item in futures]
    ready_file.write_text(
        json.dumps({"child": os.getpid(), "workers": engine.worker_pids()}),
        encoding="utf-8",
    )
    while True:
        time.sleep(1.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--hold", default="")
    arguments = parser.parse_args()

    root = Path(arguments.root).resolve()
    if arguments.hold:
        return hold_pool(root, Path(arguments.hold))

    ready = Path(os.environ.get("TEMP", ".")) / f"thermogar-job-{os.getpid()}.json"
    ready.unlink(missing_ok=True)

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
    )
    limits.BasicLimitInformation.ActiveProcessLimit = MAX_JOB_PROCESSES
    if not kernel32.SetInformationJobObject(
        wintypes.HANDLE(job),
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        raise OSError(ctypes.get_last_error(), "SetInformationJobObject")

    arguments_list = [
        sys.executable, "-P", "-s", "-B", "-X", "utf8",
        str(Path(__file__).resolve()),
        "--root", str(root),
        "--hold", str(ready),
    ]
    command = ctypes.create_unicode_buffer(subprocess.list2cmdline(arguments_list))
    environment = dict(os.environ)
    environment["PYTHONHASHSEED"] = "0"
    block = ctypes.create_unicode_buffer(
        "\0".join(f"{key}={value}" for key, value in sorted(environment.items()))
        + "\0\0"
    )
    startup = STARTUPINFOW()
    startup.cb = ctypes.sizeof(startup)
    info = PROCESS_INFORMATION()
    if not kernel32.CreateProcessW(
        sys.executable, command, None, None, False,
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW,
        block, str(root), ctypes.byref(startup), ctypes.byref(info),
    ):
        raise OSError(ctypes.get_last_error(), "CreateProcessW")
    if not kernel32.AssignProcessToJobObject(
        wintypes.HANDLE(job), wintypes.HANDLE(info.hProcess)
    ):
        raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject")
    kernel32.ResumeThread(wintypes.HANDLE(info.hThread))
    kernel32.CloseHandle(wintypes.HANDLE(info.hThread))

    deadline = time.time() + 300.0
    while not ready.exists():
        if time.time() > deadline:
            kernel32.CloseHandle(wintypes.HANDLE(job))
            raise TimeoutError("дочерний процесс не поднял пул за 300 с")
        time.sleep(0.5)
    payload = json.loads(ready.read_text(encoding="utf-8"))
    members = sorted(_job_process_ids(job))

    report = {
        "child_pid": payload["child"],
        "worker_pids": sorted(payload["workers"]),
        "job_members": members,
        "workers_inside_job": all(
            pid in members for pid in payload["workers"]
        ),
        "job_member_count": len(members),
    }

    kernel32.CloseHandle(wintypes.HANDLE(job))
    kernel32.CloseHandle(wintypes.HANDLE(info.hProcess))
    deadline = time.time() + 30.0
    alive = [pid for pid in members if _process_is_alive(pid)]
    while alive and time.time() < deadline:
        time.sleep(0.5)
        alive = [pid for pid in members if _process_is_alive(pid)]
    report["alive_after_job_close"] = alive
    ready.unlink(missing_ok=True)

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["workers_inside_job"] and not report["alive_after_job_close"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
