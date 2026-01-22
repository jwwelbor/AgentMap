"""
Algorithm-based matching utilities for OrchestratorService.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple


class AlgorithmMatcher:
    def __init__(
        self, logger: logging.Logger, nlp_capabilities: Optional[Dict[str, Any]] = None
    ):
        self.logger = logger
        self._nlp_capabilities = nlp_capabilities

    def parse_node_keywords(self, node_info: Dict[str, Any]) -> List[str]:
        keywords = []
        text_fields = [
            node_info.get("description", ""),
            node_info.get("prompt", ""),
            node_info.get("intent", ""),
            node_info.get("name", ""),
        ]
        context = node_info.get("context", {})
        if isinstance(context, dict):
            if "keywords" in context:
                keywords_field = context["keywords"]
                if isinstance(keywords_field, str):
                    keywords.extend(keywords_field.split(","))
                elif isinstance(keywords_field, list):
                    keywords.extend(keywords_field)
            text_fields.extend(
                [
                    context.get("description", ""),
                    context.get("intent", ""),
                    context.get("purpose", ""),
                ]
            )
        combined_text = " ".join(field for field in text_fields if field)
        if combined_text:
            keywords.extend(
                combined_text.lower().replace(",", " ").replace(";", " ").split()
            )
        unique_keywords = list(
            set(keyword.strip() for keyword in keywords if keyword.strip())
        )
        return [
            kw
            for kw in unique_keywords
            if len(kw) > 2 and kw not in ["the", "and", "for", "with"]
        ]

    def fuzzy_keyword_match(
        self, input_text: str, keywords: List[str], threshold: int = 80
    ) -> Tuple[float, List[str]]:
        if not self._nlp_capabilities or not self._nlp_capabilities.get(
            "fuzzywuzzy_available", False
        ):
            return 0.0, []
        try:
            from fuzzywuzzy import fuzz

            input_lower = input_text.lower()
            matched_keywords = []
            total_score = 0.0
            for keyword in keywords:
                best_ratio = max(
                    fuzz.partial_ratio(keyword, input_lower),
                    fuzz.token_sort_ratio(keyword, input_lower),
                )
                if best_ratio >= threshold:
                    matched_keywords.append(keyword)
                    total_score += best_ratio / 100.0
            return (total_score / len(keywords) if keywords else 0.0), matched_keywords
        except Exception as e:
            self.logger.debug(f"Fuzzy matching error: {e}")
            return 0.0, []

    def spacy_enhanced_keywords(self, node_info: Dict[str, Any]) -> List[str]:
        if not self._nlp_capabilities or not self._nlp_capabilities.get(
            "spacy_available", False
        ):
            return []
        try:
            import spacy

            nlp = spacy.load("en_core_web_sm")
            text_fields = [
                node_info.get("description", ""),
                node_info.get("prompt", ""),
                node_info.get("intent", ""),
            ]
            context = node_info.get("context", {})
            if isinstance(context, dict):
                text_fields.extend(
                    [
                        context.get("description", ""),
                        context.get("intent", ""),
                        context.get("purpose", ""),
                    ]
                )
            combined_text = " ".join(field for field in text_fields if field)
            if not combined_text:
                return []
            doc = nlp(combined_text)
            enhanced_keywords = [
                token.lemma_.lower()
                for token in doc
                if not token.is_stop
                and not token.is_punct
                and not token.is_space
                and len(token.text) > 2
                and token.pos_ in ["NOUN", "VERB", "ADJ"]
            ]
            enhanced_keywords.extend(
                [
                    ent.text.lower()
                    for ent in doc.ents
                    if ent.label_ in ["ORG", "PRODUCT", "EVENT", "WORK_OF_ART"]
                ]
            )
            return list(set(enhanced_keywords))
        except Exception as e:
            self.logger.debug(f"spaCy processing error: {e}")
            return []

    def algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        input_lower = input_text.lower()
        for node_name in available_nodes:
            if node_name.lower() in input_lower:
                return node_name, 1.0
        best_match, best_score = self.basic_keyword_match(input_text, available_nodes)
        if best_score > 0.3:
            return best_match, best_score
        if self._nlp_capabilities and self._nlp_capabilities.get(
            "fuzzywuzzy_available", False
        ):
            fuzzy_match, fuzzy_score = self.fuzzy_algorithm_match(
                input_text, available_nodes
            )
            if fuzzy_score > 0.2:
                return fuzzy_match, fuzzy_score + 0.1
        if self._nlp_capabilities and self._nlp_capabilities.get(
            "spacy_available", False
        ):
            spacy_match, spacy_score = self.spacy_algorithm_match(
                input_text, available_nodes
            )
            if spacy_score > 0.15:
                return spacy_match, spacy_score + 0.2
        return best_match or next(iter(available_nodes)), best_score

    def basic_keyword_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        input_lower = input_text.lower()
        best_match = None
        best_score = 0.0
        for node_name, node_info in available_nodes.items():
            if not isinstance(node_info, dict):
                continue
            keywords = self.parse_node_keywords(node_info)
            if keywords:
                matches = sum(1 for kw in keywords if kw in input_lower)
                score = matches / len(keywords) if keywords else 0.0
                combined_text = " ".join(
                    [
                        node_info.get("description", ""),
                        node_info.get("prompt", ""),
                        node_info.get("intent", ""),
                    ]
                ).lower()
                input_words = input_lower.split()
                if len(input_words) > 1:
                    for i in range(len(input_words) - 1):
                        if " ".join(input_words[i : i + 2]) in combined_text:
                            score += 0.3
                if score > best_score:
                    best_score = score
                    best_match = node_name
        return best_match or next(iter(available_nodes)), best_score

    def fuzzy_algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        best_match = None
        best_score = 0.0
        for node_name, node_info in available_nodes.items():
            if not isinstance(node_info, dict):
                continue
            keywords = self.parse_node_keywords(node_info)
            if keywords:
                fuzzy_score, _ = self.fuzzy_keyword_match(
                    input_text, keywords, threshold=70
                )
                if fuzzy_score > best_score:
                    best_score = fuzzy_score
                    best_match = node_name
        return best_match or next(iter(available_nodes)), best_score

    def spacy_algorithm_match(
        self, input_text: str, available_nodes: Dict[str, Dict[str, Any]]
    ) -> Tuple[str, float]:
        try:
            import spacy

            nlp = spacy.load("en_core_web_sm")
            input_doc = nlp(input_text.lower())
            input_keywords = [
                token.lemma_.lower()
                for token in input_doc
                if not token.is_stop and not token.is_punct and len(token.text) > 2
            ]
            if not input_keywords:
                return next(iter(available_nodes)), 0.0
            best_match = None
            best_score = 0.0
            for node_name, node_info in available_nodes.items():
                if not isinstance(node_info, dict):
                    continue
                enhanced_keywords = self.spacy_enhanced_keywords(node_info)
                if enhanced_keywords:
                    matches = sum(1 for kw in enhanced_keywords if kw in input_keywords)
                    score = matches / len(enhanced_keywords)
                    lemma_matches = sum(
                        1
                        for input_kw in input_keywords
                        for node_kw in enhanced_keywords
                        if input_kw == node_kw
                    )
                    lemma_score = lemma_matches / len(enhanced_keywords)
                    score = max(score, lemma_score * 0.8)
                    if score > best_score:
                        best_score = score
                        best_match = node_name
            return best_match or next(iter(available_nodes)), best_score
        except Exception as e:
            self.logger.debug(f"spaCy algorithm match error: {e}")
            return next(iter(available_nodes)), 0.0
