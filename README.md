# inter-macro

Color-detection based screen automation with profile JSON, retry logic, and hotkey trigger.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Calibrate

```bash
python3 main.py --calibrate --profile profiles/default.json
```

## Run

```bash
python3 main.py --listen --profile profiles/default.json
```

Press `ESC` to stop listener.

## One-shot / test mode

```bash
python3 main.py --once --dry-run --profile profiles/default.json
```

