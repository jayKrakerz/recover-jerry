# recover-jerry

A macOS file recovery tool with a web UI. Scans multiple recovery sources (Trash, APFS snapshots, Time Machine, Spotlight, PhotoRec) and lets you selectively recover deleted files with integrity verification.

## Quick Install

Open Terminal and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/jayKrakerz/recover-jerry/master/scripts/install.sh)"
```

This handles everything automatically — Homebrew, Python, dependencies, and launches the app.

To run it again later:

```bash
~/recover-jerry/scripts/launch.sh
```

## Requirements

- **macOS** (uses macOS-specific APIs: APFS snapshots, Time Machine, Spotlight)
- **Python 3.11+**
- **testdisk** (optional, for PhotoRec file carving): `brew install testdisk`

## Setup

```bash
pip3 install -r requirements.txt
```

## Usage

```bash
./scripts/launch.sh
```

This starts the server and opens `http://127.0.0.1:8787` in your browser.

Alternatively:

```bash
python3 -m recover_jerry
```

## How it works

1. **Dashboard** — Shows system info and which recovery sources are available
2. **Scan** — Select sources, date range, and file type filters, then start a scan
3. **Results** — Browse, search, and filter discovered files
4. **Recover** — Select files and a destination folder; files are copied with SHA256 verification

## Recovery sources

| Source | Requires sudo | Notes |
|---|---|---|
| Trash | No | Scans user and volume-level trash |
| APFS Snapshots | Yes | Mounts local snapshots to find deleted files |
| Time Machine | Yes | Scans Time Machine backup volumes |
| Spotlight | No | Searches the Spotlight index for file metadata |
| PhotoRec | Yes | File carving via testdisk (`brew install testdisk`) |

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|---|---|---|
| `JERRY_HOST` | `127.0.0.1` | Bind address |
| `JERRY_PORT` | `8787` | Server port |
| `JERRY_DEBUG` | `false` | Enable debug mode |

## Known limitations

- Scan results are stored in memory and lost if the app restarts
- Runs on localhost only by default (intentional for security)
- PhotoRec requires `testdisk` to be installed separately
- Some scanners require Full Disk Access (System Settings > Privacy & Security)
