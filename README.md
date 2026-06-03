# RawClone

**Disk imaging & cloning tool for Windows**

Raw sector-by-sector disk cloning and imaging utility with a modern GUI. Built on top of `dd` (rawwrite for Windows), wrapped in a PowerShell backend that handles volume locking, disk preparation, and progress reporting — all accessible through a clean PySide6 interface.

---

## Features

- **Disc → Image** — full raw sector copy of a physical disk to a `.img` file
- **Image → Disc** — restore a disk image back to a physical drive (with automatic partition cleanup and disk initialization)
- **Image → Image** — duplicate image files with integrity verification
- **SHA-256 verification** — optional hash calculation and two-pass integrity check after every operation
- **Real-time progress** — speed, ETA, bytes transferred, and error count updated live
- **Operation log** — timestamped console with export support
- **Multilingual** — Portuguese (BR), Spanish, English
- **Light / Dark theme**
- **Portable** — single `.exe` with all dependencies bundled

---

## Requirements

### To run from source
- Python 3.10+
- PySide6
- psutil

```
pip install PySide6 psutil
```

### To run the portable executable
- Windows 10/11 x64
- **Administrator privileges** (required for raw disk access)
- No Python installation needed

---

## Dependencies (bundled in the executable)

| File | Description |
|------|-------------|
| `dd.exe` | rawwrite dd for Windows v0.6beta3 by John Newbigin |
| `rawclone_dd.ps1` | PowerShell backend — handles volume locking, disk clean/init, and dd execution |
| `icone.ico` | Application icon |

---

## Usage

### Running from source

```
python main.py
```

Must be run as Administrator.

### Building the portable executable

```
pyinstaller --onefile --windowed --icon=icone.ico --add-data "icone.ico;." --add-data "dd.exe;." --add-data "rawclone_dd.ps1;." --name RawClone main.py
```

Output will be in `dist\RawClone.exe`.

---

## How to use

1. **Launch as Administrator** — raw disk access requires elevated privileges
2. **Select Source** — choose Physical disk, Volume/Partition, or Image file
3. **Select Destination** — choose Physical disk or Image file path
4. **Configure options** — SHA-256 verification, block size, compression
5. **Click INICIAR / START** — operation begins immediately

### Image → Disc notes

When writing an image to a physical disk, RawClone automatically:
- Locks and dismounts all volumes on the destination disk
- Clears existing partitions (`diskpart clean`)
- Initializes the disk (MBR) so it is accessible for writing
- Calls `dd` to perform the raw write

The destination disk will have no partition table after the operation — the raw image data is written directly at sector 0. Use Disk Management or `diskpart` to create partitions afterward if needed.

---

## Supported operations

| Source | Destination | Notes |
|--------|-------------|-------|
| Physical disk | Image file | Full raw copy, sector by sector |
| Image file | Physical disk | Overwrites entire disk |
| Image file | Image file | File-to-file raw copy |
| Physical disk | Physical disk | Not yet supported |

---

## Block size

| Size | Best for |
|------|----------|
| 512 KB | Slow/USB disks |
| 1 MB | General use |
| **4 MB** | Default — good balance |
| 8 MB | Fast NVMe/SSD |
| 16 MB | Maximum throughput |

---

## SHA-256 verification

When enabled, RawClone calculates the SHA-256 hash of the destination after the copy. With **Phase 2** enabled, it re-reads the destination file from disk for an independent verification pass.

---

## Known limitations

- Physical disk → Physical disk cloning not yet implemented (workaround: disc→image→disc)
- Compression (GZIP/LZ4) not available when destination is a physical disk
- Requires Windows PowerShell 5.1+ (included in Windows 10/11)

---

## License

MIT License — see [LICENSE](LICENSE)

`dd.exe` is copyright John Newbigin, licensed under GPL v2.

---

## Author

Developed by Fernando Valverde
