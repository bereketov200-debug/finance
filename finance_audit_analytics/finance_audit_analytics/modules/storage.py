"""Local JSON repository with validation and atomic, same-directory replacement."""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock

from .models import DEFAULT_SETTINGS, budget, review, settings, transaction


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_LOCK = RLock()
_COLLECTIONS = {
    "transactions": (transaction, lambda row: row["id"].casefold()),
    "budgets": (budget, lambda row: (row["month"], row["category"])),
    "audit_reviews": (review, lambda row: row["finding_id"]),
}


class StorageError(RuntimeError):
    """A filesystem or data integrity problem that can be shown to the user."""


class Store:
    def __init__(self, root=None):
        self.root = Path(root if root is not None else os.getenv("FINANCE_DATA_DIR", DATA_DIR))
        self.warnings = []
        with _LOCK:
            try:
                self.root.mkdir(parents=True, exist_ok=True)
                for name in (*_COLLECTIONS, "settings"):
                    if not self._path(name).exists():
                        self._write(name, self._default(name))
            except OSError as error:
                raise StorageError(f"Cannot initialize the data folder: {error}") from error

    def _path(self, name):
        if name not in (*_COLLECTIONS, "settings"):
            raise ValueError(f"Unknown dataset: {name}")
        return self.root / f"{name}.json"

    @staticmethod
    def _default(name):
        return DEFAULT_SETTINGS.copy() if name == "settings" else []

    def _write(self, name, value):
        target = self._path(name)
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.root,
                                    prefix=f".{name}-", suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        except OSError as error:
            raise StorageError(f"Could not save {target.name}: {error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _validate(self, name, value):
        if name == "settings":
            return settings(value), []
        if not isinstance(value, list):
            raise ValueError("Expected a JSON array.")
        validate, identity = _COLLECTIONS[name]
        result, problems, seen = [], [], set()
        for index, record in enumerate(value, 1):
            try:
                if not isinstance(record, dict):
                    raise ValueError("Expected an object.")
                item = validate(record)
                key = identity(item)
                if key in seen:
                    raise ValueError("Duplicate record key.")
                seen.add(key)
                result.append(item)
            except (ValueError, KeyError, TypeError) as error:
                problems.append(f"record {index}: {error}")
        return result, problems

    def _read(self, name, strict):
        target = self._path(name)
        try:
            raw = json.loads(target.read_text(encoding="utf-8-sig"))
            result, problems = self._validate(name, raw)
        except (OSError, ValueError, KeyError, TypeError) as error:
            result, problems = self._default(name), [str(error)]
        if problems:
            detail = "; ".join(problems[:3])
            message = f"{target.name} has {len(problems)} issue(s). {detail} Back up and repair the file before saving changes to it."
            if strict:
                raise StorageError(message)
            if message not in self.warnings:
                self.warnings.append(message)
        return result

    def read(self, name):
        with _LOCK:
            return self._read(name, strict=False)

    def update(self, name, change):
        """Validate the current file and candidate before committing one dataset."""
        with _LOCK:
            current = self._read(name, strict=True)
            candidate, problems = self._validate(name, change(current))
            if problems:
                raise ValueError("; ".join(problems[:3]))
            self._write(name, candidate)
            return candidate
