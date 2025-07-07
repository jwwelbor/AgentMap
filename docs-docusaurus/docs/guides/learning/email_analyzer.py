"""
Email Analyzer Agent

Specialized agent for analyzing email communications and correspondence.
Performs sentiment analysis, extracts action items, and detects priority.
"""

from agentmap.agents.base_agent import BaseAgent
from typing import Dict, Any, List
import re
from datetime import datetime


class EmailAnalyzerAgent(BaseAgent):
    """
    Specialized agent for email and communication analysis.
    
    Analyzes emails for:
    - Sentiment and tone
    - Action items and tasks
    - Priority detection
    - Communication patterns
    - Response requirements
    """
    
    def __init__(self, name: str, prompt: str, context: Dict[str, Any] = None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        
        self.sentiment_analysis = self.context.get('sentiment_analysis', True)
        self.action_items = self.context.get('action_items', True)
        self.priority_detection = self.context.get('priority_detection', True)
        
        self.log_info(f"EmailAnalyzer initialized with sentiment_analysis: {self.sentiment_analysis}")
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Analyze email content for sentiment, action items, and priority.
        
        Args:
            inputs: Contains document_content and classification_result
            
        Returns:
            Dict: Comprehensive email analysis
        """
        try:
            document_content = inputs.get('document_content', '')
            classification = inputs.get('classification_result', {})
            
            if not document_content:
                return {"error": "No document content provided for email analysis"}
            
            self.log_info("Starting email analysis")
            
            analysis = {
                'document_type': 'email_communication',
                'sentiment': self._analyze_sentiment(document_content) if self.sentiment_analysis else {},
                'action_items': self._extract_action_items(document_content) if self.action_items else {},
                'priority': self._detect_priority(document_content) if self.priority_detection else {},
                'communication_style': self._analyze_communication_style(document_content),
                'participants': self._extract_participants(document_content),
                'response_requirements': self._analyze_response_requirements(document_content),
                'email_structure': self._analyze_email_structure(document_content),
                'metadata': {
                    'analysis_date': datetime.now().isoformat(),
                    'confidence_score': classification.get('confidence', 0.0),
                    'message_length': len(document_content.split())
                }
            }
            
            self.log_info("Email analysis completed successfully")
            return analysis
            
        except Exception as e:
            error_msg = f"Email analysis failed: {str(e)}"
            self.log_error(error_msg)
            return {"error": error_msg}
    
    def _analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """Analyze the sentiment and emotional tone of the email."""
        content_lower = content.lower()
        
        # Positive sentiment indicators
        positive_words = [
            'thank', 'thanks', 'appreciate', 'great', 'excellent', 'good', 'pleased',
            'happy', 'excited', 'wonderful', 'amazing', 'fantastic', 'love', 'like',
            'positive', 'successful', 'achievement', 'congratulations', 'well done'
        ]
        
        # Negative sentiment indicators
        negative_words = [
            'sorry', 'apologize', 'problem', 'issue', 'concern', 'worried', 'upset',
            'disappointed', 'frustrated', 'angry', 'terrible', 'awful', 'bad',
            'wrong', 'error', 'mistake', 'failure', 'urgent', 'emergency'
        ]
        
        # Neutral/professional indicators
        neutral_words = [
            'regarding', 'concerning', 'please', 'request', 'follow up', 'update',
            'information', 'meeting', 'schedule', 'confirm', 'review', 'discuss'
        ]
        
        # Count sentiment indicators
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        neutral_count = sum(1 for word in neutral_words if word in content_lower)
        
        total_sentiment_words = positive_count + negative_count + neutral_count
        
        # Determine overall sentiment
        if total_sentiment_words == 0:
            sentiment = 'neutral'
            confidence = 0.3
        elif positive_count > negative_count and positive_count > neutral_count:
            sentiment = 'positive'
            confidence = positive_count / total_sentiment_words
        elif negative_count > positive_count and negative_count > neutral_count:
            sentiment = 'negative'
            confidence = negative_count / total_sentiment_words
        else:
            sentiment = 'neutral'
            confidence = neutral_count / total_sentiment_words if neutral_count > 0 else 0.5
        
        return {
            'overall_sentiment': sentiment,
            'confidence': round(confidence, 2),
            'positive_indicators': positive_count,
            'negative_indicators': negative_count,
            'neutral_indicators': neutral_count,
            'sentiment_strength': 'strong' if confidence > 0.6 else 'moderate' if confidence > 0.3 else 'weak'
        }
    
    def _extract_action_items(self, content: str) -> Dict[str, Any]:
        """Extract action items and tasks from the email."""
        action_items = []
        
        content_lower = content.lower()
        lines = content.split('\n')
        
        # Action item indicators
        action_patterns = [
            r'please\s+(\w+(?:\s+\w+){0,10})',
            r'could you\s+(\w+(?:\s+\w+){0,10})',
            r'can you\s+(\w+(?:\s+\w+){0,10})',
            r'need to\s+(\w+(?:\s+\w+){0,10})',
            r'should\s+(\w+(?:\s+\w+){0,10})',
            r'action:\s*(\w+(?:\s+\w+){0,15})',
            r'todo:\s*(\w+(?:\s+\w+){0,15})',
            r'follow up\s+(\w+(?:\s+\w+){0,10})'
        ]
        
        for pattern in action_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if len(match.strip()) > 5:  # Filter out very short matches
                    action_items.append(match.strip())
        
        # Look for bullet points or numbered lists (potential action items)
        for line in lines:
            line = line.strip()
            if re.match(r'^[-*•]\s+', line) or re.match(r'^\d+\.\s+', line):
                clean_line = re.sub(r'^[-*•\d\.]\s*', '', line)
                if len(clean_line) > 10 and any(word in clean_line.lower() for word in ['please', 'need', 'should', 'must']):
                    action_items.append(clean_line[:100])  # Truncate for safety
        
        # Detect urgency levels
        urgent_keywords = ['urgent', 'asap', 'immediately', 'emergency', 'critical']
        urgent_actions = [item for item in action_items if any(keyword in item.lower() for keyword in urgent_keywords)]
        
        return {
            'action_items': action_items[:10],  # Limit to prevent overflow
            'action_count': len(action_items),
            'urgent_actions': urgent_actions,
            'has_deadlines': bool(re.search(r'\bby\s+\w+|\bdue\s+\w+|\bdeadline', content, re.IGNORECASE)),
            'requires_action': len(action_items) > 0
        }
    
    def _detect_priority(self, content: str) -> Dict[str, Any]:
        """Detect the priority level of the email."""
        content_lower = content.lower()
        
        # High priority indicators
        high_priority_words = [
            'urgent', 'asap', 'emergency', 'critical', 'immediate', 'priority',
            'deadline', 'time sensitive', 'important', 'escalation'
        ]
        
        # Medium priority indicators
        medium_priority_words = [
            'soon', 'timely', 'prompt', 'follow up', 'reminder', 'update needed'
        ]
        
        # Low priority indicators
        low_priority_words = [
            'when convenient', 'no rush', 'fyi', 'for your information', 'heads up'
        ]
        
        # Count priority indicators
        high_count = sum(1 for word in high_priority_words if word in content_lower)
        medium_count = sum(1 for word in medium_priority_words if word in content_lower)
        low_count = sum(1 for word in low_priority_words if word in content_lower)
        
        # Determine priority level
        if high_count > 0:
            priority_level = 'high'
            confidence = min(high_count * 0.3, 1.0)
        elif medium_count > 0:
            priority_level = 'medium'
            confidence = min(medium_count * 0.4, 0.8)
        elif low_count > 0:
            priority_level = 'low'
            confidence = min(low_count * 0.5, 0.7)
        else:
            priority_level = 'medium'  # Default
            confidence = 0.3
        
        # Check for deadline mentions
        deadline_pattern = r'\b(?:by|due|deadline|before)\s+(\w+\s+\d+|\d+/\d+|\w+day)'
        deadlines = re.findall(deadline_pattern, content, re.IGNORECASE)
        
        return {
            'priority_level': priority_level,
            'confidence': round(confidence, 2),
            'high_priority_indicators': high_count,
            'medium_priority_indicators': medium_count,
            'low_priority_indicators': low_count,
            'deadlines_mentioned': deadlines[:3],
            'has_deadline': len(deadlines) > 0
        }
    
    def _analyze_communication_style(self, content: str) -> Dict[str, Any]:
        """Analyze the communication style and tone."""
        content_lower = content.lower()
        
        # Formal indicators
        formal_words = ['dear', 'sincerely', 'regards', 'respectfully', 'kindly', 'pursuant']
        formal_count = sum(1 for word in formal_words if word in content_lower)
        
        # Informal indicators
        informal_words = ['hey', 'hi', 'thanks', 'cheers', 'catch up', 'chat']
        informal_count = sum(1 for word in informal_words if word in content_lower)
        
        # Professional indicators
        professional_words = ['regarding', 'concerning', 'follow up', 'update', 'proposal', 'recommendation']
        professional_count = sum(1 for word in professional_words if word in content_lower)
        
        # Determine style
        total_style_indicators = formal_count + informal_count + professional_count
        
        if total_style_indicators == 0:
            style = 'neutral'
        elif formal_count > informal_count:
            style = 'formal'
        elif informal_count > formal_count:
            style = 'informal'
        else:
            style = 'professional'
        
        return {
            'communication_style': style,
            'formal_indicators': formal_count,
            'informal_indicators': informal_count,
            'professional_indicators': professional_count,
            'message_tone': 'conversational' if informal_count > 2 else 'business'
        }
    
    def _extract_participants(self, content: str) -> Dict[str, Any]:
        """Extract email participants and recipients."""
        # Look for email addresses
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        emails = re.findall(email_pattern, content)
        
        # Look for names (simple pattern)
        name_pattern = r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b'
        names = re.findall(name_pattern, content)
        
        # Look for common email headers
        cc_pattern = r'cc:\s*([^\\n]+)'
        cc_matches = re.findall(cc_pattern, content, re.IGNORECASE)
        
        return {
            'email_addresses': list(set(emails))[:10],
            'potential_names': list(set(names))[:10],
            'cc_recipients': cc_matches,
            'participant_count': len(set(emails)) + len(set(names)),
            'multiple_recipients': len(emails) > 1 or len(cc_matches) > 0
        }
    
    def _analyze_response_requirements(self, content: str) -> Dict[str, Any]:
        """Analyze if and how a response is required."""
        content_lower = content.lower()
        
        # Response request indicators
        response_patterns = [
            'please reply', 'let me know', 'get back to me', 'respond',
            'your thoughts', 'what do you think', 'feedback', 'confirmation'
        ]
        
        response_required = any(pattern in content_lower for pattern in response_patterns)
        
        # Question detection
        question_count = content.count('?')
        has_questions = question_count > 0
        
        # Meeting/call requests
        meeting_patterns = ['meet', 'call', 'schedule', 'appointment', 'meeting']
        meeting_request = any(pattern in content_lower for pattern in meeting_patterns)
        
        return {
            'response_required': response_required,
            'has_questions': has_questions,
            'question_count': question_count,
            'meeting_request': meeting_request,
            'response_urgency': 'high' if 'asap' in content_lower or 'urgent' in content_lower else 'normal',
            'response_type': 'meeting' if meeting_request else 'email' if response_required else 'none'
        }
    
    def _analyze_email_structure(self, content: str) -> Dict[str, Any]:
        """Analyze the structure and format of the email."""
        lines = content.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        # Check for signature
        has_signature = any(re.search(r'(best|regards|sincerely|thanks|cheers)', line, re.IGNORECASE) 
                          for line in lines[-5:])
        
        # Check for greeting
        has_greeting = any(re.search(r'(dear|hi|hello|hey)', line, re.IGNORECASE) 
                         for line in lines[:3])
        
        # Check for subject-like content
        potential_subject = lines[0] if lines and len(lines[0]) < 100 else None
        
        return {
            'total_lines': len(lines),
            'content_lines': len(non_empty_lines),
            'has_greeting': has_greeting,
            'has_signature': has_signature,
            'potential_subject': potential_subject,
            'structure_completeness': 'complete' if has_greeting and has_signature else 'partial',
            'format_type': 'formal' if has_greeting and has_signature else 'informal'
        }


# Register the agent for use in workflows
def create_email_analyzer_agent(name: str, prompt: str, context: Dict[str, Any] = None, **kwargs) -> EmailAnalyzerAgent:
    """Factory function to create EmailAnalyzerAgent instances."""
    return EmailAnalyzerAgent(name, prompt, context, **kwargs)


# Export for AgentMap registration
__all__ = ['EmailAnalyzerAgent', 'create_email_analyzer_agent']
