from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data"
DATA_PATH.mkdir(parents=True, exist_ok=True)
