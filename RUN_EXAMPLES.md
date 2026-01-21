# Run Examples (Windows PowerShell vs WSL Bash)

> This workflow is designed to run on a photographer laptop. It can run either on Windows Python or inside WSL.

## How SIMPLE mode works (queue-based)
- Drop new exports into `incoming/`.
- The workflow quickly **ingests** files from `incoming/`:
  - RAW files → moved to `raw/`
  - JPG files → moved to `jpg_in/` (this is the **upload queue/backlog**)
- Upload worker processes the backlog in `jpg_in/`:
  - success → moved to `uploaded/`
  - failure → moved to `failed/`

### Logs & summaries
- The workflow writes logs to `logs/run-YYYYMMDD.log` and prints to console.
- Every ~60 seconds it prints a `SUMMARY` line (backlog + how many succeeded/failed in that interval).
- On Ctrl+C it prints `FINAL SUMMARY` (totals + backlog + failure categories) before exiting.

To see detailed skip/retry/debug logs, set log level to `DEBUG`:
- `config.json`:
  ```json
  {"logging": {"level": "DEBUG"}}
  ```
- or CLI: `python run.py --log-level DEBUG ...`

## 1) Windows (PowerShell)

### Install
```powershell
cd python-workflow
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Run tests (optional)
pytest
```

### Recommended: config.json (one-time)
Copy `config.example.json` to `config.json` (this file is ignored by git), then fill your `api_key` and (optionally) `event_id`.

```powershell
Copy-Item config.example.json config.json
notepad config.json
```

### Interactive (select event from public list)
This will save the chosen event UUID to `state/last_event.json`.

```powershell
python run.py --interactive --events-source public
```

### Non-interactive (explicit event UUID)
```powershell
python run.py --api-key "<API_KEY>" --event-id "<EVENT_UUID>"
```

### Non-interactive (use last selected event)
If you saved `api_key` in `config.json`, you don't need to pass `--api-key`.

```powershell
python run.py --use-last-event
```

### Notes for Windows folders
- Put exported JPGs into: `python-workflow\incoming\`
- RAW files will be moved to: `python-workflow\raw\`
- Successful uploads move to: `python-workflow\uploaded\`
- Failures move to: `python-workflow\failed\`

---

## 2) WSL (Ubuntu / Bash)

### Install
```bash
cd python-workflow
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests (optional)
pytest
```

### Recommended: config.json (one-time)
Copy `config.example.json` to `config.json` (this file is ignored by git), then fill your `api_key` and (optionally) `event_id`.

```bash
cp config.example.json config.json
nano config.json
```

### Interactive (select event from public list)
This will save the chosen event UUID to `state/last_event.json`.

```bash
python3 run.py --interactive --events-source public
```

### Non-interactive (explicit event UUID)
```bash
python3 run.py --api-key "<API_KEY>" --event-id "<EVENT_UUID>"
```

### Non-interactive (use last selected event)
If you saved `api_key` in `config.json`, you don't need to pass `--api-key`.

```bash
python3 run.py --use-last-event
```

---

## 3) WSL + Windows folder (recommended if darktable exports into Windows)

Example: darktable exports to Windows path:
- `C:\Users\<YOU>\Pictures\hafiportrait\incoming`

In WSL, that becomes:
- `/mnt/c/Users/<YOU>/Pictures/hafiportrait/incoming`

You can run the workflow with `--root` pointing to the folder that contains `incoming/ raw/ jpg_in/ ...`.

```bash
python3 run.py \
  --root "/mnt/c/Users/<YOU>/Pictures/hafiportrait" \
  --interactive --events-source public
```

---

## 4) Environment variables (Bash)
```bash
export HAFI_API_KEY="<API_KEY>"
export HAFI_EVENT_ID="<EVENT_UUID>"
python3 run.py
```

## 5) Environment variables (PowerShell)
```powershell
$env:HAFI_API_KEY = "<API_KEY>"
$env:HAFI_EVENT_ID = "<EVENT_UUID>"
python run.py
```
