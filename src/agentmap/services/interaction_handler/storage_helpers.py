"""Storage helper mixin."""

from pathlib import Path
from typing import Optional


class StorageHelpersMixin:
    def _normalize_collection_name(self, collection: str) -> str:
        if not collection:
            return ""
        base_dir = str(self.file_storage.client.get("base_directory", ""))
        base_dir_normalized = base_dir.replace("\\", "/").rstrip("/")
        collection_normalized = str(collection).replace("\\", "/").strip("/")
        if base_dir_normalized and collection_normalized.startswith(
            base_dir_normalized
        ):
            return collection_normalized[len(base_dir_normalized) :].lstrip("/") or ""
        return collection_normalized

    def _write_collection(self, collection: str, **kwargs):
        return self.file_storage.write(
            collection=self._normalize_collection_name(collection), **kwargs
        )

    def _read_collection(self, collection: str, **kwargs):
        return self.file_storage.read(
            collection=self._normalize_collection_name(collection), **kwargs
        )

    def _find_legacy_thread_file(self, thread_id: str) -> Optional[Path]:
        base_dir_value = self.file_storage.client.get("base_directory")
        if not base_dir_value:
            return None
        base_dir = Path(base_dir_value)
        expected_path = (
            base_dir
            / self._normalize_collection_name(self.threads_collection)
            / f"{thread_id}.pkl"
        )
        if expected_path.exists():
            return expected_path
        if not base_dir.exists():
            return None
        for path in base_dir.rglob(f"{thread_id}.pkl"):
            if path != expected_path:
                return path
        return None
