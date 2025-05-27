# src/agentmap/validation/errors.py
"""
Error and warning classes for AgentMap validation system.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class ValidationLevel(str, Enum):
    """Validation message severity levels."""
    ERROR = "error"
    WARNING = "warning" 
    INFO = "info"


class ValidationError(BaseModel):
    """Individual validation error or warning."""
    level: ValidationLevel
    message: str
    line_number: Optional[int] = None
    field: Optional[str] = None
    value: Optional[str] = None
    suggestion: Optional[str] = None
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [f"{self.level.upper()}: {self.message}"]
        
        if self.line_number is not None:
            parts.append(f"(Line {self.line_number})")
        
        if self.field:
            parts.append(f"Field: {self.field}")
            
        if self.value:
            parts.append(f"Value: '{self.value}'")
            
        if self.suggestion:
            parts.append(f"Suggestion: {self.suggestion}")
            
        return " | ".join(parts)


class ValidationResult(BaseModel):
    """Complete validation result for a file."""
    file_path: str
    file_type: str  # "csv" or "config"
    is_valid: bool
    errors: List[ValidationError] = Field(default_factory=list)
    warnings: List[ValidationError] = Field(default_factory=list) 
    info: List[ValidationError] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=datetime.now)
    file_hash: Optional[str] = None
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are any warning-level issues."""
        return len(self.warnings) > 0
    
    @property
    def total_issues(self) -> int:
        """Total number of issues found."""
        return len(self.errors) + len(self.warnings) + len(self.info)
    
    def add_error(self, message: str, **kwargs) -> None:
        """Add an error-level validation issue."""
        error = ValidationError(level=ValidationLevel.ERROR, message=message, **kwargs)
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, message: str, **kwargs) -> None:
        """Add a warning-level validation issue."""
        warning = ValidationError(level=ValidationLevel.WARNING, message=message, **kwargs)
        self.warnings.append(warning)
    
    def add_info(self, message: str, **kwargs) -> None:
        """Add an info-level validation issue."""
        info = ValidationError(level=ValidationLevel.INFO, message=message, **kwargs)
        self.info.append(info)
    
    def get_summary(self) -> str:
        """Get a summary of validation results."""
        if self.is_valid and not self.has_warnings and not self.info:
            return f"✅ {self.file_type.upper()} validation passed - no issues found"
        
        parts = []
        if self.has_errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.has_warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        if self.info:
            parts.append(f"{len(self.info)} info message(s)")
        
        if not parts:
            return f"✅ {self.file_type.upper()} validation passed - no issues found"
        
        status = "❌" if self.has_errors else "⚠️" 
        return f"{status} {self.file_type.upper()} validation: {', '.join(parts)}"
    
    def print_detailed_report(self) -> None:
        """Print a detailed validation report."""
        print(f"\n{self.get_summary()}")
        print(f"File: {self.file_path}")
        print(f"Validated at: {self.validated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if self.errors:
            print(f"\n🚨 ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if self.info:
            print(f"\nℹ️  INFO ({len(self.info)}):")
            for info_msg in self.info:
                print(f"  • {info_msg}")
        
        print()  # Add blank line at the end


class ValidationException(Exception):
    """Exception raised when validation fails with errors."""
    
    def __init__(self, result: ValidationResult):
        self.result = result
        error_count = len(result.errors)
        super().__init__(f"Validation failed with {error_count} error(s) in {result.file_path}")