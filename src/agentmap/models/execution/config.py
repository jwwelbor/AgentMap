"""
Execution configuration model for graph execution with checkpoint support.

This model encapsulates configuration needed for graph execution,
including checkpoint services, thread IDs, and resumption settings.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver


@dataclass
class ExecutionConfig:
    """
    Configuration for graph execution with checkpoint and resumption support.

    This configuration object encapsulates all settings needed to execute
    a graph with checkpoint support, including thread management and
    state resumption capabilities.

    Attributes:
        thread_id: Unique identifier for this execution thread.
                  Used to link execution state with checkpoints.
        checkpointer: Optional checkpoint service for state persistence.
                     When provided, enables pause/resume functionality.
        initial_state: Initial state to pass to the graph.
                      Can include resume data like human responses.
        resume_from_checkpoint: Flag indicating if this is a resume operation.
                               When True, graph will load from checkpoint.
        metadata: Additional metadata for the execution.
                 Can include bundle info, user context, etc.
    """

    thread_id: str
    checkpointer: Optional[BaseCheckpointSaver] = None
    initial_state: Optional[Dict[str, Any]] = None
    resume_from_checkpoint: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_langgraph_config(self) -> Dict[str, Any]:
        """
        Convert to LangGraph-compatible configuration dictionary.

        Returns:
            Dictionary with 'configurable' section for LangGraph
        """
        config = {"configurable": {"thread_id": self.thread_id}}

        # Add any additional metadata to configurable
        if self.metadata:
            config["configurable"].update(self.metadata)

        return config

    def get_merged_initial_state(
        self, base_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Merge configuration initial state with provided base state.

        Args:
            base_state: Optional base state to merge with

        Returns:
            Merged state dictionary
        """
        merged = base_state.copy() if base_state else {}

        if self.initial_state:
            merged.update(self.initial_state)

        # Add execution flags
        if self.resume_from_checkpoint:
            merged["__resuming_from_checkpoint"] = True
            merged["__thread_id"] = self.thread_id

        return merged

    @classmethod
    def for_new_execution(
        cls,
        thread_id: str,
        initial_state: Optional[Dict[str, Any]] = None,
        checkpointer: Optional[BaseCheckpointSaver] = None,
    ) -> "ExecutionConfig":
        """
        Create configuration for a new graph execution.

        Args:
            thread_id: Unique thread identifier
            initial_state: Optional initial state
            checkpointer: Optional checkpoint service

        Returns:
            ExecutionConfig for new execution
        """
        return cls(
            thread_id=thread_id,
            checkpointer=checkpointer,
            initial_state=initial_state,
            resume_from_checkpoint=False,
        )

    @classmethod
    def for_resume(
        cls,
        thread_id: str,
        checkpointer: BaseCheckpointSaver,
        resume_state: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ExecutionConfig":
        """
        Create configuration for resuming from checkpoint.

        Args:
            thread_id: Thread ID to resume (must match checkpoint)
            checkpointer: Checkpoint service with saved state
            resume_state: Optional state to inject (e.g., human response)
            metadata: Optional metadata about the resumption

        Returns:
            ExecutionConfig for resumption
        """
        return cls(
            thread_id=thread_id,
            checkpointer=checkpointer,
            initial_state=resume_state,
            resume_from_checkpoint=True,
            metadata=metadata or {},
        )
