# src/agentmap/validation/cache.py
"""
Caching system for validation results to avoid re-validation of unchanged files.
"""
import json
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

from agentmap.validation.errors import ValidationResult


class ValidationCache:
    """
    Simple file-based cache for validation results.
    
    Caches validation results by file hash to avoid re-validating unchanged files.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None, max_age_hours: int = 24):
        """
        Initialize the validation cache.
        
        Args:
            cache_dir: Directory to store cache files (default: .agentmap/validation_cache)
            max_age_hours: Maximum age of cached results in hours
        """
        self.cache_dir = cache_dir or Path.home() / '.agentmap' / 'validation_cache'
        self.max_age = timedelta(hours=max_age_hours)
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_key(self, file_path: str, file_hash: str) -> str:
        """Generate a cache key for a file."""
        # Use file name and hash to create a unique key
        file_name = Path(file_path).name
        return f"{file_name}_{file_hash}"
    
    def get_cached_result(self, file_path: str, file_hash: str) -> Optional[ValidationResult]:
        """
        Get cached validation result if available and not expired.
        
        Args:
            file_path: Path to the file being validated
            file_hash: Hash of the file content
            
        Returns:
            Cached ValidationResult if available and valid, None otherwise
        """
        cache_key = self.get_cache_key(file_path, file_hash)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            # Load cached result
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is expired
            cached_time = datetime.fromisoformat(cache_data['cached_at'])
            if datetime.now() - cached_time > self.max_age:
                # Remove expired cache
                cache_file.unlink(missing_ok=True)
                return None
            
            # Reconstruct ValidationResult from cached data
            return ValidationResult.model_validate(cache_data['result'])
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Remove corrupted cache file
            cache_file.unlink(missing_ok=True)
            return None
    
    def cache_result(self, result: ValidationResult) -> None:
        """
        Cache a validation result.
        
        Args:
            result: ValidationResult to cache
        """
        if not result.file_hash:
            # Can't cache without a file hash
            return
        
        cache_key = self.get_cache_key(result.file_path, result.file_hash)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        try:
            # Prepare cache data
            cache_data = {
                'cached_at': datetime.now().isoformat(),
                'result': result.model_dump()
            }
            
            # Write to cache file
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception:
            # Silently fail if we can't cache - not critical
            pass
    
    def clear_cache(self, file_path: Optional[str] = None) -> int:
        """
        Clear cached validation results.
        
        Args:
            file_path: If provided, only clear cache for this file. Otherwise clear all.
            
        Returns:
            Number of cache files removed
        """
        removed_count = 0
        
        if file_path:
            # Clear cache for specific file (all hashes)
            file_name = Path(file_path).name
            pattern = f"{file_name}_*.json"
            
            for cache_file in self.cache_dir.glob(pattern):
                cache_file.unlink(missing_ok=True)
                removed_count += 1
        else:
            # Clear all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                cache_file.unlink(missing_ok=True)
                removed_count += 1
        
        return removed_count
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of expired cache files removed
        """
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
                # Remove corrupted cache files
                cache_file.unlink(missing_ok=True)
                removed_count += 1
        
        return removed_count
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        cache_files = list(self.cache_dir.glob("*.json"))
        total_files = len(cache_files)
        
        valid_files = 0
        expired_files = 0
        corrupted_files = 0
        
        for cache_file in cache_files:
            try:
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                cached_time = datetime.fromisoformat(cache_data['cached_at'])
                if datetime.now() - cached_time > self.max_age:
                    expired_files += 1
                else:
                    valid_files += 1
                    
            except (json.JSONDecodeError, KeyError, ValueError):
                corrupted_files += 1
        
        return {
            'total_files': total_files,
            'valid_files': valid_files,
            'expired_files': expired_files,
            'corrupted_files': corrupted_files
        }
