"""
File-backed JSON persistence for LLMBatchHandle objects (E05-F03).

Persists batch handles to a directory as ``{agentmap_batch_id}.json`` files.
No ``api_key`` is ever written to disk — credentials are injected at adapter
level and are never part of the handle.
"""

import json
import os
import tempfile
from typing import Any, Dict

from agentmap.models.llm_execution import LLMBatchHandle


class BatchHandleRepository:
    """
    File-backed repository for ``LLMBatchHandle`` persistence.

    Each handle is stored as ``{batch_dir}/{agentmap_batch_id}.json``.
    The batch directory is created on first save (F-HIGH-1 fix).
    Writes are atomic via a temp file + os.replace (TD-2 fix).
    """

    def __init__(self, batch_dir: str) -> None:
        self._batch_dir = batch_dir

    def save(self, handle: LLMBatchHandle) -> None:
        """
        Serialize ``handle`` to a JSON file in the batch directory.

        Creates ``batch_dir`` if it does not exist (including nested parents),
        then writes atomically via a temp file + ``os.replace`` so a crash
        mid-write cannot leave a partial/corrupt JSON file.
        """
        os.makedirs(self._batch_dir, exist_ok=True)
        data = handle.to_dict()
        file_path = os.path.join(self._batch_dir, f"{handle.agentmap_batch_id}.json")
        # Atomic write: write to a temp file in the same dir, then replace.
        dir_fd = os.open(self._batch_dir, os.O_RDONLY)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._batch_dir,
                delete=False,
                suffix=".tmp",
            ) as tmp:
                tmp_path = tmp.name
                json.dump(data, tmp, indent=2)
            os.replace(tmp_path, file_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        finally:
            os.close(dir_fd)

    def load(self, agentmap_batch_id: str) -> LLMBatchHandle:
        """Load a handle from disk by its agentmap_batch_id."""
        file_path = os.path.join(self._batch_dir, f"{agentmap_batch_id}.json")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.load_from_dict(data)

    @staticmethod
    def load_from_dict(data: Dict[str, Any]) -> LLMBatchHandle:
        """
        Reconstruct an ``LLMBatchHandle`` from a serialized dict.

        This is the production entrypoint for repo-layer restore.
        Preserves ``spec_id_map`` and all identity fields exactly.
        """
        return LLMBatchHandle.from_dict(data)
