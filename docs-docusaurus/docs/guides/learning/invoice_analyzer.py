"""
Invoice Analyzer Agent

Specialized agent for analyzing invoices, bills, and financial documents.
Extracts amounts, validates data, and performs tax analysis.
"""

from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any, List
import re
from datetime import datetime


class InvoiceAnalyzerAgent(BaseAgent):
    """
    Specialized agent for invoice and financial document analysis.
    
    Analyzes invoices for:
    - Amount extraction and validation
    - Tax calculations
    - Payment terms
    - Vendor information
    - Line item details
    """
    
    def __init__(self, name: str, prompt: str, context: Dict[str, Any] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        self.extract_amounts = self.context.get('extract_amounts', True)
        self.validate_data = self.context.get('validate_data', True)
        self.tax_analysis = self.context.get('tax_analysis', True)
        
        self.log_info(f"InvoiceAnalyzer initialized with tax_analysis: {self.tax_analysis}")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Analyze invoice document for financial data and validation.
        
        Args:
            inputs: Contains document_content and classification_result
            
        Returns:
            Dict: Comprehensive invoice analysis
        """
        try:
            document_content = inputs.get('document_content', '')
            classification = inputs.get('classification_result', {})
            
            if not document_content:
                return {"error": "No document content provided for invoice analysis"}
            
            self.log_info("Starting invoice analysis")
            
            analysis = {
                'document_type': 'invoice',
                'amounts': self._extract_amounts(document_content) if self.extract_amounts else {},
                'vendor_info': self._extract_vendor_info(document_content),
                'payment_terms': self._extract_payment_terms(document_content),
                'tax_analysis': self._perform_tax_analysis(document_content) if self.tax_analysis else {},
                'validation': self._validate_invoice_data(document_content) if self.validate_data else {},
                'line_items': self._extract_line_items(document_content),
                'metadata': {
                    'analysis_date': datetime.now().isoformat(),
                    'confidence_score': classification.get('confidence', 0.0),
                    'document_format': self._detect_format(document_content)
                }
            }
            
            self.log_info("Invoice analysis completed successfully")
            return analysis
            
        except Exception as e:
            error_msg = f"Invoice analysis failed: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg}
    
    def _extract_amounts(self, content: str) -> Dict[str, Any]:
        """Extract all monetary amounts from the invoice."""
        # Various money patterns
        money_patterns = [
            r'\$([0-9,]+(?:\.[0-9]{2})?)',  # $1,234.56
            r'USD\s*([0-9,]+(?:\.[0-9]{2})?)',  # USD 1234.56
            r'([0-9,]+\.[0-9]{2})\s*USD',  # 1234.56 USD
        ]
        
        amounts = []
        for pattern in money_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            amounts.extend(matches)
        
        # Clean and convert amounts
        clean_amounts = []
        for amount in amounts:
            try:
                clean_amount = float(amount.replace(',', ''))
                clean_amounts.append(clean_amount)
            except ValueError:
                continue
        
        return {
            'raw_amounts': amounts[:20],  # Limit to prevent overflow
            'parsed_amounts': clean_amounts[:20],
            'total_sum': sum(clean_amounts),
            'largest_amount': max(clean_amounts) if clean_amounts else 0,
            'amount_count': len(clean_amounts)
        }
    
    def _extract_vendor_info(self, content: str) -> Dict[str, Any]:
        """Extract vendor/supplier information."""
        vendor_info = {}
        
        # Look for company names
        company_pattern = r'([A-Z][a-zA-Z\s]+(?:LLC|Inc|Corp|Corporation|Ltd))'
        companies = re.findall(company_pattern, content)
        
        # Look for email addresses
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        emails = re.findall(email_pattern, content)
        
        # Look for phone numbers
        phone_pattern = r'(\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})'
        phones = re.findall(phone_pattern, content)
        
        return {
            'companies': list(set(companies))[:5],
            'emails': list(set(emails))[:3],
            'phones': list(set(phones))[:3],
            'vendor_identified': len(companies) > 0
        }
    
    def _extract_payment_terms(self, content: str) -> Dict[str, Any]:
        """Extract payment terms and due dates."""
        payment_terms = {}
        
        content_lower = content.lower()
        
        # Look for common payment terms
        if 'net 30' in content_lower:
            payment_terms['terms'] = 'Net 30'
        elif 'net 15' in content_lower:
            payment_terms['terms'] = 'Net 15'
        elif 'due on receipt' in content_lower or 'due immediately' in content_lower:
            payment_terms['terms'] = 'Due on receipt'
        else:
            payment_terms['terms'] = 'Not specified'
        
        # Look for due dates
        date_pattern = r'(\w+\s+\d+,\s+\d{4})'
        dates = re.findall(date_pattern, content)
        payment_terms['dates_mentioned'] = dates[:3]
        
        # Look for invoice numbers
        invoice_pattern = r'(?:invoice|inv)[\s#]*([A-Z0-9-]+)'
        invoice_numbers = re.findall(invoice_pattern, content, re.IGNORECASE)
        payment_terms['invoice_numbers'] = invoice_numbers[:3]
        
        return payment_terms
    
    def _perform_tax_analysis(self, content: str) -> Dict[str, Any]:
        """Analyze tax-related information."""
        tax_analysis = {}
        
        content_lower = content.lower()
        
        # Look for tax mentions
        tax_keywords = ['tax', 'vat', 'gst', 'sales tax', 'tax rate']
        tax_mentions = [keyword for keyword in tax_keywords if keyword in content_lower]
        
        # Look for percentage patterns (potential tax rates)
        percentage_pattern = r'([0-9.]+)%'
        percentages = re.findall(percentage_pattern, content)
        
        # Look for tax amounts
        tax_amount_patterns = [
            r'tax[:\s]*\$?([0-9,]+(?:\.[0-9]{2})?)',
            r'vat[:\s]*\$?([0-9,]+(?:\.[0-9]{2})?)'
        ]
        
        tax_amounts = []
        for pattern in tax_amount_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            tax_amounts.extend(matches)
        
        return {
            'tax_mentioned': len(tax_mentions) > 0,
            'tax_keywords_found': tax_mentions,
            'potential_tax_rates': percentages[:5],
            'potential_tax_amounts': tax_amounts[:5],
            'tax_complexity': 'high' if len(tax_mentions) > 2 else 'low'
        }
    
    def _validate_invoice_data(self, content: str) -> Dict[str, Any]:
        """Validate invoice data for completeness and accuracy."""
        validation = {}
        
        # Check for essential elements
        validation['has_amounts'] = '$' in content or 'usd' in content.lower()
        validation['has_dates'] = bool(re.search(r'\d{4}', content))
        validation['has_vendor_info'] = bool(re.search(r'(llc|inc|corp|ltd)', content, re.IGNORECASE))
        validation['has_contact_info'] = '@' in content or bool(re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', content))
        
        # Calculate completeness score
        checks = [validation['has_amounts'], validation['has_dates'], 
                 validation['has_vendor_info'], validation['has_contact_info']]
        completeness_score = sum(checks) / len(checks)
        
        validation['completeness_score'] = completeness_score
        validation['validation_status'] = 'complete' if completeness_score >= 0.75 else 'incomplete'
        
        # Check for potential issues
        issues = []
        if not validation['has_amounts']:
            issues.append("No monetary amounts found")
        if not validation['has_vendor_info']:
            issues.append("Vendor information unclear")
        if not validation['has_dates']:
            issues.append("No dates specified")
        
        validation['issues'] = issues
        
        return validation
    
    def _extract_line_items(self, content: str) -> Dict[str, Any]:
        """Extract individual line items from the invoice."""
        # This is a simplified line item extraction
        # Look for lines that might contain item descriptions and amounts
        lines = content.split('\n')
        potential_line_items = []
        
        for line in lines:
            line = line.strip()
            # Skip very short lines or headers
            if len(line) < 10:
                continue
            
            # Look for lines with both text and amounts
            if re.search(r'\$[0-9,]+', line) and len(line.split()) > 2:
                potential_line_items.append(line[:100])  # Truncate for safety
        
        return {
            'potential_line_items': potential_line_items[:10],
            'line_item_count': len(potential_line_items),
            'detailed_breakdown': len(potential_line_items) > 3
        }
    
    def _detect_format(self, content: str) -> str:
        """Detect the format/structure of the invoice."""
        if 'invoice' in content.lower():
            return 'formal_invoice'
        elif 'receipt' in content.lower():
            return 'receipt'
        elif 'bill' in content.lower():
            return 'bill'
        elif '$' in content:
            return 'financial_document'
        else:
            return 'unknown'


# Register the agent for use in workflows
def create_invoice_analyzer_agent(name: str, prompt: str, context: Dict[str, Any] = None, **kwargs) -> InvoiceAnalyzerAgent:
    """Factory function to create InvoiceAnalyzerAgent instances."""
    return InvoiceAnalyzerAgent(name, prompt, context, **kwargs)


# Export for AgentMap registration
__all__ = ['InvoiceAnalyzerAgent', 'create_invoice_analyzer_agent']
