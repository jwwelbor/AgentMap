"""
Report Analyzer Agent

Specialized agent for analyzing business reports, analytics documents, and presentations.
Extracts metrics, performs trend analysis, and generates insights.
"""

from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any, List
import re
from datetime import datetime


class ReportAnalyzerAgent(BaseAgent):
    """
    Specialized agent for business report and analytics document analysis.
    
    Analyzes reports for:
    - Key metrics and KPIs
    - Trend analysis
    - Data insights
    - Performance indicators
    - Recommendations
    """
    
    def __init__(self, name: str, prompt: str, context: Dict[str, Any] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        self.extract_metrics = self.context.get('extract_metrics', True)
        self.trend_analysis = self.context.get('trend_analysis', True)
        self.insights_generation = self.context.get('insights_generation', True)
        
        self.log_info(f"ReportAnalyzer initialized with insights_generation: {self.insights_generation}")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Analyze report document for metrics, trends, and insights.
        
        Args:
            inputs: Contains document_content and classification_result
            
        Returns:
            Dict: Comprehensive report analysis
        """
        try:
            document_content = inputs.get('document_content', '')
            classification = inputs.get('classification_result', {})
            
            if not document_content:
                return {"error": "No document content provided for report analysis"}
            
            self.log_info("Starting report analysis")
            
            analysis = {
                'document_type': 'business_report',
                'metrics': self._extract_metrics(document_content) if self.extract_metrics else {},
                'structure_analysis': self._analyze_structure(document_content),
                'key_themes': self._identify_themes(document_content),
                'trends': self._analyze_trends(document_content) if self.trend_analysis else {},
                'insights': self._generate_insights(document_content) if self.insights_generation else {},
                'data_quality': self._assess_data_quality(document_content),
                'metadata': {
                    'analysis_date': datetime.now().isoformat(),
                    'confidence_score': classification.get('confidence', 0.0),
                    'document_complexity': self._assess_complexity(document_content)
                }
            }
            
            self.log_info("Report analysis completed successfully")
            return analysis
            
        except Exception as e:
            error_msg = f"Report analysis failed: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg}
    
    def _extract_metrics(self, content: str) -> Dict[str, Any]:
        """Extract numerical metrics and KPIs from the report."""
        metrics = {}
        
        # Look for percentage patterns
        percentage_pattern = r'([0-9.]+)%'
        percentages = re.findall(percentage_pattern, content)
        
        # Look for monetary amounts
        money_pattern = r'\$([0-9,]+(?:\.[0-9]{2})?)'
        amounts = re.findall(money_pattern, content)
        
        # Look for large numbers (potential metrics)
        number_pattern = r'\b([0-9,]+)\b'
        numbers = re.findall(number_pattern, content)
        
        # Clean and analyze numbers
        clean_numbers = []
        for num in numbers:
            try:
                clean_num = int(num.replace(',', ''))
                if clean_num > 10:  # Filter out small numbers
                    clean_numbers.append(clean_num)
            except ValueError:
                continue
        
        return {
            'percentages': percentages[:10],
            'monetary_amounts': amounts[:10],
            'large_numbers': clean_numbers[:20],
            'metrics_count': len(percentages) + len(amounts) + len(clean_numbers),
            'data_richness': 'high' if len(percentages) + len(amounts) > 5 else 'low'
        }
    
    def _analyze_structure(self, content: str) -> Dict[str, Any]:
        """Analyze the document structure and organization."""
        lines = content.split('\n')
        
        # Count sections (lines that might be headers)
        potential_headers = []
        for line in lines:
            line = line.strip()
            if line.isupper() and len(line) > 3 and len(line) < 50:
                potential_headers.append(line)
            elif re.match(r'^\d+\.', line):  # Numbered sections
                potential_headers.append(line[:50])
        
        # Analyze document length and complexity
        word_count = len(content.split())
        line_count = len([l for l in lines if l.strip()])
        
        return {
            'word_count': word_count,
            'line_count': line_count,
            'potential_sections': potential_headers[:10],
            'section_count': len(potential_headers),
            'document_length': 'long' if word_count > 1000 else 'medium' if word_count > 300 else 'short',
            'structure_complexity': 'complex' if len(potential_headers) > 5 else 'simple'
        }
    
    def _identify_themes(self, content: str) -> Dict[str, Any]:
        """Identify key themes and topics in the report."""
        content_lower = content.lower()
        
        # Business theme keywords
        business_themes = {
            'financial': ['revenue', 'profit', 'cost', 'budget', 'financial', 'income', 'expense'],
            'performance': ['performance', 'kpi', 'metric', 'result', 'achievement', 'goal'],
            'growth': ['growth', 'increase', 'expansion', 'scale', 'develop', 'improve'],
            'market': ['market', 'customer', 'client', 'competitive', 'industry', 'segment'],
            'operational': ['operational', 'process', 'efficiency', 'productivity', 'workflow'],
            'strategic': ['strategy', 'strategic', 'planning', 'vision', 'mission', 'objective'],
            'risk': ['risk', 'challenge', 'threat', 'issue', 'problem', 'concern'],
            'technology': ['technology', 'software', 'system', 'digital', 'automation', 'innovation']
        }
        
        theme_scores = {}
        for theme, keywords in business_themes.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                theme_scores[theme] = score
        
        # Find dominant themes
        if theme_scores:
            max_score = max(theme_scores.values())
            dominant_themes = [theme for theme, score in theme_scores.items() if score >= max_score * 0.7]
        else:
            dominant_themes = []
        
        return {
            'theme_scores': theme_scores,
            'dominant_themes': dominant_themes,
            'theme_diversity': len(theme_scores),
            'primary_focus': dominant_themes[0] if dominant_themes else 'unclear'
        }
    
    def _analyze_trends(self, content: str) -> Dict[str, Any]:
        """Analyze trend indicators in the report."""
        content_lower = content.lower()
        
        # Trend indicator words
        positive_trends = ['increase', 'growth', 'improve', 'rise', 'up', 'higher', 'gain', 'expand']
        negative_trends = ['decrease', 'decline', 'drop', 'fall', 'down', 'lower', 'loss', 'reduce']
        stable_trends = ['stable', 'consistent', 'maintain', 'steady', 'constant', 'unchanged']
        
        trend_indicators = {
            'positive': sum(1 for word in positive_trends if word in content_lower),
            'negative': sum(1 for word in negative_trends if word in content_lower),
            'stable': sum(1 for word in stable_trends if word in content_lower)
        }
        
        # Determine overall trend sentiment
        total_indicators = sum(trend_indicators.values())
        if total_indicators > 0:
            dominant_trend = max(trend_indicators, key=trend_indicators.get)
            trend_strength = trend_indicators[dominant_trend] / total_indicators
        else:
            dominant_trend = 'unclear'
            trend_strength = 0
        
        # Look for time-based references
        time_pattern = r'\b(201\d|202\d|Q[1-4]|quarter|month|year|weekly|daily)\b'
        time_references = re.findall(time_pattern, content, re.IGNORECASE)
        
        return {
            'trend_indicators': trend_indicators,
            'dominant_trend': dominant_trend,
            'trend_strength': round(trend_strength, 2),
            'time_references': list(set(time_references))[:10],
            'temporal_analysis': len(time_references) > 3
        }
    
    def _generate_insights(self, content: str) -> Dict[str, Any]:
        """Generate analytical insights from the report content."""
        insights = []
        
        # Analyze content characteristics
        word_count = len(content.split())
        
        # Check for data density
        numbers_count = len(re.findall(r'\d+', content))
        data_density = numbers_count / word_count if word_count > 0 else 0
        
        if data_density > 0.1:
            insights.append("Report is data-rich with significant quantitative content")
        elif data_density < 0.02:
            insights.append("Report is primarily narrative with limited quantitative data")
        
        # Check for conclusion indicators
        content_lower = content.lower()
        if 'conclusion' in content_lower or 'summary' in content_lower:
            insights.append("Report includes explicit conclusions or summary")
        
        # Check for future-looking content
        future_words = ['future', 'plan', 'forecast', 'predict', 'expect', 'project']
        if any(word in content_lower for word in future_words):
            insights.append("Report contains forward-looking statements or projections")
        
        # Check for action items
        action_words = ['recommend', 'should', 'action', 'implement', 'execute']
        if any(word in content_lower for word in action_words):
            insights.append("Report includes recommendations or action items")
        
        return {
            'key_insights': insights,
            'data_density': round(data_density, 3),
            'insight_count': len(insights),
            'analytical_depth': 'deep' if len(insights) > 2 else 'shallow'
        }
    
    def _assess_data_quality(self, content: str) -> Dict[str, Any]:
        """Assess the quality and reliability of data in the report."""
        quality_indicators = {}
        
        content_lower = content.lower()
        
        # Check for source citations
        source_indicators = ['source:', 'data from', 'according to', 'based on', 'reference']
        quality_indicators['has_sources'] = any(indicator in content_lower for indicator in source_indicators)
        
        # Check for dates and timeliness
        current_year = datetime.now().year
        years_mentioned = re.findall(r'\b(20\d{2})\b', content)
        recent_data = any(int(year) >= current_year - 2 for year in years_mentioned if year.isdigit())
        quality_indicators['recent_data'] = recent_data
        
        # Check for specific metrics vs vague language
        vague_words = ['approximately', 'roughly', 'around', 'about', 'estimate']
        vague_count = sum(1 for word in vague_words if word in content_lower)
        quality_indicators['precision_level'] = 'low' if vague_count > 5 else 'medium' if vague_count > 2 else 'high'
        
        # Overall quality score
        quality_score = 0
        if quality_indicators['has_sources']:
            quality_score += 0.4
        if quality_indicators['recent_data']:
            quality_score += 0.3
        if quality_indicators['precision_level'] == 'high':
            quality_score += 0.3
        elif quality_indicators['precision_level'] == 'medium':
            quality_score += 0.15
        
        quality_indicators['overall_quality_score'] = round(quality_score, 2)
        quality_indicators['quality_rating'] = 'high' if quality_score > 0.7 else 'medium' if quality_score > 0.4 else 'low'
        
        return quality_indicators
    
    def _assess_complexity(self, content: str) -> str:
        """Assess the complexity level of the report."""
        word_count = len(content.split())
        technical_terms = len(re.findall(r'\b[A-Z]{2,}\b', content))  # Acronyms/technical terms
        numbers_count = len(re.findall(r'\d+', content))
        
        complexity_score = 0
        if word_count > 1000:
            complexity_score += 1
        if technical_terms > 10:
            complexity_score += 1
        if numbers_count > 20:
            complexity_score += 1
        
        if complexity_score >= 2:
            return 'high'
        elif complexity_score == 1:
            return 'medium'
        else:
            return 'low'


# Register the agent for use in workflows
def create_report_analyzer_agent(name: str, prompt: str, context: Dict[str, Any] = None, **kwargs) -> ReportAnalyzerAgent:
    """Factory function to create ReportAnalyzerAgent instances."""
    return ReportAnalyzerAgent(name, prompt, context, **kwargs)


# Export for AgentMap registration
__all__ = ['ReportAnalyzerAgent', 'create_report_analyzer_agent']
