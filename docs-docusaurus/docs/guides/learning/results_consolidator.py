"""
Results Consolidator Agent

Specialized agent for consolidating and combining analysis results from multiple agents.
Merges outputs, generates summaries, and provides unified reporting.
"""

from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any, List
import json
from datetime import datetime


class ResultsConsolidatorAgent(BaseAgent):
    """
    Specialized agent for consolidating results from multiple analysis agents.
    
    Consolidates results from:
    - Contract analyzer
    - Invoice analyzer
    - Report analyzer
    - Email analyzer
    - General analysis
    """
    
    def __init__(self, name: str, prompt: str, context: Dict[str, Any] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        self.include_metadata = self.context.get('include_metadata', True)
        self.generate_summary = self.context.get('generate_summary', True)
        
        self.log_info(f"ResultsConsolidator initialized with generate_summary: {self.generate_summary}")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Consolidate analysis results from multiple specialized agents.
        
        Args:
            inputs: Contains results from various analysis agents
            
        Returns:
            Dict: Consolidated analysis results with unified structure
        """
        try:
            self.log_info("Starting results consolidation")
            
            # Extract individual analysis results
            contract_analysis = inputs.get('contract_analysis', {})
            invoice_analysis = inputs.get('invoice_analysis', {})
            report_analysis = inputs.get('report_analysis', {})
            email_analysis = inputs.get('email_analysis', {})
            general_analysis = inputs.get('general_analysis', {})
            classification_result = inputs.get('classification_result', {})
            
            # Determine which analysis was actually performed
            performed_analyses = self._identify_performed_analyses(inputs)
            
            # Consolidate results
            consolidated = {
                'consolidation_metadata': {
                    'consolidation_date': datetime.now().isoformat(),
                    'analyses_performed': performed_analyses,
                    'analysis_count': len(performed_analyses),
                    'primary_analysis': self._determine_primary_analysis(performed_analyses, classification_result)
                },
                'document_classification': classification_result,
                'specialized_analyses': {
                    'contract': contract_analysis if contract_analysis else None,
                    'invoice': invoice_analysis if invoice_analysis else None,
                    'report': report_analysis if report_analysis else None,
                    'email': email_analysis if email_analysis else None
                },
                'general_analysis': general_analysis,
                'unified_insights': self._generate_unified_insights(inputs),
                'cross_analysis_findings': self._perform_cross_analysis(inputs),
                'summary': self._generate_consolidated_summary(inputs) if self.generate_summary else {}
            }
            
            # Add metadata if requested
            if self.include_metadata:
                consolidated['processing_metadata'] = self._compile_processing_metadata(inputs)
            
            self.log_info(f"Results consolidation completed with {len(performed_analyses)} analyses")
            return consolidated
            
        except Exception as e:
            error_msg = f"Results consolidation failed: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg}
    
    def _identify_performed_analyses(self, inputs: Dict[str, Any]) -> List[str]:
        """Identify which specialized analyses were actually performed."""
        performed = []
        
        if inputs.get('contract_analysis') and not inputs.get('contract_analysis', {}).get('error'):
            performed.append('contract')
        if inputs.get('invoice_analysis') and not inputs.get('invoice_analysis', {}).get('error'):
            performed.append('invoice')
        if inputs.get('report_analysis') and not inputs.get('report_analysis', {}).get('error'):
            performed.append('report')
        if inputs.get('email_analysis') and not inputs.get('email_analysis', {}).get('error'):
            performed.append('email')
        if inputs.get('general_analysis') and not inputs.get('general_analysis', {}).get('error'):
            performed.append('general')
        
        return performed
    
    def _determine_primary_analysis(self, performed_analyses: List[str], classification: Dict[str, Any]) -> str:
        """Determine which analysis should be considered primary."""
        if not performed_analyses:
            return 'none'
        
        # Use classification result to determine primary analysis
        doc_category = classification.get('category', '').lower()
        
        if 'contract' in doc_category and 'contract' in performed_analyses:
            return 'contract'
        elif 'invoice' in doc_category and 'invoice' in performed_analyses:
            return 'invoice'
        elif 'report' in doc_category and 'report' in performed_analyses:
            return 'report'
        elif 'email' in doc_category and 'email' in performed_analyses:
            return 'email'
        else:
            return performed_analyses[0]  # Return first available
    
    def _generate_unified_insights(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights that span across different analysis types."""
        insights = {
            'document_complexity': self._assess_overall_complexity(inputs),
            'data_richness': self._assess_data_richness(inputs),
            'actionability': self._assess_actionability(inputs),
            'risk_indicators': self._compile_risk_indicators(inputs),
            'quality_assessment': self._assess_overall_quality(inputs)
        }
        
        return insights
    
    def _assess_overall_complexity(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the overall complexity of the document."""
        complexity_indicators = []
        
        # Check contract complexity
        contract_analysis = inputs.get('contract_analysis', {})
        if contract_analysis and contract_analysis.get('risk_assessment', {}).get('risk_level') == 'high':
            complexity_indicators.append('High legal complexity')
        
        # Check report complexity
        report_analysis = inputs.get('report_analysis', {})
        if report_analysis and report_analysis.get('metadata', {}).get('document_complexity') == 'high':
            complexity_indicators.append('High analytical complexity')
        
        # Check financial complexity
        invoice_analysis = inputs.get('invoice_analysis', {})
        if invoice_analysis and invoice_analysis.get('tax_analysis', {}).get('tax_complexity') == 'high':
            complexity_indicators.append('High financial complexity')
        
        # Determine overall complexity
        if len(complexity_indicators) > 1:
            overall_complexity = 'high'
        elif len(complexity_indicators) == 1:
            overall_complexity = 'medium'
        else:
            overall_complexity = 'low'
        
        return {
            'overall_complexity': overall_complexity,
            'complexity_factors': complexity_indicators,
            'complexity_score': len(complexity_indicators)
        }
    
    def _assess_data_richness(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Assess how data-rich the document is."""
        data_richness = {
            'numerical_data': False,
            'structured_content': False,
            'detailed_information': False,
            'richness_score': 0
        }
        
        # Check for numerical data from various analyses
        invoice_analysis = inputs.get('invoice_analysis', {})
        if invoice_analysis and invoice_analysis.get('amounts', {}).get('amount_count', 0) > 0:
            data_richness['numerical_data'] = True
            data_richness['richness_score'] += 1
        
        report_analysis = inputs.get('report_analysis', {})
        if report_analysis and report_analysis.get('metrics', {}).get('data_richness') == 'high':
            data_richness['numerical_data'] = True
            data_richness['richness_score'] += 1
        
        # Check for structured content
        contract_analysis = inputs.get('contract_analysis', {})
        if contract_analysis and len(contract_analysis.get('key_terms', {})) > 3:
            data_richness['structured_content'] = True
            data_richness['richness_score'] += 1
        
        # Check for detailed information
        if report_analysis and report_analysis.get('structure_analysis', {}).get('section_count', 0) > 5:
            data_richness['detailed_information'] = True
            data_richness['richness_score'] += 1
        
        # Determine overall richness
        if data_richness['richness_score'] >= 3:
            data_richness['overall_richness'] = 'high'
        elif data_richness['richness_score'] >= 2:
            data_richness['overall_richness'] = 'medium'
        else:
            data_richness['overall_richness'] = 'low'
        
        return data_richness
    
    def _assess_actionability(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Assess how actionable the document content is."""
        actionability = {
            'has_action_items': False,
            'has_deadlines': False,
            'has_recommendations': False,
            'requires_response': False,
            'actionability_score': 0
        }
        
        # Check email for action items
        email_analysis = inputs.get('email_analysis', {})
        if email_analysis:
            if email_analysis.get('action_items', {}).get('requires_action', False):
                actionability['has_action_items'] = True
                actionability['actionability_score'] += 1
            
            if email_analysis.get('action_items', {}).get('has_deadlines', False):
                actionability['has_deadlines'] = True
                actionability['actionability_score'] += 1
            
            if email_analysis.get('response_requirements', {}).get('response_required', False):
                actionability['requires_response'] = True
                actionability['actionability_score'] += 1
        
        # Check contract for recommendations
        contract_analysis = inputs.get('contract_analysis', {})
        if contract_analysis and len(contract_analysis.get('recommendations', [])) > 0:
            actionability['has_recommendations'] = True
            actionability['actionability_score'] += 1
        
        # Determine overall actionability
        if actionability['actionability_score'] >= 3:
            actionability['overall_actionability'] = 'high'
        elif actionability['actionability_score'] >= 2:
            actionability['overall_actionability'] = 'medium'
        else:
            actionability['overall_actionability'] = 'low'
        
        return actionability
    
    def _compile_risk_indicators(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Compile risk indicators from all analyses."""
        risk_indicators = []
        
        # Contract risks
        contract_analysis = inputs.get('contract_analysis', {})
        if contract_analysis:
            contract_risks = contract_analysis.get('risk_assessment', {}).get('risk_factors', [])
            risk_indicators.extend([f"Legal: {risk}" for risk in contract_risks])
        
        # Email priority/urgency as risk indicator
        email_analysis = inputs.get('email_analysis', {})
        if email_analysis and email_analysis.get('priority', {}).get('priority_level') == 'high':
            risk_indicators.append("Communication: High priority/urgent email")
        
        return {
            'risk_indicators': risk_indicators,
            'risk_count': len(risk_indicators),
            'overall_risk_level': 'high' if len(risk_indicators) > 2 else 'medium' if len(risk_indicators) > 0 else 'low'
        }
    
    def _assess_overall_quality(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the overall quality of the document."""
        quality_scores = []
        
        # Report quality
        report_analysis = inputs.get('report_analysis', {})
        if report_analysis:
            quality_score = report_analysis.get('data_quality', {}).get('overall_quality_score', 0)
            if quality_score > 0:
                quality_scores.append(quality_score)
        
        # Invoice validation quality
        invoice_analysis = inputs.get('invoice_analysis', {})
        if invoice_analysis:
            completeness = invoice_analysis.get('validation', {}).get('completeness_score', 0)
            if completeness > 0:
                quality_scores.append(completeness)
        
        # Calculate average quality
        if quality_scores:
            avg_quality = sum(quality_scores) / len(quality_scores)
            quality_rating = 'high' if avg_quality > 0.7 else 'medium' if avg_quality > 0.4 else 'low'
        else:
            avg_quality = 0.5  # Default neutral
            quality_rating = 'medium'
        
        return {
            'average_quality_score': round(avg_quality, 2),
            'quality_rating': quality_rating,
            'quality_assessments': len(quality_scores)
        }
    
    def _perform_cross_analysis(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Perform analysis across different specialized results."""
        cross_analysis = {}
        
        # Check for consistency between classification and specialized analysis
        classification = inputs.get('classification_result', {})
        predicted_category = classification.get('category', '').lower()
        
        # Verify if the right specialized analysis was performed
        if 'contract' in predicted_category and inputs.get('contract_analysis'):
            cross_analysis['classification_match'] = True
        elif 'invoice' in predicted_category and inputs.get('invoice_analysis'):
            cross_analysis['classification_match'] = True
        elif 'report' in predicted_category and inputs.get('report_analysis'):
            cross_analysis['classification_match'] = True
        elif 'email' in predicted_category and inputs.get('email_analysis'):
            cross_analysis['classification_match'] = True
        else:
            cross_analysis['classification_match'] = False
        
        # Look for conflicting information
        conflicts = []
        
        # Check for sentiment vs priority conflicts (email analysis)
        email_analysis = inputs.get('email_analysis', {})
        if email_analysis:
            sentiment = email_analysis.get('sentiment', {}).get('overall_sentiment')
            priority = email_analysis.get('priority', {}).get('priority_level')
            
            if sentiment == 'negative' and priority == 'low':
                conflicts.append("Negative sentiment with low priority may indicate missed urgency")
        
        cross_analysis['conflicts'] = conflicts
        cross_analysis['analysis_consistency'] = len(conflicts) == 0
        
        return cross_analysis
    
    def _generate_consolidated_summary(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a high-level summary of all analyses."""
        classification = inputs.get('classification_result', {})
        performed_analyses = self._identify_performed_analyses(inputs)
        
        summary = {
            'document_type': classification.get('category', 'Unknown'),
            'confidence': classification.get('confidence', 0),
            'analyses_performed': performed_analyses,
            'key_findings': [],
            'recommendations': [],
            'next_steps': []
        }
        
        # Compile key findings from each analysis
        for analysis_type in performed_analyses:
            analysis_data = inputs.get(f'{analysis_type}_analysis', {})
            if analysis_type == 'contract' and analysis_data:
                summary['key_findings'].append(f"Contract type: {analysis_data.get('contract_type', {}).get('primary_type', 'Unknown')}")
                summary['recommendations'].extend(analysis_data.get('recommendations', [])[:2])
            elif analysis_type == 'email' and analysis_data:
                sentiment = analysis_data.get('sentiment', {}).get('overall_sentiment', 'neutral')
                priority = analysis_data.get('priority', {}).get('priority_level', 'medium')
                summary['key_findings'].append(f"Email sentiment: {sentiment}, Priority: {priority}")
                if analysis_data.get('response_requirements', {}).get('response_required'):
                    summary['next_steps'].append("Response required to email")
        
        return summary
    
    def _compile_processing_metadata(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Compile metadata from all processing steps."""
        metadata = {
            'processing_timestamp': datetime.now().isoformat(),
            'agent_metadata': {},
            'processing_statistics': {}
        }
        
        # Collect metadata from each analysis
        for key, value in inputs.items():
            if isinstance(value, dict) and 'metadata' in value:
                metadata['agent_metadata'][key] = value['metadata']
        
        # Compile processing statistics
        total_analyses = len([k for k in inputs.keys() if k.endswith('_analysis')])
        successful_analyses = len([k for k, v in inputs.items() if k.endswith('_analysis') and not v.get('error')])
        
        metadata['processing_statistics'] = {
            'total_analyses_attempted': total_analyses,
            'successful_analyses': successful_analyses,
            'success_rate': successful_analyses / total_analyses if total_analyses > 0 else 0
        }
        
        return metadata


# Register the agent for use in workflows
def create_results_consolidator_agent(name: str, prompt: str, context: Dict[str, Any] = None, **kwargs) -> ResultsConsolidatorAgent:
    """Factory function to create ResultsConsolidatorAgent instances."""
    return ResultsConsolidatorAgent(name, prompt, context, **kwargs)


# Export for AgentMap registration
__all__ = ['ResultsConsolidatorAgent', 'create_results_consolidator_agent']
