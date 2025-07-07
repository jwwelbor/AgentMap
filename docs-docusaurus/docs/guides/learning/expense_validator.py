"""
Custom Expense Validator Agent

This agent demonstrates custom business logic implementation
by validating expense data against company policies.
"""

from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any, List
from datetime import datetime
import re


class ExpenseValidatorAgent(BaseAgent):
    """
    Custom agent that validates expense data against business rules.
    
    This agent demonstrates:
    - Custom process() method implementation
    - Business rule validation
    - Data transformation and enrichment
    - Error handling and logging
    """
    
    def __init__(self, name: str, prompt: str, context: Dict[str, Any] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        # Initialize validation rules from context
        self.max_amount = self.context.get('max_amount', 1000)
        self.required_fields = self.context.get('required_fields', ['amount', 'description', 'date'])
        self.allowed_categories = self.context.get('allowed_categories', [])
        
        self.log_info(f"ExpenseValidator initialized with max_amount: ${self.max_amount}")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Validate expense data against business rules.
        
        Args:
            inputs: Dictionary containing 'expense_data' from CSV reader
            
        Returns:
            Dict: Validation results with flagged expenses and statistics
        """
        try:
            expense_data = inputs.get('expense_data', [])
            
            if not expense_data:
                self.log_warning("No expense data provided for validation")
                return {"error": "No expense data to validate"}
            
            self.log_info(f"Starting validation of {len(expense_data)} expenses")
            
            # Process each expense through validation pipeline
            validation_results = []
            stats = {
                'total_expenses': len(expense_data),
                'valid_expenses': 0,
                'flagged_expenses': 0,
                'total_amount': 0.0,
                'validation_errors': []
            }
            
            for i, expense in enumerate(expense_data):
                try:
                    result = self._validate_single_expense(expense, i)
                    validation_results.append(result)
                    
                    # Update statistics
                    stats['total_amount'] += float(result.get('amount', 0))
                    if result.get('is_valid', True):
                        stats['valid_expenses'] += 1
                    else:
                        stats['flagged_expenses'] += 1
                        
                except Exception as e:
                    error_msg = f"Error processing expense {i}: {str(e)}"
                    self.log_error(error_msg)
                    stats['validation_errors'].append(error_msg)
            
            # Generate summary
            summary = self._generate_validation_summary(stats)
            
            result = {
                'validation_results': validation_results,
                'statistics': stats,
                'summary': summary
            }
            
            self.log_info(f"Validation complete: {stats['valid_expenses']}/{stats['total_expenses']} valid expenses")
            return result
            
        except Exception as e:
            error_msg = f"ExpenseValidator process failed: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg}
    
    def _validate_single_expense(self, expense: Dict[str, Any], index: int) -> Dict[str, Any]:
        """
        Validate a single expense record against business rules.
        
        Args:
            expense: Individual expense record
            index: Record index for tracking
            
        Returns:
            Dict: Validation result with flags and details
        """
        result = {
            'index': index,
            'original_expense': expense,
            'is_valid': True,
            'validation_flags': [],
            'amount': 0.0,
            'cleaned_description': '',
            'date_parsed': None
        }
        
        # Required field validation
        missing_fields = []
        for field in self.required_fields:
            if field not in expense or not expense[field]:
                missing_fields.append(field)
                result['is_valid'] = False
        
        if missing_fields:
            result['validation_flags'].append(f"Missing required fields: {', '.join(missing_fields)}")
        
        # Amount validation
        try:
            amount = float(expense.get('amount', 0))
            result['amount'] = amount
            
            if amount <= 0:
                result['validation_flags'].append("Invalid amount: must be positive")
                result['is_valid'] = False
            elif amount > self.max_amount:
                result['validation_flags'].append(f"Amount exceeds limit: ${amount} > ${self.max_amount}")
                result['is_valid'] = False
                
        except (ValueError, TypeError):
            result['validation_flags'].append("Invalid amount format")
            result['is_valid'] = False
        
        # Description validation and cleaning
        description = expense.get('description', '').strip()
        if description:
            result['cleaned_description'] = self._clean_description(description)
            if len(description) < 5:
                result['validation_flags'].append("Description too short")
                result['is_valid'] = False
        
        # Date validation
        date_str = expense.get('date', '')
        if date_str:
            parsed_date = self._parse_date(date_str)
            if parsed_date:
                result['date_parsed'] = parsed_date
                # Check if date is in reasonable range (not future, not too old)
                if parsed_date > datetime.now():
                    result['validation_flags'].append("Date is in the future")
                    result['is_valid'] = False
            else:
                result['validation_flags'].append("Invalid date format")
                result['is_valid'] = False
        
        # Receipt validation
        receipt = expense.get('receipt', '').lower()
        if receipt == 'no' or not receipt:
            result['validation_flags'].append("No receipt provided")
            # This is a warning, not an error for validation
        
        # Employee validation
        employee = expense.get('employee', '').strip()
        if not employee or employee.lower() in ['unknown', 'anonymous']:
            result['validation_flags'].append("Employee identification missing or suspicious")
            result['is_valid'] = False
        
        return result
    
    def _clean_description(self, description: str) -> str:
        """Clean and normalize expense description."""
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', description.strip())
        # Remove special characters that might cause issues
        cleaned = re.sub(r'[^\w\s\-\.,()]', '', cleaned)
        return cleaned
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse date string into datetime object."""
        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%Y-%m-%d %H:%M:%S'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _generate_validation_summary(self, stats: Dict[str, Any]) -> str:
        """Generate human-readable validation summary."""
        summary_lines = [
            f"📊 Expense Validation Summary",
            f"Total Expenses: {stats['total_expenses']}",
            f"Valid Expenses: {stats['valid_expenses']}",
            f"Flagged Expenses: {stats['flagged_expenses']}",
            f"Total Amount: ${stats['total_amount']:.2f}",
        ]
        
        if stats['validation_errors']:
            summary_lines.append(f"Processing Errors: {len(stats['validation_errors'])}")
        
        if stats['flagged_expenses'] > 0:
            percentage = (stats['flagged_expenses'] / stats['total_expenses']) * 100
            summary_lines.append(f"⚠️ {percentage:.1f}% of expenses require review")
        
        return "\n".join(summary_lines)


# Register the agent for use in workflows
def create_expense_validator_agent(name: str, prompt: str, context: Dict[str, Any] = None, **kwargs) -> ExpenseValidatorAgent:
    """Factory function to create ExpenseValidatorAgent instances."""
    return ExpenseValidatorAgent(name, prompt, context, **kwargs)


# Export for AgentMap registration
__all__ = ['ExpenseValidatorAgent', 'create_expense_validator_agent']
