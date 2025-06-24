import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from agentmap.models.validation.validation_models import ValidationResult


class ValidationCacheService:
    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 24):
        # Create a simple logger fallback if logging service isn't available
        import logging

        self.logger = logging.getLogger("agentmap.validation_cache")

        self.cache_dir = cache_dir or Path.home() / ".agentmap" / "validation_cache"
        self.max_age = timedelta(hours=max_age_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_result_by_path(self, file_path: Path) -> Optional[ValidationResult]:
        """Get cached result by file path (calculates hash automatically)."""
        file_hash = self._calculate_file_hash(file_path)
        return self._read_cache(file_path, file_hash)

    def clear_cache(self, file_path: Optional[Path] = None) -> int:
        return self._clear_cache_files(file_path)

    def cleanup_expired(self) -> int:
        return self._remove_expired_files()

    def get_cache_stats(self) -> Dict[str, int]:
        return self._gather_stats()

    # ========================================================================
    # CLI-compatible method aliases
    # ========================================================================

    def clear_validation_cache(self, file_path: Optional[str] = None) -> int:
        """CLI-compatible alias for clear_cache."""
        file_path_obj = Path(file_path) if file_path else None
        return self.clear_cache(file_path_obj)

    def cleanup_validation_cache(self) -> int:
        """CLI-compatible alias for cleanup_expired."""
        return self.cleanup_expired()

    def get_validation_cache_stats(self) -> Dict[str, int]:
        """CLI-compatible alias for get_cache_stats."""
        return self.get_cache_stats()

    def calculate_file_hash(self, file_path: Path) -> str:
        """Public method for calculating file hash."""
        return self._calculate_file_hash(file_path)

    def get_cached_result(
        self, file_path: str, file_hash: str
    ) -> Optional["ValidationResult"]:
        """Get cached result by file path and hash."""
        return self._read_cache(Path(file_path), file_hash)

    def cache_result(self, result: "ValidationResult") -> None:
        """Cache a validation result."""
        if not result.file_hash:
            self.logger.warning("ValidationResult missing file_hash. Skipping cache.")
            return
        self._write_cache(result)

    def _calculate_file_hash(self, file_path: Path) -> str:
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def _get_cache_key(self, file_path: Path, file_hash: str) -> str:
        return f"{file_path.name}_{file_hash}"

    def _get_cache_file_path(self, file_path: Path, file_hash: str) -> Path:
        return self.cache_dir / f"{self._get_cache_key(file_path, file_hash)}.json"

    def _read_cache(
        self, file_path: Path, file_hash: str
    ) -> Optional[ValidationResult]:
        """Read cached validation result from file."""
        cache_file = self._get_cache_file_path(file_path, file_hash)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache_data = json.load(f)

            # Validate cache data structure
            if (
                not isinstance(cache_data, dict)
                or "cached_at" not in cache_data
                or "result" not in cache_data
            ):
                self.logger.warning(f"Invalid cache file structure: {cache_file}")
                cache_file.unlink(missing_ok=True)
                return None

            cached_time = datetime.fromisoformat(cache_data["cached_at"])
            if datetime.now() - cached_time > self.max_age:
                self.logger.debug(f"Cache file expired: {cache_file}")
                cache_file.unlink(missing_ok=True)
                return None

            return ValidationResult.model_validate(cache_data["result"])

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            self.logger.warning(f"Corrupted cache file {cache_file}: {e}")
            # Remove corrupted cache file
            try:
                cache_file.unlink(missing_ok=True)
            except Exception:
                pass  # Ignore cleanup errors
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error reading cache file {cache_file}: {e}")
            return None

    def _write_cache(self, result: ValidationResult) -> None:
        """Write validation result to cache file with proper JSON serialization."""
        cache_file = self._get_cache_file_path(Path(result.file_path), result.file_hash)

        # Try different serialization methods for compatibility
        result_data = None

        # Method 1: Try model_dump with mode='json' (Pydantic v2)
        try:
            result_data = result.model_dump(mode="json")
            self.logger.debug("Using model_dump(mode='json') serialization")
        except (TypeError, AttributeError):
            # Method 2: Try model_dump_json then parse (Pydantic v2)
            try:
                json_str = result.model_dump_json()
                result_data = json.loads(json_str)
                self.logger.debug("Using model_dump_json() serialization")
            except (TypeError, AttributeError):
                # Method 3: Fallback to regular model_dump and manual datetime conversion
                try:
                    result_data = result.model_dump()
                    # Manually convert datetime objects to strings
                    result_data = self._convert_datetime_to_string(result_data)
                    self.logger.debug(
                        "Using model_dump() with manual datetime conversion"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to serialize ValidationResult: {e}")
                    return

        if result_data is None:
            self.logger.error("Could not serialize ValidationResult with any method")
            return

        cache_data = {"cached_at": datetime.now().isoformat(), "result": result_data}

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False, default=str)
            self.logger.debug(f"Successfully wrote cache file: {cache_file}")
        except Exception as e:
            self.logger.error(f"Failed to write cache file {cache_file}: {e}")
            # Clean up partial file if it exists
            try:
                if cache_file.exists():
                    cache_file.unlink()
            except Exception:
                pass

    def _convert_datetime_to_string(self, data):
        """Recursively convert datetime objects to ISO format strings."""
        if isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, dict):
            return {
                key: self._convert_datetime_to_string(value)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._convert_datetime_to_string(item) for item in data]
        else:
            return data

    def _clear_cache_files(self, file_path: Optional[Path] = None) -> int:
        removed_count = 0

        if file_path:
            pattern = f"{file_path.name}_*.json"
            files = self.cache_dir.glob(pattern)
        else:
            files = self.cache_dir.glob("*.json")

        for file in files:
            file.unlink(missing_ok=True)
            removed_count += 1

        return removed_count

    def _remove_expired_files(self) -> int:
        removed_count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
                cached_time = datetime.fromisoformat(cache_data["cached_at"])
                if datetime.now() - cached_time > self.max_age:
                    cache_file.unlink()
                    removed_count += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                cache_file.unlink(missing_ok=True)
                removed_count += 1
        return removed_count

    def _gather_stats(self) -> Dict[str, int]:
        stats = dict(total_files=0, valid_files=0, expired_files=0, corrupted_files=0)
        for cache_file in self.cache_dir.glob("*.json"):
            stats["total_files"] += 1
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
                cached_time = datetime.fromisoformat(cache_data["cached_at"])
                if datetime.now() - cached_time > self.max_age:
                    stats["expired_files"] += 1
                else:
                    stats["valid_files"] += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                stats["corrupted_files"] += 1
        return stats
