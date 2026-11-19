"""Storage helper mixin."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from agentmap.models.storage.types import StorageResult, WriteMode

if TYPE_CHECKING:
    from agentmap.services.storage.file_service import FileStorageService


class StorageHelpersMixin:
    if TYPE_CHECKING:
        file_storage: FileStorageService
        threads_collection: str

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

    def _write_collection(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        **kwargs: Any,
    ) -> StorageResult[Any]:
        return self.file_storage.write(
            collection=self._normalize_collection_name(collection),
            data=data,
            document_id=document_id,
            mode=mode,
            **kwargs,
        )

    def _read_collection(
        self, collection: str, document_id: Optional[str] = None, **kwargs: Any
    ) -> Any:
        return self.file_storage.read(
            collection=self._normalize_collection_name(collection),
            document_id=document_id,
            **kwargs,
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
