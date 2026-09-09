"""Bounded, read-only ZIP candidate inspection. Never extracts or executes files."""
from pathlib import PurePosixPath
from zipfile import ZipFile
from .pe_scan import inspect_bytes
from .compatibility import assess


def inspect_archive(path, runtime, cancelled=lambda: False):
    results = []
    with ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 20000:
            raise ValueError("Archive has too many entries")
        dlls = []
        fomod = False
        total = 0
        for member in members:
            if cancelled():
                raise ValueError("Inspection canceled")
            name = member.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or any(":" in p for p in parts):
                raise ValueError("Archive contains an unsafe path")
            if name.casefold().endswith("fomod/moduleconfig.xml"):
                fomod = True
            if name.lower().endswith(".dll"):
                total += member.file_size
                if len(dlls) >= 256 or member.file_size > 128 * 1024 * 1024 or total > 512 * 1024 * 1024:
                    raise ValueError("Archive DLL inspection exceeds size limits")
                if member.file_size > max(1, member.compress_size) * 1000:
                    raise ValueError("Archive compression ratio exceeds inspection limit")
                dlls.append(member)
        for member in dlls:
            if cancelled():
                raise ValueError("Inspection canceled")
            binary = inspect_bytes(archive.read(member))
            result = assess(binary, runtime)
            results.append((member.filename, binary.sha256, result))
    return fomod, results
