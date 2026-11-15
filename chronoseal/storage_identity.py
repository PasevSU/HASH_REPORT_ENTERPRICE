"""Read-only filesystem provenance. Never guesses absent platform identifiers."""
import os
import shutil
from pathlib import Path


def inspect_storage(path):
    p = Path(path).expanduser().resolve()
    probe = p if p.exists() and p.is_dir() else p.parent
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    st = probe.stat()
    disk = shutil.disk_usage(probe)
    result = {
        "requested_path": str(p), "probed_directory": str(probe),
        "device_id_st_dev": st.st_dev, "directory_inode_st_ino": st.st_ino,
        "bytes_total": disk.total, "bytes_used": disk.used,
        "bytes_available": disk.free, "capacity_percent_used": round(100 * disk.used / disk.total, 2) if disk.total else None,
        "volume_guid_path": None, "volume_mount_point": None,
        "filesystem_name": None, "volume_serial_number": None,
    }
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        mount = ctypes.create_unicode_buffer(32768)
        if not k.GetVolumePathNameW(str(probe), mount, len(mount)):
            raise OSError(ctypes.get_last_error(), "GetVolumePathNameW failed")
        result["volume_mount_point"] = mount.value
        guid = ctypes.create_unicode_buffer(32768)
        if k.GetVolumeNameForVolumeMountPointW(mount.value, guid, len(guid)):
            result["volume_guid_path"] = guid.value
        # Some UNC/network mounts cannot expose a local volume GUID.
        fs = ctypes.create_unicode_buffer(256)
        serial = wintypes.DWORD()
        max_component = wintypes.DWORD()
        flags = wintypes.DWORD()
        if k.GetVolumeInformationW(mount.value, None, 0, ctypes.byref(serial),
                                   ctypes.byref(max_component), ctypes.byref(flags), fs, len(fs)):
            result["filesystem_name"] = fs.value
            result["volume_serial_number"] = f"{serial.value:08X}"
    return result


def inspect_workspaces(input_path, evidence_path, output_path):
    return {"input": inspect_storage(input_path),
            "evidence": inspect_storage(evidence_path),
            "output": inspect_storage(output_path)}


DEFAULT_MIN_FREE_BYTES = 512 * 1024 * 1024


def low_space_warning(identity, minimum=None):
    """Advisory only: a nearly full volume must not silently truncate a sealed report.

    The seal step writes the report, a full evidence copy and the archive blobs,
    so free space is checked before the run instead of failing halfway through.
    """
    limit = DEFAULT_MIN_FREE_BYTES if minimum is None else int(minimum)
    if limit <= 0:
        return None
    free = (identity or {}).get("bytes_available")
    if free is None or free >= limit:
        return None
    where = identity.get("probed_directory") or identity.get("requested_path") or "the target volume"
    return (f"Low free space on {where}: {free / 1048576:.0f} MiB available, "
            f"{limit / 1048576:.0f} MiB expected; the sealed report, its evidence copy and the "
            f"archive may not fit.")
