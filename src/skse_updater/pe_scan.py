"""Bounded, read-only PE export parser. Never loads or invokes scanned DLLs.

SKSE structure layout: SKSEPluginVersionData in SKSE's PluginAPI.h.
Only schema 1 is decoded. Unknown flags remain visible to the evaluator.
"""
import hashlib
import struct
from pathlib import Path

from .models import Binary, Declaration, unpack_version

MAX_BYTES = 128 * 1024 * 1024


class PEError(ValueError):
    pass


class PE:
    def __init__(self, data: bytes):
        self.data = data
        if self.take(0, 2) != b"MZ":
            raise PEError("Not a PE file")
        header = self.u32(0x3C)
        if self.take(header, 4) != b"PE\0\0":
            raise PEError("Invalid PE signature")
        self.machine, count = self.unpack("HH", header + 4)
        self.timestamp = self.u32(header + 8)
        size = self.unpack("H", header + 20)[0]
        optional = header + 24
        magic = self.unpack("H", optional)[0]
        if magic not in (0x10B, 0x20B):
            raise PEError("Unknown optional-header format")
        directory = 112 if magic == 0x20B else 96
        if size < directory + 8 or not 0 < count <= 96:
            raise PEError("Invalid header sizes")
        self.take(optional, size)
        if self.u32(optional + directory - 4) < 1:
            self.export_rva, self.export_size = 0, 0
        else:
            self.export_rva, self.export_size = self.unpack("II", optional + directory)
        self.headers_size = self.u32(optional + 60)
        self.sections = []
        for i in range(count):
            entry = optional + size + i * 40
            self.take(entry, 40)
            virtual_size, rva, raw_size, raw = self.unpack("IIII", entry + 8)
            self.sections.append((rva, virtual_size, raw_size, raw))

    def take(self, offset: int, size: int) -> bytes:
        if offset < 0 or size < 0 or offset + size > len(self.data):
            raise PEError("Truncated or out-of-bounds PE data")
        return self.data[offset:offset + size]

    def unpack(self, fmt: str, offset: int):
        return struct.unpack("<" + fmt, self.take(offset, struct.calcsize("<" + fmt)))

    def u32(self, offset: int) -> int:
        return self.unpack("I", offset)[0]

    def offset(self, rva: int, size: int) -> int:
        if rva < self.headers_size and rva + size <= self.headers_size:
            self.take(rva, size)
            return rva
        matches = []
        for start, virtual_size, raw_size, raw in self.sections:
            delta = rva - start
            if 0 <= delta and delta + size <= raw_size:
                matches.append(raw + delta)
        if len(matches) != 1:
            raise PEError("Unmapped, virtual-only or overlapping RVA")
        self.take(matches[0], size)
        return matches[0]

    def export_name(self, rva: int) -> str:
        result = bytearray()
        for i in range(4096):
            value = self.data[self.offset(rva + i, 1)]
            if not value:
                return result.decode("ascii", errors="replace")
            result.append(value)
        raise PEError("Unterminated export name")

    def exports(self) -> dict[str, int]:
        if not self.export_rva:
            return {}
        at = self.offset(self.export_rva, 40)
        functions, names, addresses, name_rvas, ordinals = self.unpack("IIIII", at + 20)
        if functions > 65536 or names > 65536:
            raise PEError("Unreasonable export count")
        address_at = self.offset(addresses, functions * 4)
        names_at = self.offset(name_rvas, names * 4)
        ordinal_at = self.offset(ordinals, names * 2)
        result = {}
        for i in range(names):
            name = self.export_name(self.u32(names_at + 4 * i))
            ordinal = self.unpack("H", ordinal_at + 2 * i)[0]
            if ordinal >= functions:
                raise PEError("Invalid export ordinal")
            result[name] = self.u32(address_at + ordinal * 4)
        return result

    def declaration(self, rva: int) -> Declaration:
        if self.export_rva <= rva < self.export_rva + self.export_size:
            raise PEError("Forwarded metadata export")
        at = self.offset(rva, 0x350)
        schema, version = self.unpack("II", at)
        if schema != 1:
            raise PEError(f"Unsupported SKSE metadata schema {schema}")
        name = self.take(at + 8, 256)
        if b"\0" not in name or not name.split(b"\0", 1)[0]:
            raise PEError("Invalid plugin name")
        flags_ex, flags = self.unpack("II", at + 0x304)
        packed = self.unpack("16I", at + 0x30C)
        end = packed.index(0) if 0 in packed else len(packed)
        runtimes = [unpack_version(v) for v in packed[:end]]
        return Declaration(schema, version, name.split(b"\0", 1)[0].decode("utf-8", "replace"),
                           flags_ex, flags, runtimes, self.u32(at + 0x34C))


def inspect_bytes(data: bytes) -> Binary:
    result = Binary(sha256=hashlib.sha256(data).hexdigest())
    try:
        pe = PE(data)
        result.machine = pe.machine
        result.timestamp = pe.timestamp
        exports = pe.exports()
        result.exports = sorted(exports)
        if "SKSEPlugin_Version" in exports:
            result.declaration = pe.declaration(exports["SKSEPlugin_Version"])
    except (PEError, struct.error) as exc:
        result.error = str(exc)
    return result


def inspect_file(path: Path) -> Binary:
    try:
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return Binary(error="DLL exceeds scanner size limit")
        return inspect_bytes(data)
    except OSError as exc:
        return Binary(error=f"Cannot read DLL: {exc.strerror}")
