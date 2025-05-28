# src/agentmap/validation/__init__.py
"""
AgentMap validation system for CSV and configuration files.

This module provides validation for:
- CSV workflow definitions
- YAML configuration files
- Integration with compilation and runtime systems
"""
from pathlib import Path
from typing import Optional, Tuple

from agentmap.validation.errors import ValidationResult, ValidationException
from agentmap.validation.csv_validator import CSVValidator
from agentmap.validation.config_validator import ConfigValidator
from agentmap.validation.cache import ValidationCache

# Global cache instance
_validation_cache = ValidationCache()


def validate_csv(csv_path: Path, use_cache: bool = True) -> ValidationResult:
    """
    Validate a CSV workflow definition file.
    
    Args:
        csv_path: Path to the CSV file to validate
        use_cache: Whether to use cached results if available
        
    Returns:
        ValidationResult with validation results
    """
    csv_path = Path(csv_path)
    
    # Check cache first if enabled
    if use_cache:
        # Calculate file hash for cache lookup
        try:
            import hashlib
            with open(csv_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            cached_result = _validation_cache.get_cached_result(str(csv_path), file_hash)
            if cached_result:
                return cached_result
        except Exception:
            # If we can't calculate hash or access cache, continue with validation
            pass
    
    # Perform validation
    validator = CSVValidator()
    result = validator.validate_file(csv_path)
    
    # Cache the result if enabled
    if use_cache and result.file_hash:
        _validation_cache.cache_result(result)
    
    return result


def validate_config(config_path: Path, use_cache: bool = True) -> ValidationResult:
    """
    Validate a YAML configuration file.
    
    Args:
        config_path: Path to the config file to validate
        use_cache: Whether to use cached results if available
        
    Returns:
        ValidationResult with validation results
    """
    config_path = Path(config_path)
    
    # Check cache first if enabled
    if use_cache:
        # Calculate file hash for cache lookup
        try:
            import hashlib
            with open(config_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
            
            cached_result = _validation_cache.get_cached_result(str(config_path), file_hash)
            if cached_result:
                return cached_result
        except Exception:
            # If we can't calculate hash or access cache, continue with validation
            pass
    
    # Perform validation
    validator = ConfigValidator()
    result = validator.validate_file(config_path)
    
    # Cache the result if enabled
    if use_cache and result.file_hash:
        _validation_cache.cache_result(result)
    
    return result


def validate_both(csv_path: Path, config_path: Optional[Path] = None, use_cache: bool = True) -> Tuple[ValidationResult, Optional[ValidationResult]]:
    """
    Validate both CSV and config files.
    
    Args:
        csv_path: Path to the CSV file to validate
        config_path: Optional path to the config file to validate
        use_cache: Whether to use cached results if available
        
    Returns:
        Tuple of (csv_result, config_result). config_result is None if no config_path provided.
    """
    csv_result = validate_csv(csv_path, use_cache)
    
    config_result = None
    if config_path:
        config_result = validate_config(config_path, use_cache)
    
    return csv_result, config_result


def validate_and_raise(csv_path: Path, config_path: Optional[Path] = None, use_cache: bool = True) -> None:
    """
    Validate files and raise ValidationException if there are errors.
    
    Args:
        csv_path: Path to the CSV file to validate
        config_path: Optional path to the config file to validate
        use_cache: Whether to use cached results if available
        
    Raises:
        ValidationException: If validation fails with errors
    """
    csv_result, config_result = validate_both(csv_path, config_path, use_cache)
    
    # Check for errors in either result
    if csv_result.has_errors:
        raise ValidationException(csv_result)
    
    if config_result and config_result.has_errors:
        raise ValidationException(config_result)


def print_validation_summary(csv_result: Optional[ValidationResult] = None, config_result: Optional[ValidationResult] = None) -> None:
    """
    Print a summary of validation results.
    
    Args:
        csv_result: Optional CSV validation result
        config_result: Optional config validation result
    """
    if not csv_result and not config_result:
        print("No validation results to display")
        return
    
    print("\n" + "="*60)
    print("AgentMap Validation Summary")
    print("="*60)
    
    # CSV results
    if csv_result:
        print(f"\n📄 {csv_result.get_summary()}")
        if csv_result.has_errors or csv_result.has_warnings:
            csv_result.print_detailed_report()
    
    # Config results
    if config_result:
        print(f"\n⚙️  {config_result.get_summary()}")
        if config_result.has_errors or config_result.has_warnings:
            config_result.print_detailed_report()
    
    # Overall summary
    total_errors = 0
    has_errors = False
    
    if csv_result:
        total_errors += csv_result.total_issues
        has_errors = has_errors or csv_result.has_errors
    
    if config_result:
        total_errors += config_result.total_issues
        has_errors = has_errors or config_result.has_errors
    
    print(f"\n{'='*60}")
    if has_errors:
        print("❌ VALIDATION FAILED - Fix errors before proceeding")
    elif total_errors > 0:
        print("⚠️  VALIDATION PASSED WITH WARNINGS - Review warnings")
    else:
        print("✅ VALIDATION PASSED - No issues found")
    print("="*60)


def clear_validation_cache(file_path: Optional[str] = None) -> int:
    """
    Clear validation cache.
    
    Args:
        file_path: If provided, only clear cache for this file. Otherwise clear all.
        
    Returns:
        Number of cache files removed
    """
    return _validation_cache.clear_cache(file_path)


def get_validation_cache_stats() -> dict:
    """
    Get validation cache statistics.
    
    Returns:
        Dictionary with cache statistics
    """
    return _validation_cache.get_cache_stats()


def cleanup_validation_cache() -> int:
    """
    Remove expired validation cache entries.
    
    Returns:
        Number of expired cache files removed
    """
    return _validation_cache.cleanup_expired()


# Integration helper functions for use by other AgentMap components

def validate_csv_for_compilation(csv_path: Path) -> None:
    """
    Validate CSV file before compilation and raise if errors found.
    
    This function is intended for use by the compiler to ensure
    CSV files are valid before attempting compilation.
    
    Args:
        csv_path: Path to CSV file to validate
        
    Raises:
        ValidationException: If CSV validation fails with errors
    """
    result = validate_csv(csv_path)
    
    if result.has_errors:
        print(f"\n❌ CSV validation failed for {csv_path}")
        result.print_detailed_report()
        raise ValidationException(result)
    
    if result.has_warnings:
        print(f"\n⚠️  CSV validation warnings for {csv_path}")
        for warning in result.warnings:
            print(f"  • {warning}")
        print("")


def validate_config_for_loading(config_path: Path) -> None:
    """
    Validate config file and warn about issues.
    
    This function is intended for use when loading configuration
    to warn about potential issues without failing.
    
    Args:
        config_path: Path to config file to validate
    """
    result = validate_config(config_path)
    
    if result.has_errors:
        print(f"\n❌ Configuration validation errors in {config_path}")
        for error in result.errors:
            print(f"  • {error}")
        print("⚠️  Some features may not work correctly with invalid configuration")
    
    if result.has_warnings:
        print(f"\nℹ️  Configuration validation warnings for {config_path}")
        for warning in result.warnings:
            print(f"  • {warning}")


# Export main classes and functions
__all__ = [
    'ValidationResult',
    'ValidationException', 
    'CSVValidator',
    'ConfigValidator',
    'validate_csv',
    'validate_config',
    'validate_both',
    'validate_and_raise',
    'print_validation_summary',
    'clear_validation_cache',
    'get_validation_cache_stats',
    'cleanup_validation_cache',
    'validate_csv_for_compilation',
    'validate_config_for_loading'
]