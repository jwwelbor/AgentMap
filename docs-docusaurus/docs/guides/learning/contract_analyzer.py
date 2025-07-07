"""
Contract Analyzer Agent

Specialized agent for analyzing legal contracts and agreements.
Extracts key terms, identifies risks, and provides legal insights.
"""

from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any, List
import re
from datetime import datetime


class ContractAnalyzerAgent(BaseAgent):
    """
    Specialized agent for contract analysis and legal document processing.
    
    Analyzes contracts for:
    - Key terms and conditions
    - Financial obligations
    - Risk factors
    - Compliance requirements
    - Timeline and deliverables
    """
    
    def __init__(self, name: str, prompt: str, context: Dict[str, Any] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        self.analysis_depth = self.context.get('analysis_depth', 'standard')
        self.legal_focus = self.context.get('legal_focus', True)
        self.risk_assessment = self.context.get('risk_assessment', True)
        
        self.log_info(f"ContractAnalyzer initialized with depth: {self.analysis_depth}")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Analyze contract document for legal terms, risks, and key provisions.
        
        Args:
            inputs: Contains document_content and classification_result
            
        Returns:
            Dict: Comprehensive contract analysis
        """
        try:
            document_content = inputs.get('document_content', '')
            classification = inputs.get('classification_result', {})
            
            if not document_content:
                return {"error": "No document content provided for contract analysis"}
            
            self.log_info("Starting contract analysis")
            
            analysis = {
                'contract_type': self._identify_contract_type(document_content),
                'parties': self._extract_parties(document_content),
                'key_terms': self._extract_key_terms(document_content),
                'financial_terms': self._extract_financial_terms(document_content),
                'timeline_analysis': self._analyze_timeline(document_content),
                'risk_assessment': self._assess_risks(document_content) if self.risk_assessment else {},
                'compliance_check': self._check_compliance(document_content),
                'recommendations': self._generate_recommendations(document_content),
                'metadata': {
                    'analysis_date': datetime.now().isoformat(),
                    'confidence_score': classification.get('confidence', 0.0),
                    'analysis_depth': self.analysis_depth
                }
            }
            
            self.log_info("Contract analysis completed successfully")
            return analysis
            
        except Exception as e:
            error_msg = f"Contract analysis failed: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg}
    
    def _identify_contract_type(self, content: str) -> Dict[str, Any]:
        """Identify the specific type of contract."""
        content_lower = content.lower()
        
        contract_types = {
            'service_agreement': ['service agreement', 'services agreement', 'consulting agreement'],
            'software_development': ['software development', 'development services', 'programming services'],
            'nda': ['non-disclosure agreement', 'confidentiality agreement', 'nda'],
            'employment': ['employment agreement', 'employment contract', 'job offer'],
            'lease': ['lease agreement', 'rental agreement', 'tenancy agreement'],
            'purchase': ['purchase agreement', 'sales agreement', 'buy-sell agreement']
        }
        
        detected_types = []
        for contract_type, keywords in contract_types.items():
            for keyword in keywords:
                if keyword in content_lower:
                    detected_types.append(contract_type)
                    break
        
        return {
            'primary_type': detected_types[0] if detected_types else 'unknown',
            'all_detected_types': detected_types,
            'confidence': 0.9 if detected_types else 0.3
        }
    
    def _extract_parties(self, content: str) -> Dict[str, Any]:
        """Extract contracting parties information."""
        # Look for company names and signatures
        company_pattern = r'([A-Z][a-zA-Z\s]+(?:LLC|Inc|Corp|Corporation))'
        companies = re.findall(company_pattern, content)
        
        # Look for signatures
        signature_pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+),\s*([A-Z][a-zA-Z\s]*)'
        signatures = re.findall(signature_pattern, content)
        
        return {
            'companies': list(set(companies))[:5],  # Limit and deduplicate
            'signatures': signatures[:5],
            'party_count': len(set(companies))
        }
    
    def _extract_key_terms(self, content: str) -> Dict[str, Any]:
        """Extract key contractual terms and conditions."""
        key_terms = {}
        
        # Check for termination clause
        if 'termination' in content.lower() or 'terminate' in content.lower():
            key_terms['termination'] = 'Present'
        
        # Check for confidentiality
        if 'confidential' in content.lower() or 'non-disclosure' in content.lower():
            key_terms['confidentiality'] = 'Present'
        
        # Check for IP terms
        if 'intellectual property' in content.lower() or 'copyright' in content.lower():
            key_terms['intellectual_property'] = 'Present'
            
        # Check for warranties
        if 'warrant' in content.lower() or 'guarantee' in content.lower():
            key_terms['warranties'] = 'Present'
        
        return key_terms
    
    def _extract_financial_terms(self, content: str) -> Dict[str, Any]:
        """Extract financial obligations and payment terms."""
        # Look for monetary amounts
        money_pattern = r'\$([0-9,]+(?:\.[0-9]{2})?)'
        amounts = re.findall(money_pattern, content)
        
        # Calculate total if multiple amounts found
        total = 0
        for amount in amounts:
            try:
                clean_amount = amount.replace(',', '')
                total += float(clean_amount)
            except ValueError:
                continue
        
        return {
            'amounts_found': amounts[:10],  # Limit to prevent overflow
            'total_value': total,
            'currency': 'USD',
            'payment_schedule': 'installments' if len(amounts) > 1 else 'lump_sum'
        }
    
    def _analyze_timeline(self, content: str) -> Dict[str, Any]:
        """Extract timeline and milestone information."""
        timeline = {}
        
        # Look for week patterns
        week_pattern = r'Week\s+(\d+)'
        weeks = re.findall(week_pattern, content, re.IGNORECASE)
        
        # Look for date patterns
        date_pattern = r'(\w+\s+\d+,\s+\d{4})'
        dates = re.findall(date_pattern, content)
        
        timeline['milestones'] = f"{len(weeks)} week-based milestones found" if weeks else "No clear milestones"
        timeline['dates_mentioned'] = dates[:5]  # Limit dates
        timeline['duration_weeks'] = max([int(w) for w in weeks]) if weeks else 0
        
        return timeline
    
    def _assess_risks(self, content: str) -> Dict[str, Any]:
        """Assess potential risks in the contract."""
        risks = []
        
        # Check for common risk indicators
        content_lower = content.lower()
        
        if 'penalty' in content_lower or 'damages' in content_lower:
            risks.append("Financial penalties present")
            
        if 'exclusive' in content_lower:
            risks.append("Exclusivity clauses detected")
            
        if 'liability' in content_lower:
            risks.append("Liability terms present")
            
        if 'indemnification' in content_lower or 'indemnify' in content_lower:
            risks.append("Indemnification clauses found")
        
        return {
            'risk_factors': risks,
            'risk_level': 'high' if len(risks) > 2 else 'medium' if risks else 'low'
        }
    
    def _check_compliance(self, content: str) -> Dict[str, Any]:
        """Check for standard compliance elements."""
        compliance = {}
        
        content_lower = content.lower()
        
        # Check for standard legal elements
        compliance['signatures'] = 'present' if 'signature' in content_lower else 'missing'
        compliance['dates'] = 'present' if re.search(r'\d{4}', content) else 'missing'
        compliance['parties_identified'] = 'present' if 'llc' in content_lower or 'inc' in content_lower else 'unclear'
        compliance['governing_law'] = 'present' if 'law' in content_lower or 'jurisdiction' in content_lower else 'not_specified'
        
        return compliance
    
    def _generate_recommendations(self, content: str) -> List[str]:
        """Generate recommendations based on analysis."""
        recommendations = []
        
        if 'termination' not in content.lower():
            recommendations.append("Consider adding clear termination clauses")
            
        if '$' not in content:
            recommendations.append("Clarify payment terms and amounts")
            
        if 'confidential' not in content.lower():
            recommendations.append("Consider adding confidentiality provisions")
            
        if not recommendations:
            recommendations.append("Contract appears to have standard provisions")
        
        return recommendations


# Register the agent for use in workflows
def create_contract_analyzer_agent(name: str, prompt: str, context: Dict[str, Any] = None, **kwargs) -> ContractAnalyzerAgent:
    """Factory function to create ContractAnalyzerAgent instances."""
    return ContractAnalyzerAgent(name, prompt, context, **kwargs)


# Export for AgentMap registration
__all__ = ['ContractAnalyzerAgent', 'create_contract_analyzer_agent']
