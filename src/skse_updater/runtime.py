"""Read executable resources through Windows version APIs, never LoadLibrary on mods."""
import ctypes
import os
from pathlib import Path

from .models import Version


def file_version(path: Path) -> Version | None:
    if os.name != "nt" or not path.is_file():
        return None
    from ctypes import wintypes
    api = ctypes.WinDLL("version", use_last_error=True)
    api.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    api.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    api.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    api.GetFileVersionInfoW.restype = wintypes.BOOL
    api.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                  ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    api.VerQueryValueW.restype = wintypes.BOOL
    unused = wintypes.DWORD()
    size = api.GetFileVersionInfoSizeW(str(path), ctypes.byref(unused))
    if not size or size > 16 * 1024 * 1024:
        return None
    buffer = ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(str(path), 0, size, buffer):
        return None
    address, length = ctypes.c_void_p(), wintypes.UINT()
    if not api.VerQueryValueW(buffer, "\\", ctypes.byref(address), ctypes.byref(length)) or length.value < 52:
        return None
    info = ctypes.cast(address, ctypes.POINTER(wintypes.DWORD))
    if info[0] != 0xFEEF04BD:
        return None
    return info[2] >> 16, info[2] & 65535, info[3] >> 16, info[3] & 65535
