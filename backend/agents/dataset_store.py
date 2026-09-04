"""Per-user uploaded dataset registry (disk paths + metadata).

The CSV is written to disk and a manifest.json is kept so the dataset
survives process restarts and in-memory cache misses (e.g. uvicorn reload).
"""
from __future__ import annotations

import json
import os
import re
from threading import Lock
from typing import Dict, List, Optional

from Pages.data_models import InputData

UPLOAD_ROOT = os.path.abspath(os.getenv("UPLOAD_DIR", "uploads"))
_lock = Lock()
# user_id -> list of InputData
_store: Dict[int, List[InputData]] = {}


def _safe_filename(name: str) -> str:
    base = os.path.basename(name)
    return re.sub(r"[^\w.\-]", "_", base) or "dataset.csv"


def _variable_name(filename: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    cleaned = re.sub(r"\W+", "_", stem).strip("_") or "df"
    if cleaned[0].isdigit():
        cleaned = f"df_{cleaned}"
    return cleaned


def _user_dir(user_id: int) -> str:
    return os.path.join(UPLOAD_ROOT, str(user_id))


def _manifest_path(user_id: int) -> str:
    return os.path.join(_user_dir(user_id), "manifest.json")


def _item_to_dict(item: InputData) -> dict:
    return {
        "variable_name": item.variable_name,
        "data_path": item.data_path,
        "data_description": item.data_description,
    }


def _item_from_dict(raw: dict) -> Optional[InputData]:
    path = raw.get("data_path")
    if not path or not os.path.isfile(path):
        return None
    return InputData(
        variable_name=raw.get("variable_name") or "df",
        data_path=os.path.abspath(path),
        data_description=raw.get("data_description") or "",
    )


def _write_manifest(user_id: int, datasets: List[InputData]) -> None:
    os.makedirs(_user_dir(user_id), exist_ok=True)
    with open(_manifest_path(user_id), "w", encoding="utf-8") as f:
        json.dump([_item_to_dict(d) for d in datasets], f, ensure_ascii=False, indent=2)


def _load_manifest(user_id: int) -> List[InputData]:
    path = _manifest_path(user_id)
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            items = [_item_from_dict(x) for x in raw if isinstance(x, dict)]
            found = [i for i in items if i is not None]
            if found:
                return found
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    # Fallback: any CSV left on disk for this user
    user_dir = _user_dir(user_id)
    if not os.path.isdir(user_dir):
        return []
    recovered: List[InputData] = []
    for name in sorted(os.listdir(user_dir)):
        if not name.lower().endswith(".csv"):
            continue
        full = os.path.abspath(os.path.join(user_dir, name))
        recovered.append(
            InputData(
                variable_name="df",
                data_path=full,
                data_description=f"Uploaded file {name}",
            )
        )
    return recovered


def save_upload(user_id: int, filename: str, content: bytes, description: str = "") -> InputData:
    """Persist an uploaded file and register it for the user as `df` (LLM default)."""
    user_dir = _user_dir(user_id)
    os.makedirs(user_dir, exist_ok=True)

    safe_name = _safe_filename(filename)
    path = os.path.abspath(os.path.join(user_dir, safe_name))
    with open(path, "wb") as f:
        f.write(content)

    source_name = _variable_name(safe_name)
    item = InputData(
        variable_name="df",
        data_path=path,
        data_description=description or f"Uploaded file {safe_name} (also available as {source_name})",
    )
    with _lock:
        datasets = _store.setdefault(user_id, [])
        datasets[:] = [d for d in datasets if d.data_path != path]
        datasets.append(item)
        _write_manifest(user_id, datasets)
    return item


def get_datasets(user_id: int) -> List[InputData]:
    with _lock:
        cached = list(_store.get(user_id, []))
        if cached:
            return cached
        recovered = _load_manifest(user_id)
        if recovered:
            _store[user_id] = recovered
        return list(recovered)


def set_primary_dataset(user_id: int, item: InputData) -> None:
    with _lock:
        _store[user_id] = [item]
        _write_manifest(user_id, [item])


def clear_user(user_id: int) -> None:
    with _lock:
        _store.pop(user_id, None)


def latest_dataset(user_id: int) -> Optional[InputData]:
    datasets = get_datasets(user_id)
    return datasets[-1] if datasets else None
