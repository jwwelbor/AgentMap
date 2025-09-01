"""
Complexity analysis system for LLM routing.

This module provides intelligent complexity analysis for prompts and contexts,
helping to determine appropriate model selection based on task requirements.
"""

import re
from collections import Counter
from typing import Any, Dict, List

from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.routing.types import (
    ComplexitySignal,
    RoutingContext,
    TaskComplexity,
    get_complexity_order,
)


class PromptComplexityAnalyzer:
    """
    Comprehensive complexity analyzer for LLM routing decisions.

    Analyzes multiple signals including prompt length, keywords, structure,
    context, and memory to determine appropriate task complexity.
    """

    def __init__(
        self, configuration: AppConfigService, logging_service: LoggingService
    ):
        """
        Initialize the complexity analyzer with configuration.

        Args:
            config: Routing configuration section
        """
        self.config = configuration.get_routing_config()
        self.complexity_config = self.config["complexity_analysis"]

        # Load configuration settings
        self.length_thresholds = self._load_length_thresholds()
        self.analysis_methods = self._load_analysis_methods()
        self.keyword_weights = self._load_keyword_weights()
        self.context_thresholds = self._load_context_thresholds()
        self._logger = logging_service.get_class_logger(self)

        # Compile regex patterns for efficiency
        self._compile_patterns()

    def _load_length_thresholds(self) -> Dict[str, int]:
        """Load prompt length thresholds from configuration."""
        thresholds = self.complexity_config.get("prompt_length_thresholds", {})
        return {
            "low": thresholds.get("low", 100),
            "medium": thresholds.get("medium", 300),
            "high": thresholds.get("high", 800),
        }

    def _load_analysis_methods(self) -> Dict[str, bool]:
        """Load which analysis methods are enabled."""
        methods = self.complexity_config.get("methods", {})
        return {
            "prompt_length": methods.get("prompt_length", True),
            "keyword_analysis": methods.get("keyword_analysis", True),
            "context_analysis": methods.get("context_analysis", True),
            "memory_analysis": methods.get("memory_analysis", True),
            "structure_analysis": methods.get("structure_analysis", True),
        }

    def _load_keyword_weights(self) -> Dict[str, float]:
        """Load keyword analysis weights from configuration."""
        weights = self.complexity_config.get("keyword_weights", {})
        return {
            "complexity_keywords": weights.get("complexity_keywords", 0.4),
            "task_specific_keywords": weights.get("task_specific_keywords", 0.3),
            "prompt_structure": weights.get("prompt_structure", 0.3),
        }

    def _load_context_thresholds(self) -> Dict[str, int]:
        """Load context analysis thresholds."""
        context_config = self.complexity_config.get("context_analysis", {})
        return {
            "memory_size_threshold": context_config.get("memory_size_threshold", 10),
            "input_field_count_threshold": context_config.get(
                "input_field_count_threshold", 5
            ),
        }

    def _compile_patterns(self):
        """Compile regex patterns for prompt structure analysis."""
        self.patterns = {
            "questions": re.compile(
                r"\?|\bwhat\b|\bhow\b|\bwhy\b|\bwhen\b|\bwhere\b|\bwho\b", re.IGNORECASE
            ),
            "commands": re.compile(
                r"\banalyze\b|\bcreate\b|\bgenerate\b|\bexplain\b|\bcompare\b|\bwrite\b",
                re.IGNORECASE,
            ),
            "technical_terms": re.compile(
                r"\bAPI\b|\bJSON\b|\bSQL\b|\bHTTP\b|\balgorithm\b|\bfunction\b|\bclass\b",
                re.IGNORECASE,
            ),
            "complexity_indicators": re.compile(
                r"\bcomplex\b|\bdetailed\b|\bcomprehensive\b|\badvanced\b|\bin-depth\b",
                re.IGNORECASE,
            ),
            "urgency_indicators": re.compile(
                r"\burgent\b|\bcritical\b|\bemergency\b|\bimportant\b|\basap\b",
                re.IGNORECASE,
            ),
            "creative_indicators": re.compile(
                r"\bcreative\b|\bimagine\b|\bstory\b|\bnarrative\b|\bartistic\b|\binnovative\b",
                re.IGNORECASE,
            ),
        }

    def analyze_prompt_complexity(self, prompt: str) -> TaskComplexity:
        """Analyze prompt text to determine complexity."""
        if not prompt or not self.analysis_methods["prompt_length"]:
            return TaskComplexity.MEDIUM

        signals = []

        # Length-based analysis
        if self.analysis_methods["prompt_length"]:
            length_signal = self._analyze_prompt_length(prompt)
            signals.append(length_signal)

        # Keyword-based analysis
        if self.analysis_methods["keyword_analysis"]:
            keyword_signal = self._analyze_prompt_keywords(prompt)
            signals.append(keyword_signal)

        # Structure-based analysis
        if self.analysis_methods["structure_analysis"]:
            structure_signal = self._analyze_prompt_structure(prompt)
            signals.append(structure_signal)

        # Combine signals
        return self.combine_complexity_signals([s.complexity for s in signals])

    def _analyze_prompt_length(self, prompt: str) -> ComplexitySignal:
        """Analyze prompt length to determine complexity."""
        length = len(prompt)

        if length <= self.length_thresholds["low"]:
            complexity = TaskComplexity.LOW
            reasoning = f"Short prompt ({length} chars)"
            confidence = 0.8
        elif length <= self.length_thresholds["medium"]:
            complexity = TaskComplexity.MEDIUM
            reasoning = f"Medium-length prompt ({length} chars)"
            confidence = 0.7
        elif length <= self.length_thresholds["high"]:
            complexity = TaskComplexity.HIGH
            reasoning = f"Long prompt ({length} chars)"
            confidence = 0.8
        else:
            complexity = TaskComplexity.CRITICAL
            reasoning = f"Very long prompt ({length} chars)"
            confidence = 0.9

        return ComplexitySignal(
            complexity=complexity,
            confidence=confidence,
            reasoning=reasoning,
            source="prompt_length",
        )

    def _analyze_prompt_keywords(self, prompt: str) -> ComplexitySignal:
        """Analyze prompt keywords to determine complexity."""
        prompt.lower()
        complexity_scores = {
            TaskComplexity.LOW: 0,
            TaskComplexity.MEDIUM: 0,
            TaskComplexity.HIGH: 0,
            TaskComplexity.CRITICAL: 0,
        }

        # Check for urgency indicators (critical)
        urgency_matches = len(self.patterns["urgency_indicators"].findall(prompt))
        if urgency_matches > 0:
            complexity_scores[TaskComplexity.CRITICAL] += urgency_matches * 2.0

        # Check for complexity indicators (high)
        complexity_matches = len(self.patterns["complexity_indicators"].findall(prompt))
        if complexity_matches > 0:
            complexity_scores[TaskComplexity.HIGH] += complexity_matches * 1.5

        # Check for technical terms (medium-high)
        technical_matches = len(self.patterns["technical_terms"].findall(prompt))
        if technical_matches > 0:
            complexity_scores[TaskComplexity.HIGH] += technical_matches * 1.0
            complexity_scores[TaskComplexity.MEDIUM] += technical_matches * 0.5

        # Check for creative indicators (medium-high)
        creative_matches = len(self.patterns["creative_indicators"].findall(prompt))
        if creative_matches > 0:
            complexity_scores[TaskComplexity.HIGH] += creative_matches * 1.2
            complexity_scores[TaskComplexity.MEDIUM] += creative_matches * 0.8

        # Check for command complexity
        command_matches = len(self.patterns["commands"].findall(prompt))
        if command_matches > 2:
            complexity_scores[TaskComplexity.HIGH] += 1.0
        elif command_matches > 0:
            complexity_scores[TaskComplexity.MEDIUM] += 0.5

        # Determine final complexity based on highest score
        if not any(complexity_scores.values()):
            # No specific indicators found
            complexity = TaskComplexity.MEDIUM
            confidence = 0.3
            reasoning = "No specific complexity keywords found"
        else:
            complexity = max(
                complexity_scores.keys(), key=lambda k: complexity_scores[k]
            )
            max_score = complexity_scores[complexity]
            confidence = min(0.9, max_score / 5.0)  # Normalize to 0-0.9 range
            reasoning = f"Keyword analysis (score: {max_score:.1f})"

        return ComplexitySignal(
            complexity=complexity,
            confidence=confidence,
            reasoning=reasoning,
            source="keyword_analysis",
        )

    def _analyze_prompt_structure(self, prompt: str) -> ComplexitySignal:
        """Analyze prompt structure to determine complexity."""
        structure_score = 0
        reasoning_parts = []

        # Count sentences
        sentences = len([s for s in prompt.split(".") if s.strip()])
        if sentences > 5:
            structure_score += 1
            reasoning_parts.append(f"{sentences} sentences")

        # Count questions
        questions = len(self.patterns["questions"].findall(prompt))
        if questions > 3:
            structure_score += 1
            reasoning_parts.append(f"{questions} questions")

        # Check for multiple paragraphs
        paragraphs = len([p for p in prompt.split("\n\n") if p.strip()])
        if paragraphs > 2:
            structure_score += 1
            reasoning_parts.append(f"{paragraphs} paragraphs")

        # Check for lists or bullet points
        if "\n-" in prompt or "\n*" in prompt or "\n1." in prompt:
            structure_score += 1
            reasoning_parts.append("structured lists")

        # Determine complexity based on structure score
        if structure_score >= 3:
            complexity = TaskComplexity.HIGH
            confidence = 0.7
        elif structure_score >= 2:
            complexity = TaskComplexity.MEDIUM
            confidence = 0.6
        elif structure_score >= 1:
            complexity = TaskComplexity.MEDIUM
            confidence = 0.4
        else:
            complexity = TaskComplexity.LOW
            confidence = 0.5

        reasoning = f"Structure analysis: {', '.join(reasoning_parts) if reasoning_parts else 'simple structure'}"

        return ComplexitySignal(
            complexity=complexity,
            confidence=confidence,
            reasoning=reasoning,
            source="structure_analysis",
        )

    def analyze_context_complexity(self, context: Dict[str, Any]) -> TaskComplexity:
        """Analyze context information to determine complexity."""
        if not self.analysis_methods["context_analysis"]:
            return TaskComplexity.MEDIUM

        signals = []

        # Analyze input field count
        input_count = context.get("input_field_count", 0)
        if input_count > self.context_thresholds["input_field_count_threshold"]:
            signals.append(
                ComplexitySignal(
                    complexity=TaskComplexity.HIGH,
                    confidence=0.6,
                    reasoning=f"Many input fields ({input_count})",
                    source="context_analysis",
                )
            )
        elif input_count > 2:
            signals.append(
                ComplexitySignal(
                    complexity=TaskComplexity.MEDIUM,
                    confidence=0.5,
                    reasoning=f"Multiple input fields ({input_count})",
                    source="context_analysis",
                )
            )

        # Analyze context data complexity
        context_size = sum(
            len(str(v)) for v in context.values() if isinstance(v, (str, int, float))
        )
        if context_size > 1000:
            signals.append(
                ComplexitySignal(
                    complexity=TaskComplexity.HIGH,
                    confidence=0.5,
                    reasoning=f"Large context data ({context_size} chars)",
                    source="context_analysis",
                )
            )

        # If no signals, return medium complexity
        if not signals:
            return TaskComplexity.MEDIUM

        return self.combine_complexity_signals([s.complexity for s in signals])

    def analyze_memory_complexity(
        self, memory_size: int, memory_content: List[Dict[str, str]]
    ) -> TaskComplexity:
        """Analyze conversation memory to determine complexity."""
        if not self.analysis_methods["memory_analysis"] or memory_size == 0:
            return TaskComplexity.LOW

        signals = []

        # Memory size analysis
        if memory_size >= self.context_thresholds["memory_size_threshold"]:
            signals.append(
                ComplexitySignal(
                    complexity=TaskComplexity.HIGH,
                    confidence=0.7,
                    reasoning=f"Large conversation history ({memory_size} messages)",
                    source="memory_analysis",
                )
            )
        elif memory_size >= 5:
            signals.append(
                ComplexitySignal(
                    complexity=TaskComplexity.MEDIUM,
                    confidence=0.6,
                    reasoning=f"Moderate conversation history ({memory_size} messages)",
                    source="memory_analysis",
                )
            )

        # Memory content analysis
        if memory_content:
            total_content_length = sum(
                len(msg.get("content", "")) for msg in memory_content
            )
            if total_content_length > 2000:
                signals.append(
                    ComplexitySignal(
                        complexity=TaskComplexity.HIGH,
                        confidence=0.6,
                        reasoning=f"Extensive conversation content ({total_content_length} chars)",
                        source="memory_analysis",
                    )
                )

        if not signals:
            return TaskComplexity.LOW

        return self.combine_complexity_signals([s.complexity for s in signals])

    def analyze_task_type_complexity(
        self, task_type: str, prompt: str
    ) -> ComplexitySignal:
        """Analyze complexity based on task type and its keywords."""
        task_types = self.config.get("task_types", {})
        task_config = task_types.get(task_type, {})
        complexity_keywords = task_config.get("complexity_keywords", {})
        default_complexity = task_config.get("default_complexity", "medium")

        # Start with task type default
        base_complexity = TaskComplexity.from_string(default_complexity)

        # Check for task-specific complexity keywords
        prompt_lower = prompt.lower()
        keyword_scores = {}

        for complexity_level, keywords in complexity_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in prompt_lower:
                    score += 1
            if score > 0:
                keyword_scores[complexity_level] = score

        if keyword_scores:
            # Use the highest scoring complexity level
            max_complexity_level = max(
                keyword_scores.keys(), key=lambda k: keyword_scores[k]
            )
            detected_complexity = TaskComplexity.from_string(max_complexity_level)
            confidence = min(0.8, keyword_scores[max_complexity_level] / 3.0)
            reasoning = (
                f"Task-specific keywords for {task_type} ({max_complexity_level})"
            )
        else:
            detected_complexity = base_complexity
            confidence = 0.4
            reasoning = f"Default complexity for {task_type}"

        return ComplexitySignal(
            complexity=detected_complexity,
            confidence=confidence,
            reasoning=reasoning,
            source="task_type_analysis",
        )

    def combine_complexity_signals(
        self, signals: List[TaskComplexity]
    ) -> TaskComplexity:
        """Combine multiple complexity signals into final determination."""
        if not signals:
            return TaskComplexity.MEDIUM

        # Count occurrences of each complexity level
        signal_counts = Counter(signals)

        # If we have a clear majority, use it
        if len(signal_counts) == 1:
            return signals[0]

        # Weight by complexity level (higher complexity levels have more influence)
        get_complexity_order()
        weighted_score = 0
        total_weight = 0

        for complexity, count in signal_counts.items():
            weight = complexity.value * count  # Higher complexity = higher value
            weighted_score += weight
            total_weight += count

        # Calculate average complexity index
        avg_complexity_value = weighted_score / total_weight if total_weight > 0 else 2

        # Map back to complexity level
        if avg_complexity_value <= 1.3:
            return TaskComplexity.LOW
        elif avg_complexity_value <= 2.3:
            return TaskComplexity.MEDIUM
        elif avg_complexity_value <= 3.3:
            return TaskComplexity.HIGH
        else:
            return TaskComplexity.CRITICAL

    def determine_overall_complexity(
        self, prompt: str, task_type: str, routing_context: RoutingContext
    ) -> TaskComplexity:
        """Determine overall complexity using all available analysis methods."""
        # Check for complexity override first
        if routing_context.complexity_override:
            try:
                return TaskComplexity.from_string(routing_context.complexity_override)
            except ValueError:
                self._logger.warning(
                    f"Invalid complexity override: {routing_context.complexity_override}"
                )

        # Skip analysis if auto-detect is disabled
        if not routing_context.auto_detect_complexity:
            task_types = self.config.get("task_types", {})
            task_config = task_types.get(task_type, {})
            default_complexity = task_config.get("default_complexity", "medium")
            return TaskComplexity.from_string(default_complexity)

        signals = []

        # Prompt analysis
        prompt_complexity = self.analyze_prompt_complexity(prompt)
        signals.append(prompt_complexity)

        # Task type analysis
        task_signal = self.analyze_task_type_complexity(task_type, prompt)
        signals.append(task_signal.complexity)

        # Context analysis
        if routing_context.input_context:
            context_complexity = self.analyze_context_complexity(
                routing_context.input_context
            )
            signals.append(context_complexity)

        # Memory analysis
        if routing_context.memory_size > 0:
            memory_complexity = self.analyze_memory_complexity(
                routing_context.memory_size, []
            )
            signals.append(memory_complexity)

        # Combine all signals
        final_complexity = self.combine_complexity_signals(signals)

        self._logger.debug(
            f"Complexity analysis for {task_type}: {[str(s) for s in signals]} -> {final_complexity}"
        )

        return final_complexity
