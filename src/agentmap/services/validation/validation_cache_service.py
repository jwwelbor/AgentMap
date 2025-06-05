import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

from agentmap.services.logging_service import LoggingService
from agentmap.models.validation.validation_models import ValidationResult

class ValidationCacheService:
    def __init__(
        self,
        logging_service: LoggingService,
        cache_dir: Optional[Path] = None,
        max_age_hours: int = 24
    ):
        self.logger = logging_service.get_class_logger(self)
        self.cache_dir = cache_dir or Path.home() / '.agentmap' / 'validation_cache'
        self.max_age = timedelta(hours=max_age_hours)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_cached_result(self, file_path: Path) -> Optional[ValidationResult]:
        file_hash = self._calculate_file_hash(file_path)
        return self._read_cache(file_path, file_hash)

    def cache_result(self, result: ValidationResult) -> None:
        if not result.file_hash:
            self.logger.warning("ValidationResult missing file_hash. Skipping cache.")
            return
        self._write_cache(result)

    def clear_cache(self, file_path: Optional[Path] = None) -> int:
        return self._clear_cache_files(file_path)

    def cleanup_expired(self) -> int:
        return self._remove_expired_files()

    def get_cache_stats(self) -> Dict[str, int]:
        return self._gather_stats()

    def _calculate_file_hash(self, file_path: Path) -> str:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def _get_cache_key(self, file_path: Path, file_hash: str) -> str:
        return f"{file_path.name}_{file_hash}"

    def _get_cache_file_path(self, file_path: Path, file_hash: str) -> Path:
        return self.cache_dir / f"{self._get_cache_key(file_path, file_hash)}.json"

    def _read_cache(self, file_path: Path, file_hash: str) -> Optional[ValidationResult]:
        cache_file = self._get_cache_file_path(file_path, file_hash)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            cached_time = datetime.fromisoformat(cache_data['cached_at'])
            if datetime.now() - cached_time > self.max_age:
                cache_file.unlink(missing_ok=True)
                return None

            return ValidationResult.model_validate(cache_data['result'])

        except (json.JSONDecodeError, KeyError, ValueError):
            cache_file.unlink(missing_ok=True)
            return None

    def _write_cache(self, result: ValidationResult) -> None:
        cache_file = self._get_cache_file_path(Path(result.file_path), result.file_hash)
        cache_data = {
            'cached_at': datetime.now().isoformat(),
            'result': result.model_dump()
        }
        try:
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to write cache file: {e}")

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
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                cached_time = datetime.fromisoformat(cache_data['cached_at'])
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
            stats['total_files'] += 1
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                cached_time = datetime.fromisoformat(cache_data['cached_at'])
                if datetime.now() - cached_time > self.max_age:
                    stats['expired_files'] += 1
                else:
                    stats['valid_files'] += 1
            except (json.JSONDecodeError, KeyError, ValueError):
                stats['corrupted_files'] += 1
        return stats
