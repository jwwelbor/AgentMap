"""
Unit tests for the shared _batch_ids helper (spec §1.9, TC-007).

Tests cover:
- _sanitize_spec_id with CUSTOM_ID_RE (Anthropic/OpenAI constraint)
- _sanitize_spec_id with GEMINI_KEY_RE (Gemini constraint)
- build_spec_id_map: happy path, collision detection, already-safe ids
"""

import re

import pytest

from agentmap.exceptions import LLMServiceError
from agentmap.models.llm_execution import LLMCallSpec
from agentmap.services.llm._batch_ids import (
    CUSTOM_ID_RE,
    GEMINI_KEY_RE,
    _sanitize_spec_id,
    build_spec_id_map,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spec(spec_id: str) -> LLMCallSpec:
    return LLMCallSpec(spec_id=spec_id, messages=[{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# AC-T1: _sanitize_spec_id
# ---------------------------------------------------------------------------


class TestSanitizeSpecId:
    """AC-T1: accepts raw spec_id + regex constraint; returns sanitized id."""

    def test_already_safe_id_returned_unchanged(self):
        """TC-007 edge: spec_id already safe → returned unchanged."""
        result = _sanitize_spec_id("my_safe_id", CUSTOM_ID_RE)
        assert result == "my_safe_id"

    def test_safe_id_with_hyphens_returned_unchanged(self):
        result = _sanitize_spec_id("safe-id-123", CUSTOM_ID_RE)
        assert result == "safe-id-123"

    def test_unsafe_id_returns_deterministic_hash(self):
        """TC-007: spec_id with special chars → deterministic safe string."""
        result = _sanitize_spec_id("my/spec/with:special!chars", CUSTOM_ID_RE)
        # Must match regex
        assert CUSTOM_ID_RE.match(
            result
        ), f"Result {result!r} does not match CUSTOM_ID_RE"

    def test_unsafe_id_is_deterministic(self):
        """Same input always produces same output."""
        result1 = _sanitize_spec_id("my/spec/with:special!chars", CUSTOM_ID_RE)
        result2 = _sanitize_spec_id("my/spec/with:special!chars", CUSTOM_ID_RE)
        assert result1 == result2

    def test_different_inputs_produce_different_hashes(self):
        """TC-007: 'my/spec/with:special!chars' does not collide with 'my_spec_with_special_chars'."""
        r1 = _sanitize_spec_id("my/spec/with:special!chars", CUSTOM_ID_RE)
        r2 = _sanitize_spec_id("my_spec_with_special_chars", CUSTOM_ID_RE)
        # r2 is already safe so returned unchanged; they must differ
        assert r1 != r2

    def test_spec_id_over_64_chars_is_truncated(self):
        """TC-007 edge: spec_id > 64 chars → truncated to 64."""
        long_id = "a" * 100
        result = _sanitize_spec_id(long_id, CUSTOM_ID_RE)
        assert len(result) <= 64
        assert CUSTOM_ID_RE.match(result)

    def test_gemini_regex_constraint_applied(self):
        """AC-T1: regex parameter accepted; Gemini key regex allows up to 128 chars."""
        # A 128-char alphanumeric id should pass Gemini regex but may fail CUSTOM_ID_RE (>64)
        long_safe = "a" * 128
        result = _sanitize_spec_id(long_safe, GEMINI_KEY_RE)
        assert result == long_safe

    def test_gemini_regex_unsafe_id_truncated_to_128(self):
        """Gemini max is 128; unsafe id should hash to <= 128 chars."""
        unsafe_id = "my/spec/with:special!chars"
        result = _sanitize_spec_id(unsafe_id, GEMINI_KEY_RE)
        assert len(result) <= 128
        assert GEMINI_KEY_RE.match(result)

    def test_default_regex_is_custom_id_re(self):
        """_sanitize_spec_id without regex arg uses CUSTOM_ID_RE."""
        unsafe = "has spaces here"
        result = _sanitize_spec_id(unsafe)
        assert CUSTOM_ID_RE.match(result)


# ---------------------------------------------------------------------------
# AC-T2: build_spec_id_map — collision detection
# ---------------------------------------------------------------------------


class TestBuildSpecIdMap:
    """AC-T2 / AC-T1: build_spec_id_map sanitization and collision detection."""

    def test_happy_path_all_safe_ids(self):
        """All safe spec_ids returned in 1-to-1 map."""
        specs = [_make_spec("spec1"), _make_spec("spec2")]
        result = build_spec_id_map(specs, CUSTOM_ID_RE)
        assert result == {"spec1": "spec1", "spec2": "spec2"}

    def test_unsafe_ids_sanitized_in_map(self):
        """Unsafe spec_ids are sanitized; map keys are original spec_ids."""
        spec = _make_spec("my/spec/with:special!chars")
        result = build_spec_id_map([spec], CUSTOM_ID_RE)
        assert "my/spec/with:special!chars" in result
        assert CUSTOM_ID_RE.match(result["my/spec/with:special!chars"])

    def test_collision_raises_llm_service_error(self):
        """AC-T2: two spec_ids that sanitize to the same provider_id raise LLMServiceError.

        Use a tiny regex (max length 1) so that different unsafe inputs truncate to the
        same single hex character, forcing a deterministic collision without needing a
        real SHA-1 collision.
        """
        import hashlib

        tiny_re = re.compile(r"^[a-zA-Z0-9_-]{1,1}$")
        # Brute-force: find two *different* unsafe strings whose sha1 hexdigest[0] matches.
        found = []
        i = 0
        while len(found) < 2:
            s = f"unsafe/{i}"
            h = hashlib.sha1(s.encode()).hexdigest()[0]
            if not found or h == hashlib.sha1(found[0].encode()).hexdigest()[0]:
                found.append(s)
                if len(found) == 2 and found[0] == found[1]:
                    found.pop()  # skip duplicates
            i += 1

        specs = [_make_spec(found[0]), _make_spec(found[1])]
        with pytest.raises(LLMServiceError, match="collision"):
            build_spec_id_map(specs, tiny_re)

    def test_no_collision_distinct_hashes(self):
        """Two different unsafe ids that do NOT collide produce two distinct entries."""
        spec_a = _make_spec("path/a")
        spec_b = _make_spec("path/b")
        result = build_spec_id_map([spec_a, spec_b], CUSTOM_ID_RE)
        assert len(result) == 2
        assert result["path/a"] != result["path/b"]

    def test_empty_specs_returns_empty_map(self):
        result = build_spec_id_map([], CUSTOM_ID_RE)
        assert result == {}

    def test_gemini_regex_accepted(self):
        """build_spec_id_map accepts Gemini regex."""
        specs = [_make_spec("my/gemini/spec")]
        result = build_spec_id_map(specs, GEMINI_KEY_RE)
        assert "my/gemini/spec" in result
        assert GEMINI_KEY_RE.match(result["my/gemini/spec"])
