"""
ImportFixerService for AgentMap.

Service that extends existing validation infrastructure to handle import fixing operations.
This service resolves 227 import issues by systematically fixing circular imports, missing 
typing imports, and missing standard library imports while maintaining code functionality.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from agentmap.models.validation.validation_models import ValidationResult, ValidationError, ValidationLevel
from agentmap.services.validation.validation_service import ValidationService
from agentmap.services.logging_service import LoggingService
from agentmap.services.config.app_config_service import AppConfigService


class ImportFixerService:
    """
    Service for fixing import issues in Python files.
    
    Extends existing validation infrastructure to provide systematic import fixing
    capabilities including circular imports, missing typing imports, and missing
    standard library imports.
    """
    
    # Comprehensive typing symbols mapping with detection patterns
    TYPING_SYMBOLS = {
        'Any', 'Union', 'Optional', 'Dict', 'List', 'Tuple', 'Set', 
        'Callable', 'Type', 'TypeVar', 'Generic', 'Protocol', 'Literal',
        'ClassVar', 'Final', 'Annotated', 'TYPE_CHECKING', 'ForwardRef',
        'Counter', 'DefaultDict', 'OrderedDict', 'ChainMap', 'Deque'
    }
    
    # Enhanced patterns for comprehensive type hint detection
    TYPE_HINT_PATTERNS = [
        r':\s*([A-Z][a-zA-Z_]*(?:\[[^\]]*\])?)',  # Variable annotations: x: Dict[str, Any]
        r'->\s*([A-Z][a-zA-Z_]*(?:\[[^\]]*\])?)',  # Return annotations: -> Optional[str]
        r'\[\s*([A-Z][a-zA-Z_]*(?:\[[^\]]*\])?)',  # Generic parameters: List[Dict[str, Any]]
        r'Union\[([^\]]+)\]',  # Union types: Union[str, int, None]
        r'Optional\[([^\]]+)\]',  # Optional types: Optional[Dict[str, Any]]
        r'Callable\[\[[^\]]*\],\s*([A-Z][a-zA-Z_]*)',  # Callable return types
        r'@([a-z_]+)\s*\n\s*def',  # Decorator patterns that might need typing
        r'cast\(([A-Z][a-zA-Z_]*)',  # Type casting: cast(Dict, value)
    ]
    
    # Comprehensive standard library import patterns
    STANDARD_IMPORT_PATTERNS = {
        r'\bPath\b(?!\s*=)': 'from pathlib import Path',
        r'@dataclass\b': 'from dataclasses import dataclass',
        r'\bfield\s*\(.*default_factory': 'from dataclasses import field',
        r'\bABC\b(?!\s*=)': 'from abc import ABC',
        r'@abstractmethod\b': 'from abc import abstractmethod',
        r'\bdefaultdict\b': 'from collections import defaultdict',
        r'\bOrderedDict\b': 'from collections import OrderedDict',
        r'\bCounter\b': 'from collections import Counter',
        r'\bdeque\b': 'from collections import deque',
        r'\bpartial\b': 'from functools import partial',
        r'\bwraps\b': 'from functools import wraps',
        r'\bcache\b': 'from functools import cache',
        r'\benum\b': 'from enum import Enum',
        r'\bEnum\b': 'from enum import Enum',
        r'\bdatetime\b': 'from datetime import datetime',
        r'\bdate\b': 'from datetime import date',
        r'\btime\b': 'from datetime import time',
    }
    
    # Circular import patterns for AgentMap architecture
    CIRCULAR_IMPORT_PATTERNS = {
        # Services importing from same package
        r'from agentmap\.services\.([\w.]+) import': r'from ..services.\1 import',
        r'from agentmap\.models\.([\w.]+) import': r'from ..models.\1 import', 
        r'from agentmap\.core\.([\w.]+) import': r'from ..core.\1 import',
        r'from agentmap\.agents\.([\w.]+) import': r'from ..agents.\1 import',
        r'from agentmap\.exceptions\.([\w.]+) import': r'from ..exceptions.\1 import',
        r'from agentmap\.infrastructure\.([\w.]+) import': r'from ..infrastructure.\1 import',
        r'from agentmap\.di\.([\w.]+) import': r'from ..di.\1 import',
        # Cross-layer imports that might cause issues
        r'from agentmap\.([\w.]+) import': r'from ..\1 import',
    }
    
    def __init__(
        self,
        validation_service: ValidationService,
        logging_service: LoggingService,
        app_config_service: AppConfigService
    ):
        """Initialize service with dependency injection."""
        self.validation = validation_service
        self.logger = logging_service.get_class_logger(self)
        self.config = app_config_service
        self.logger.info("[ImportFixerService] Initialized")
    
    def fix_file_imports(self, file_path: Path) -> ValidationResult:
        """
        Fix import issues in a single Python file.
        
        Args:
            file_path: Path to Python file to fix
            
        Returns:
            ValidationResult with details of fixes applied
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file cannot be written
        """
        file_path = Path(file_path)
        self.logger.info(f"[ImportFixerService] Fixing imports in: {file_path}")
        
        # Create validation result
        result = ValidationResult(
            file_path=str(file_path),
            file_type="import",
            is_valid=True,
            validated_at=datetime.now()
        )
        
        if not file_path.exists():
            result.add_error("File not found", suggestion="Check file path")
            self.logger.error(f"[ImportFixerService] File not found: {file_path}")
            return result
        
        if not file_path.suffix == '.py':
            result.add_warning("Not a Python file", suggestion="Only .py files are processed")
            self.logger.warning(f"[ImportFixerService] Not a Python file: {file_path}")
            return result
        
        try:
            # Read original content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Create backup before making changes
            backup_path = self._create_backup(file_path)
            result.add_info(f"Created backup at: {backup_path}")
            
            # Apply fixes in order
            fixes_applied = 0
            fixes_applied += self._fix_circular_imports(file_path, result)
            fixes_applied += self._add_missing_typing_imports(file_path, result)
            fixes_applied += self._add_missing_standard_imports(file_path, result)
            
            if fixes_applied > 0:
                result.add_info(f"Applied {fixes_applied} import fixes")
                self.logger.info(f"[ImportFixerService] Applied {fixes_applied} fixes to {file_path}")
            else:
                result.add_info("No import issues found")
                self.logger.debug(f"[ImportFixerService] No fixes needed for {file_path}")
            
            return result
            
        except Exception as e:
            result.add_error(f"Failed to fix imports: {str(e)}")
            self.logger.error(f"[ImportFixerService] Error fixing {file_path}: {e}")
            return result
    
    def _fix_circular_imports(self, file_path: Path, result: ValidationResult) -> int:
        """
        Fix circular import issues by converting absolute to relative imports.
        
        Uses comprehensive pattern matching and proper relative path calculation
        based on file location within the AgentMap architecture.
        
        Args:
            file_path: Path to file being fixed
            result: ValidationResult to record fixes
            
        Returns:
            Number of fixes applied
        """
        fixes_applied = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Calculate proper relative import patterns based on file location
            relative_patterns = self._calculate_relative_import_patterns(file_path)
            
            if not relative_patterns:
                self.logger.debug(f"[ImportFixerService] No relative patterns needed for {file_path}")
                return 0
            
            modified_lines = []
            for line_num, line in enumerate(lines, 1):
                original_line = line.strip()
                
                # Skip comments and empty lines
                if not original_line or original_line.startswith('#'):
                    modified_lines.append(line)
                    continue
                
                modified_line = line
                
                # Apply pattern-based transformations in priority order
                for pattern, replacement in relative_patterns.items():
                    if re.search(pattern, modified_line):
                        new_line = re.sub(pattern, replacement, modified_line)
                        if new_line != modified_line:
                            modified_line = new_line
                            fixes_applied += 1
                            
                            # Extract the imported module for better reporting
                            import_match = re.search(r'from ([^\s]+) import', new_line)
                            imported_module = import_match.group(1) if import_match else "unknown"
                            
                            result.add_info(
                                f"Fixed circular import on line {line_num}",
                                line_number=line_num,
                                field="import_statement",
                                value=original_line,
                                suggestion=f"Changed to relative import: {new_line.strip()}"
                            )
                            
                            self.logger.debug(
                                f"[ImportFixerService] Line {line_num}: "
                                f"'{original_line}' -> '{new_line.strip()}'"
                            )
                            
                            # Only apply first matching pattern per line
                            break
                
                modified_lines.append(modified_line)
            
            # Validate and write back modified content
            if fixes_applied > 0:
                # Basic validation: ensure no syntax errors introduced
                try:
                    compile('\n'.join(modified_lines), str(file_path), 'exec')
                except SyntaxError as e:
                    result.add_error(
                        f"Syntax error introduced by circular import fix: {e}",
                        line_number=e.lineno,
                        suggestion="Manual review required"
                    )
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(modified_lines))
                
                self.logger.info(
                    f"[ImportFixerService] Applied {fixes_applied} circular import fixes to {file_path}"
                )
            
        except Exception as e:
            result.add_error(f"Error fixing circular imports: {str(e)}")
            self.logger.error(f"[ImportFixerService] Error in _fix_circular_imports: {e}")
        
        return fixes_applied
    
    def _add_missing_typing_imports(self, file_path: Path, result: ValidationResult) -> int:
        """
        Add missing typing imports based on comprehensive usage analysis.
        
        Uses enhanced pattern matching to detect typing symbols in type hints,
        function signatures, variable annotations, and generic types.
        
        Args:
            file_path: Path to file being fixed
            result: ValidationResult to record fixes
            
        Returns:
            Number of fixes applied
        """
        fixes_applied = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Find typing symbols used in the file with enhanced detection
            used_symbols = self._extract_typing_symbols_comprehensive(content)
            
            if not used_symbols:
                self.logger.debug(f"[ImportFixerService] No typing symbols found in {file_path}")
                return 0
            
            # Find existing typing imports
            imported_symbols, typing_import_line = self._extract_existing_typing_imports(lines)
            
            # Find missing symbols
            missing_symbols = used_symbols - imported_symbols
            
            if missing_symbols:
                # Validate that these symbols are actually from typing module
                validated_missing = self._validate_typing_symbols(missing_symbols, content)
                
                if not validated_missing:
                    self.logger.debug(f"[ImportFixerService] No valid typing symbols missing in {file_path}")
                    return 0
                
                if typing_import_line is not None:
                    # Update existing import line
                    all_symbols = sorted(imported_symbols | validated_missing)
                    new_import = f"from typing import {', '.join(all_symbols)}"
                    lines[typing_import_line] = new_import
                    fixes_applied = 1
                    
                    result.add_info(
                        f"Updated typing imports on line {typing_import_line + 1}",
                        line_number=typing_import_line + 1,
                        field="typing_import",
                        value=f"Added: {', '.join(sorted(validated_missing))}",
                        suggestion=new_import
                    )
                else:
                    # Add new typing import line after other imports
                    insert_line = self._find_import_insertion_point(lines)
                    new_import = f"from typing import {', '.join(sorted(validated_missing))}"
                    lines.insert(insert_line, new_import)
                    fixes_applied = 1
                    
                    result.add_info(
                        f"Added typing import on line {insert_line + 1}",
                        line_number=insert_line + 1,
                        field="typing_import",
                        value=f"Symbols: {', '.join(sorted(validated_missing))}",
                        suggestion=new_import
                    )
                
                # Validate and write back modified content
                try:
                    compile('\n'.join(lines), str(file_path), 'exec')
                except SyntaxError as e:
                    result.add_error(
                        f"Syntax error introduced by typing import fix: {e}",
                        line_number=e.lineno,
                        suggestion="Manual review required"
                    )
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                
                self.logger.info(
                    f"[ImportFixerService] Added missing typing imports to {file_path}: "
                    f"{', '.join(sorted(validated_missing))}"
                )
        
        except Exception as e:
            result.add_error(f"Error adding typing imports: {str(e)}")
            self.logger.error(f"[ImportFixerService] Error in _add_missing_typing_imports: {e}")
        
        return fixes_applied
    
    def _add_missing_standard_imports(self, file_path: Path, result: ValidationResult) -> int:
        """
        Add missing standard library imports based on comprehensive usage patterns.
        
        Detects usage of standard library classes, functions, and decorators
        and adds appropriate import statements.
        
        Args:
            file_path: Path to file being fixed
            result: ValidationResult to record fixes
            
        Returns:
            Number of fixes applied
        """
        fixes_applied = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            imports_to_add = []
            patterns_found = []
            
            # Check for each standard library pattern with context validation
            for pattern, required_import in self.STANDARD_IMPORT_PATTERNS.items():
                matches = list(re.finditer(pattern, content, re.MULTILINE))
                
                if matches:
                    # Validate that this is actually usage, not just a string or comment
                    valid_usage = self._validate_standard_library_usage(pattern, content)
                    
                    if valid_usage:
                        # Check if import already exists
                        import_module = required_import.split(' import ')[0].split('from ')[1]
                        if not self._has_import_comprehensive(content, import_module, required_import):
                            imports_to_add.append(required_import)
                            patterns_found.append((pattern, len(matches)))
            
            if imports_to_add:
                # Remove duplicates while preserving order
                unique_imports = []
                seen = set()
                for imp in imports_to_add:
                    if imp not in seen:
                        unique_imports.append(imp)
                        seen.add(imp)
                
                # Add imports after existing import block
                insert_line = self._find_import_insertion_point(lines)
                
                for i, import_statement in enumerate(unique_imports):
                    lines.insert(insert_line + i, import_statement)
                    fixes_applied += 1
                    
                    # Find which pattern triggered this import
                    triggered_pattern = None
                    for pattern, count in patterns_found:
                        expected_import = self.STANDARD_IMPORT_PATTERNS.get(pattern)
                        if expected_import == import_statement:
                            triggered_pattern = f"{count} usage(s) found"
                            break
                    
                    result.add_info(
                        f"Added standard library import on line {insert_line + i + 1}",
                        line_number=insert_line + i + 1,
                        field="standard_import",
                        value=triggered_pattern or "usage detected",
                        suggestion=import_statement
                    )
                
                # Validate and write back modified content
                try:
                    compile('\n'.join(lines), str(file_path), 'exec')
                except SyntaxError as e:
                    result.add_error(
                        f"Syntax error introduced by standard import fix: {e}",
                        line_number=e.lineno,
                        suggestion="Manual review required"
                    )
                    return 0
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(lines))
                
                self.logger.info(
                    f"[ImportFixerService] Added {len(unique_imports)} standard imports to {file_path}: "
                    f"{', '.join(unique_imports)}"
                )
        
        except Exception as e:
            result.add_error(f"Error adding standard imports: {str(e)}")
            self.logger.error(f"[ImportFixerService] Error in _add_missing_standard_imports: {e}")
        
        return fixes_applied
    
    def _calculate_relative_import_patterns(self, file_path: Path) -> Dict[str, str]:
        """
        Calculate proper relative import patterns based on file location within AgentMap architecture.
        
        Args:
            file_path: Path to file being processed
            
        Returns:
            Dictionary mapping regex patterns to replacement strings
        """
        patterns = {}
        
        try:
            # Find the agentmap root directory
            current_path = file_path.parent
            agentmap_root = None
            
            # Walk up the directory tree to find agentmap
            while current_path.name and current_path != current_path.parent:
                if current_path.name == 'agentmap':
                    agentmap_root = current_path
                    break
                current_path = current_path.parent
            
            if not agentmap_root:
                self.logger.debug(f"[ImportFixerService] Could not find agentmap root for {file_path}")
                return {}
            
            # Calculate relative path and depth
            try:
                rel_path = file_path.relative_to(agentmap_root)
                depth = len(rel_path.parts) - 1  # Subtract 1 for the file itself
                
                if depth > 0:
                    # Use the predefined patterns with proper depth calculation
                    relative_prefix = '../' * depth
                    
                    for abs_pattern, rel_template in self.CIRCULAR_IMPORT_PATTERNS.items():
                        # Replace the .. prefix with the calculated relative prefix
                        relative_replacement = rel_template.replace('..', relative_prefix.rstrip('/'))
                        patterns[abs_pattern] = relative_replacement
                    
                    self.logger.debug(
                        f"[ImportFixerService] Calculated {len(patterns)} relative patterns for {file_path} "
                        f"(depth: {depth})"
                    )
                else:
                    self.logger.debug(f"[ImportFixerService] File at root level, no relative imports needed: {file_path}")
            
            except ValueError as e:
                self.logger.warning(f"[ImportFixerService] Could not calculate relative path: {e}")
        
        except Exception as e:
            self.logger.warning(f"[ImportFixerService] Error calculating relative patterns: {e}")
        
        return patterns
    
    def _extract_typing_symbols_comprehensive(self, content: str) -> Set[str]:
        """Extract typing symbols used in the file with comprehensive pattern matching."""
        used_symbols = set()
        
        # Apply enhanced pattern matching
        for pattern in self.TYPE_HINT_PATTERNS:
            matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle patterns that return tuples
                    for submatch in match:
                        symbols = re.findall(r'[A-Z][a-zA-Z_]*', submatch)
                        used_symbols.update(symbols)
                else:
                    # Extract symbol names from type hints
                    symbols = re.findall(r'[A-Z][a-zA-Z_]*', match)
                    used_symbols.update(symbols)
        
        # Additional pattern: look for direct typing symbol usage in isinstance, etc.
        direct_usage_patterns = [
            r'isinstance\([^,]+,\s*([A-Z][a-zA-Z_]*)',
            r'issubclass\([^,]+,\s*([A-Z][a-zA-Z_]*)',
            r'type\s*\[([A-Z][a-zA-Z_]*)\]',
        ]
        
        for pattern in direct_usage_patterns:
            matches = re.findall(pattern, content)
            used_symbols.update(matches)
        
        # Filter to only known typing symbols
        typing_symbols_used = used_symbols.intersection(self.TYPING_SYMBOLS)
        
        self.logger.debug(
            f"[ImportFixerService] Found typing symbols: {typing_symbols_used}"
        )
        
        return typing_symbols_used
    
    def _extract_existing_typing_imports(self, lines: List[str]) -> Tuple[Set[str], Optional[int]]:
        """Extract existing typing imports and their line number with enhanced parsing."""
        imported_symbols = set()
        typing_import_line = None
        
        for i, line in enumerate(lines):
            stripped_line = line.strip()
            
            # Handle various typing import formats
            if 'from typing import' in stripped_line:
                typing_import_line = i
                
                # Extract imported symbols, handling multi-line imports
                import_part = stripped_line.split('from typing import')[1].strip()
                
                # Remove parentheses for multi-line imports
                import_part = import_part.strip('()')
                
                # Split by comma and clean up
                symbols = [s.strip() for s in import_part.split(',') if s.strip()]
                
                # Handle symbols that might have comments
                clean_symbols = []
                for symbol in symbols:
                    # Remove inline comments
                    clean_symbol = symbol.split('#')[0].strip()
                    if clean_symbol:
                        clean_symbols.append(clean_symbol)
                
                imported_symbols.update(clean_symbols)
                
                # For multi-line imports, check following lines
                j = i + 1
                while j < len(lines) and not lines[j].strip().endswith(')'):
                    continuation = lines[j].strip()
                    if continuation and not continuation.startswith('#'):
                        symbols = [s.strip() for s in continuation.split(',') if s.strip()]
                        for symbol in symbols:
                            clean_symbol = symbol.split('#')[0].strip().rstrip(',')
                            if clean_symbol:
                                imported_symbols.add(clean_symbol)
                    j += 1
        
        return imported_symbols, typing_import_line
    
    def _find_import_insertion_point(self, lines: List[str]) -> int:
        """Find the best place to insert new import statements."""
        # Find the last import line
        last_import_line = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')) and not line.strip().startswith('#'):
                last_import_line = i
        
        # Insert after the last import, or at the beginning if no imports
        return last_import_line + 1 if last_import_line > 0 else 0
    
    def _has_import_comprehensive(self, content: str, module_name: str, required_import: str) -> bool:
        """Check if a module or specific import is already present."""
        # Check for exact import statement
        if required_import in content:
            return True
        
        # Check for module-level imports
        patterns = [
            f'from {module_name} import',
            f'import {module_name}',
            f'import {module_name} as',
        ]
        
        for pattern in patterns:
            if pattern in content:
                return True
        
        # Check for specific symbol imports from the module
        import_symbol = required_import.split(' import ')[-1] if ' import ' in required_import else None
        if import_symbol:
            symbol_patterns = [
                f'from {module_name} import.*{import_symbol}',
                f'from {module_name} import {import_symbol}',
            ]
            for pattern in symbol_patterns:
                if re.search(pattern, content):
                    return True
        
        return False
    
    def _validate_typing_symbols(self, symbols: Set[str], content: str) -> Set[str]:
        """Validate that typing symbols are actually used in valid contexts."""
        validated_symbols = set()
        
        for symbol in symbols:
            # Check if the symbol is used in a valid typing context
            typing_context_patterns = [
                f':\s*{symbol}\b',  # Type annotation
                f'->\s*{symbol}\b',  # Return type
                f'\[.*{symbol}.*\]',  # Generic parameter
                f'Union\[.*{symbol}.*\]',  # Union type
                f'Optional\[.*{symbol}.*\]',  # Optional type
                f'isinstance\(.*{symbol}\)',  # Type checking
            ]
            
            for pattern in typing_context_patterns:
                if re.search(pattern, content):
                    validated_symbols.add(symbol)
                    break
        
        return validated_symbols
    
    def _validate_standard_library_usage(self, pattern: str, content: str) -> bool:
        """Validate that standard library patterns represent actual usage."""
        matches = list(re.finditer(pattern, content, re.MULTILINE))
        
        for match in matches:
            # Get the context around the match
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            context = content[start:end]
            
            # Skip if it's in a comment or string
            if any(marker in context for marker in ['#', '"""', "'''", 'r"', "r'"]):
                continue
            
            # Skip if it's in a docstring or comment line
            lines_around = context.split('\n')
            for line in lines_around:
                if match.group() in line:
                    stripped = line.strip()
                    if stripped.startswith('#') or '"""' in stripped or "'''" in stripped:
                        continue
                    else:
                        return True
        
        return False
    
    def _create_backup(self, file_path: Path) -> Path:
        """
        Create a backup of the file before modification.
        
        Args:
            file_path: Original file path
            
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.with_suffix(f'.backup_{timestamp}{file_path.suffix}')
        shutil.copy2(file_path, backup_path)
        self.logger.debug(f"[ImportFixerService] Created backup: {backup_path}")
        return backup_path
    
    def get_service_info(self) -> Dict[str, any]:
        """
        Get information about the import fixer service for debugging.
        
        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "service": "ImportFixerService",
            "validation_service_available": self.validation is not None,
            "config_available": self.config is not None,
            "typing_symbols_count": len(self.TYPING_SYMBOLS),
            "standard_patterns_count": len(self.STANDARD_IMPORT_PATTERNS),
            "initialized": True
        }
