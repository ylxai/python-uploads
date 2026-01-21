# Hafiportrait Photographer Python Workflow (Standalone)

This folder is **standalone** and intentionally **gitignored**. It is meant to be copied to a photographer laptop.

## What it does (SIMPLE mode)
### Queue-based ingest + upload
- Watch (poll) `incoming/` for new files.
- **Ingest quickly** from `incoming/`:
  - RAW (`.nef/.cr2/.cr3/.arw/.dng/.rw2`) → moved to `raw/`
  - JPG/JPEG → moved to `jpg_in/` (this is the **upload queue/backlog**)
- Upload worker processes the backlog in `jpg_in/`:
  - validates JPG is fully written and readable
  - uploads to Hafiportrait event endpoint (API key)
  - moves results:
    - success → `uploaded/`
    - failure → `failed/`

### State / resume
- `state/state.json`
- last event memory: `state/last_event.json`

### Logs & summaries
- Logs are written to `logs/run-YYYYMMDD.log` and printed to console.
- Periodic `SUMMARY` is printed every ~60 seconds.
- On Ctrl+C, a `FINAL SUMMARY` is printed before exiting.

## Install
Python 3.10+ recommended.

Use a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Development / Tests

```bash
source .venv/bin/activate
pytest
```

## Folder structure
The script assumes these subfolders exist under the workflow root:

- `incoming/`
- `raw/`
- `jpg_in/`
- `processed/` (unused in simple mode)
- `uploaded/`
- `failed/`
- `tmp/`
- `state/`
- `logs/`

## Configuration (recommended)
Create a local `config.json` (it is **ignored by git**) by copying `config.example.json`:

```bash
cp config.example.json config.json
```

Fill in at least:
- `api_key`
- `event_id` (event UUID)

Optional but recommended:
- `logging.level` (e.g. `DEBUG` for troubleshooting)

> Placeholders like `YOUR_API_KEY` / `EVENT_UUID` are treated as missing and the script will error until you replace them.

### Priority order
Settings are resolved in this order:
1) CLI flags
2) Environment variables
3) `config.json`

## Running (interactive)
Interactive mode can:
- select event using `--events-source public` **without API key**
- store last selected event id to `state/last_event.json`

Note: API key is **not prompted**. Provide it via `config.json`, CLI, or environment variables.

Tip: enable debug logs with:
- `config.json`: `{ "logging": { "level": "DEBUG" } }`
- or CLI: `python3 run.py --log-level DEBUG ...`

See full examples in:
- `RUN_EXAMPLES.md`

## Running (examples)
For clean and complete run examples (Windows PowerShell vs WSL Bash), see:
- `RUN_EXAMPLES.md`

## Environment variables (alternative to config.json)
If you prefer not to keep a `config.json`, you can set environment variables instead.

Priority is still:
1) CLI flags
2) Environment variables
3) `config.json`

Supported env vars:
- `HAFI_API_BASE_URL` (default `https://hafiportrait.photography/api`)
- `HAFI_API_KEY`
- `HAFI_EVENT_ID`
- `HAFI_EVENTS_SOURCE` (`admin` or `public`)
- `HAFI_POLL_SECONDS` (default `2`)
- `HAFI_FILE_STABLE_SECONDS` (default `2`)
- `HAFI_UPLOAD_TIMEOUT_SECONDS` (default `120`)
- `HAFI_UPLOAD_RETRIES` (default `3`)
- `HAFI_LOG_LEVEL` (default `INFO`)

Example (Bash):
```bash
export HAFI_API_KEY="<API_KEY>"
export HAFI_EVENT_ID="<EVENT_UUID>"
python3 run.py
```

Tip: if you already selected an event once (saved in `state/last_event.json`), you can run:
```bash
python3 run.py --use-last-event
```

## Notes
- Upload endpoint requires the **event UUID** (not slug).
- The script does not depend on Next.js source code; it only uses HTTP API.
- If you want FULL mode (watermark + preset), it will be implemented later.
