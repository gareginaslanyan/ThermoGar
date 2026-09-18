import ctypes, os, json
from ctypes import wintypes
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.restype=wintypes.HANDLE
k.GetFinalPathNameByHandleW.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]
k.CloseHandle.argtypes=[wintypes.HANDLE]
def fin(p):
    h=k.CreateFileW(p,0,7,None,3,0x02000000,None)
    buf=ctypes.create_unicode_buffer(1024); n=k.GetFinalPathNameByHandleW(h,buf,1024,0); k.CloseHandle(h); return buf.value or f"err {ctypes.get_last_error()}"
la=os.environ['LOCALAPPDATA']; t=os.path.join(la,'ThermoGar_probe17d')
os.makedirs(t,exist_ok=True)
print(json.dumps({"LOCALAPPDATA":fin(la),"probe_dir":fin(t),"ThermoGar":fin(os.path.join(la,'ThermoGar'))},indent=1))
os.rmdir(t)
