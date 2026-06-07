"""
File-backed JSON persistence for LLMBatchHandle objects (E05-F03).

Persists batch handles to a directory as ``{agentmap_batch_id}.json`` files.
No ``api_key`` is ever written to disk — credentials are injected at adapter
level and are never part of the handle.
"""

import json
import os
from typing import Any, Dict

from agentmap.models.llm_execution import LLMBatchHandle


class BatchHandleRepository:
    """
    File-backed repository for ``LLMBatchHandle`` persistence.

    Each handle is stored as ``{batch_dir}/{agentmap_batch_id}.json``.
    """

    def __init__(self, batch_dir: str) -> None:
        self._batch_dir = batch_dir

    def save(self, handle: LLMBatchHandle) -> None:
        """Serialize ``handle`` to a JSON file in the batch directory."""
        data = handle.to_dict()
        file_path = os.path.join(self._batch_dir, f"{handle.agentmap_batch_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

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
