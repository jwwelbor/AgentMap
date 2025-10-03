"""
Core types and interfaces for LLM routing system.

This module defines the foundational types, enums, and protocols that all
routing components depend on.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol


class TaskComplexity(Enum):
    """
    Enumeration of task complexity levels for LLM routing.

    Used to determine appropriate model selection based on task requirements.
    """

    LOW = 1  # Simple responses, basic information retrieval
    MEDIUM = 2  # Standard dialogue, processing, moderate analysis
    HIGH = 3  # Complex analysis, creative content, detailed reasoning
    CRITICAL = 4  # Mission-critical decisions, advanced reasoning

    def __str__(self) -> str:
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> "TaskComplexity":
        """Create TaskComplexity from string value."""
        try:
            return cls[value.upper()]
        except KeyError:
            raise ValueError(f"Invalid complexity level: {value}")


class TaskType(Enum):
    """
    Enumeration of task types for specialized LLM routing.

    Different task types may have different provider preferences and
    complexity characteristics.
    """

    GENERAL = "general"  # General purpose tasks
    ANALYSIS = "analysis"  # Data analysis, reasoning
    CREATIVE = "creative"  # Creative writing, content generation
    DIALOGUE = "dialogue"  # Conversational interactions
    TECHNICAL = "technical"  # Code, documentation, technical tasks
    CUSTOMER_SERVICE = "customer_service"  # Customer support interactions
    DATA_ANALYSIS = "data_analysis"  # Data processing and insights
    CREATIVE_WRITING = "creative_writing"  # Story, narrative, artistic content
    CODE_ANALYSIS = "code_analysis"  # Code review, programming tasks

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_string(cls, value: str) -> "TaskType":
        """Create TaskType from string value."""
        try:
            return cls(value)
        except ValueError:
            # If exact match fails, try case-insensitive search
            for task_type in cls:
                if task_type.value.lower() == value.lower():
                    return task_type
            raise ValueError(f"Invalid task type: {value}")


@dataclass
class RoutingContext:
    """
    Context information for LLM routing decisions.

    Contains all the information needed to make intelligent routing decisions
    including task type, complexity preferences, and provider constraints.
    """

    # Core routing parameters
    task_type: str = "general"
    routing_enabled: bool = False

    # Complexity control
    complexity_override: Optional[str] = None
    auto_detect_complexity: bool = True

    # Provider preferences
    activity: Optional[str] = None
    provider_preference: List[str] = field(default_factory=list)
    excluded_providers: List[str] = field(default_factory=list)

    # Model constraints
    model_override: Optional[str] = None
    max_cost_tier: Optional[str] = None  # low, medium, high, critical

    # Input context for complexity analysis
    prompt: str = ""
    input_context: Dict[str, Any] = field(default_factory=dict)
    memory_size: int = 0
    input_field_count: int = 0

    # Cost and performance preferences
    cost_optimization: bool = True
    prefer_speed: bool = False
    prefer_quality: bool = False

    # Fallback configuration
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None
    retry_with_lower_complexity: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert routing context to dictionary."""
        return {
            "task_type": self.task_type,
            "routing_enabled": self.routing_enabled,
            "activity": self.activity,
            "complexity_override": self.complexity_override,
            "auto_detect_complexity": self.auto_detect_complexity,
            "provider_preference": self.provider_preference,
            "excluded_providers": self.excluded_providers,
            "model_override": self.model_override,
            "max_cost_tier": self.max_cost_tier,
            "prompt": self.prompt,
            "input_context": self.input_context,
            "memory_size": self.memory_size,
            "input_field_count": self.input_field_count,
            "cost_optimization": self.cost_optimization,
            "prefer_speed": self.prefer_speed,
            "prefer_quality": self.prefer_quality,
            "fallback_provider": self.fallback_provider,
            "fallback_model": self.fallback_model,
            "retry_with_lower_complexity": self.retry_with_lower_complexity,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingContext":
        """Create RoutingContext from dictionary."""
        return cls(
            task_type=data.get("task_type", "general"),
            routing_enabled=data.get("routing_enabled", False),
            complexity_override=data.get("complexity_override"),
            auto_detect_complexity=data.get("auto_detect_complexity", True),
            provider_preference=data.get("provider_preference", []),
            excluded_providers=data.get("excluded_providers", []),
            activity=data.get("activity"),
            model_override=data.get("model_override"),
            max_cost_tier=data.get("max_cost_tier"),
            prompt=data.get("prompt", ""),
            input_context=data.get("input_context", {}),
            memory_size=data.get("memory_size", 0),
            input_field_count=data.get("input_field_count", 0),
            cost_optimization=data.get("cost_optimization", True),
            prefer_speed=data.get("prefer_speed", False),
            prefer_quality=data.get("prefer_quality", False),
            fallback_provider=data.get("fallback_provider"),
            fallback_model=data.get("fallback_model"),
            retry_with_lower_complexity=data.get("retry_with_lower_complexity", True),
        )


@dataclass
class RoutingDecision:
    """
    Result of a routing decision.

    Contains the selected provider, model, and metadata about the decision.
    """

    provider: str
    model: str
    complexity: TaskComplexity
    confidence: float = 1.0  # 0.0 to 1.0 confidence in the decision
    reasoning: str = ""  # Human-readable explanation of the decision
    fallback_used: bool = False
    cache_hit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert routing decision to dictionary."""
        return {
            "provider": self.provider,
            "model": self.model,
            "complexity": str(self.complexity),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "fallback_used": self.fallback_used,
            "cache_hit": self.cache_hit,
        }


@dataclass
class ComplexitySignal:
    """
    A single complexity signal with metadata.

    Used to track individual complexity indicators and their confidence levels.
    """

    complexity: TaskComplexity
    confidence: float  # 0.0 to 1.0
    reasoning: str  # Human-readable explanation
    source: str  # Which analyzer produced this signal

    def __post_init__(self):
        """Validate signal data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


class ComplexityAnalyzer(Protocol):
    """
    Protocol for analyzing task complexity.

    Implementations should analyze various signals to determine the appropriate
    complexity level for a given task.
    """

    def analyze_prompt_complexity(self, prompt: str) -> TaskComplexity:
        """
        Analyze prompt text to determine complexity.

        Args:
            prompt: The prompt text to analyze

        Returns:
            Determined complexity level
        """
        ...

    def analyze_context_complexity(self, context: Dict[str, Any]) -> TaskComplexity:
        """
        Analyze context information to determine complexity.

        Args:
            context: Context dictionary with various signals

        Returns:
            Determined complexity level
        """
        ...

    def analyze_memory_complexity(
        self, memory_size: int, memory_content: List[Dict[str, str]]
    ) -> TaskComplexity:
        """
        Analyze conversation memory to determine complexity.

        Args:
            memory_size: Number of messages in memory
            memory_content: List of memory messages

        Returns:
            Determined complexity level
        """
        ...

    def combine_complexity_signals(
        self, signals: List[TaskComplexity]
    ) -> TaskComplexity:
        """
        Combine multiple complexity signals into final determination.

        Args:
            signals: List of complexity signals from different analyzers

        Returns:
            Final complexity determination
        """
        ...


class LLMRouter(Protocol):
    """
    Protocol for LLM routing implementations.

    Defines the interface for routing LLM requests to appropriate providers
    and models based on task requirements and constraints.
    """

    def determine_complexity(
        self, task_type: str, prompt: str, context: RoutingContext
    ) -> TaskComplexity:
        """
        Determine the complexity level for a routing request.

        Args:
            task_type: Type of task being performed
            prompt: The prompt text
            context: Additional routing context

        Returns:
            Determined complexity level
        """
        ...

    def select_optimal_model(
        self,
        task_type: str,
        complexity: TaskComplexity,
        available_providers: List[str],
        routing_context: RoutingContext,
    ) -> RoutingDecision:
        """
        Select the optimal provider and model for a request.

        Args:
            task_type: Type of task being performed
            complexity: Determined complexity level
            available_providers: List of available providers
            routing_context: Additional routing context and preferences

        Returns:
            Routing decision with selected provider and model
        """
        ...

    def route_request(
        self,
        prompt: str,
        task_type: str,
        available_providers: List[str],
        routing_context: RoutingContext,
    ) -> RoutingDecision:
        """
        Perform end-to-end routing for an LLM request.

        Args:
            prompt: The prompt text
            task_type: Type of task being performed
            available_providers: List of available providers
            routing_context: Routing context and preferences

        Returns:
            Complete routing decision
        """
        ...


# Utility functions for working with routing types


def normalize_task_type(task_type: str) -> str:
    """
    Normalize task type string to standard format.

    Args:
        task_type: Raw task type string

    Returns:
        Normalized task type string
    """
    if not task_type:
        return "general"

    # Convert to lowercase and replace common separators
    normalized = task_type.lower().replace("-", "_").replace(" ", "_")

    # Map common aliases
    aliases = {
        "chat": "dialogue",
        "conversation": "dialogue",
        "coding": "code_analysis",
        "programming": "code_analysis",
        "writing": "creative_writing",
        "story": "creative_writing",
        "support": "customer_service",
        "help": "customer_service",
        "data": "data_analysis",
        "analytics": "data_analysis",
    }

    return aliases.get(normalized, normalized)


def normalize_complexity(complexity: str) -> str:
    """
    Normalize complexity string to standard format.

    Args:
        complexity: Raw complexity string

    Returns:
        Normalized complexity string
    """
    if not complexity:
        return "medium"

    normalized = complexity.lower().strip()

    # Map common aliases
    aliases = {
        "simple": "low",
        "basic": "low",
        "easy": "low",
        "standard": "medium",
        "normal": "medium",
        "moderate": "medium",
        "advanced": "high",
        "complex": "high",
        "difficult": "high",
        "urgent": "critical",
        "emergency": "critical",
        "important": "critical",
    }

    return aliases.get(normalized, normalized)


def get_complexity_order() -> List[TaskComplexity]:
    """
    Get complexity levels in order from lowest to highest.

    Returns:
        List of complexity levels in ascending order
    """
    return [
        TaskComplexity.LOW,
        TaskComplexity.MEDIUM,
        TaskComplexity.HIGH,
        TaskComplexity.CRITICAL,
    ]


def get_valid_task_types() -> List[str]:
    """
    Get list of all valid task type values.

    Returns:
        List of valid task type strings
    """
    return [task_type.value for task_type in TaskType]


def get_valid_complexity_levels() -> List[str]:
    """
    Get list of all valid complexity level values.

    Returns:
        List of valid complexity level strings
    """
    return [complexity.name.lower() for complexity in TaskComplexity]
