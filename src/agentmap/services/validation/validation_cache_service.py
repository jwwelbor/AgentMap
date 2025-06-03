# src/agentmap/services/validation/validation_cache_service.py
import hashlib
from pathlib import Path
from agentmap.models.validation.cache import ValidationCache


class ValidationCacheService:
    def __init__(self):
        self.cache = ValidationCache()

    def get_cached_result(self, file_path: str, file_hash: str):
        return self.cache.get_cached_result(file_path, file_hash)

    def cache_result(self, result):
        self.cache.cache_result(result)

    def clear_cache(self, file_path: str = None) -> int:
        return self.cache.clear_cache(file_path)

    def cleanup_expired(self) -> int:
        return self.cache.cleanup_expired()

    def get_cache_stats(self) -> dict:
        return self.cache.get_cache_stats()

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()