---
sidebar_position: 5
title: Multi-Agent Research System
description: Build a sophisticated multi-agent research system with specialized researcher agents, fact-checking, synthesis, and collaborative intelligence.
keywords: [multi-agent research, collaborative AI, research automation, agent coordination, distributed intelligence, research agents]
---

# Building a Multi-Agent Research System

Learn how to create a sophisticated multi-agent research system where specialized AI agents collaborate to conduct comprehensive research, fact-checking, and knowledge synthesis. This tutorial showcases AgentMap's powerful multi-agent orchestration capabilities.

## System Architecture

Our multi-agent research system consists of several specialized agents working in coordination:

1. **Research Coordinator Agent** - Orchestrates the entire research process
2. **Topic Analysis Agent** - Breaks down research topics into specific questions
3. **Web Research Agent** - Conducts web searches and gathers information
4. **Academic Research Agent** - Searches academic databases and papers
5. **Fact Verification Agent** - Cross-references and validates information
6. **Synthesis Agent** - Combines findings into coherent reports
7. **Quality Assurance Agent** - Reviews and scores research quality
8. **Report Generator Agent** - Creates final formatted research reports

## Core Components

### Research Coordinator Agent

```python
import json
from datetime import datetime
from typing import List, Dict, Any
from agentmap.agents import BaseAgent

class ResearchCoordinatorAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.research_session = {
            'id': None,
            'topic': None,
            'subtopics': [],
            'agents_status': {},
            'findings': [],
            'start_time': None,
            'end_time': None
        }
    
    def execute(self, input_data, context=None):
        """
        Coordinate multi-agent research process
        
        Input: Research topic or query
        Context: research_depth, max_agents, time_limit
        """
        research_topic = input_data
        research_depth = context.get('research_depth', 'medium')  # shallow, medium, deep
        max_agents = context.get('max_agents', 5)
        time_limit = context.get('time_limit_minutes', 30)
        
        # Initialize research session
        self.research_session['id'] = f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.research_session['topic'] = research_topic
        self.research_session['start_time'] = datetime.now().isoformat()
        
        # Generate research plan
        research_plan = self.create_research_plan(research_topic, research_depth)
        
        # Coordinate agent execution
        results = self.execute_research_plan(research_plan, max_agents)
        
        # Finalize session
        self.research_session['end_time'] = datetime.now().isoformat()
        
        return {
            'research_session': self.research_session,
            'research_plan': research_plan,
            'results': results,
            'status': 'completed',
            'total_findings': len(self.research_session['findings'])
        }
    
    def create_research_plan(self, topic: str, depth: str) -> Dict:
        """Create comprehensive research plan"""
        
        # Define research parameters based on depth
        depth_config = {
            'shallow': {
                'subtopics': 3,
                'sources_per_subtopic': 2,
                'fact_check_threshold': 0.7
            },
            'medium': {
                'subtopics': 5,
                'sources_per_subtopic': 4,
                'fact_check_threshold': 0.8
            },
            'deep': {
                'subtopics': 8,
                'sources_per_subtopic': 6,
                'fact_check_threshold': 0.9
            }
        }
        
        config = depth_config[depth]
        
        return {
            'main_topic': topic,
            'research_depth': depth,
            'subtopics_count': config['subtopics'],
            'sources_per_subtopic': config['sources_per_subtopic'],
            'fact_check_threshold': config['fact_check_threshold'],
            'agents_needed': [
                'topic_analysis',
                'web_research',
                'academic_research',
                'fact_verification',
                'synthesis',
                'quality_assurance'
            ]
        }
    
    def execute_research_plan(self, plan: Dict, max_agents: int) -> Dict:
        """Execute the research plan with agent coordination"""
        
        results = {
            'topic_analysis': None,
            'web_research': [],
            'academic_research': [],
            'fact_verification': [],
            'synthesis': None,
            'quality_score': None
        }
        
        # Track agent status
        for agent_type in plan['agents_needed']:
            self.research_session['agents_status'][agent_type] = 'pending'
        
        # Simulate agent coordination (in real implementation, this would use actual agent execution)
        self.log_agent_activity("research_coordinator", f"Starting research on: {plan['main_topic']}")
        
        return results
    
    def log_agent_activity(self, agent_name: str, activity: str):
        """Log agent activities for monitoring"""
        self.research_session['findings'].append({
            'timestamp': datetime.now().isoformat(),
            'agent': agent_name,
            'activity': activity
        })
```

### Topic Analysis Agent

```python
class TopicAnalysisAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.llm_service = self.get_service('llm') if services else None
    
    def execute(self, input_data, context=None):
        """
        Analyze research topic and break it down into specific research questions
        
        Input: Main research topic
        Context: research_depth, domain_expertise
        """
        main_topic = input_data
        research_depth = context.get('research_depth', 'medium')
        domain = context.get('domain_expertise', 'general')
        
        # Generate research questions using LLM
        analysis_prompt = self.create_analysis_prompt(main_topic, research_depth, domain)
        
        if self.llm_service:
            analysis_result = self.llm_service.generate(analysis_prompt)
        else:
            # Fallback to rule-based analysis
            analysis_result = self.rule_based_analysis(main_topic, research_depth)
        
        # Parse and structure the analysis
        structured_analysis = self.parse_analysis_result(analysis_result)
        
        return {
            'main_topic': main_topic,
            'research_questions': structured_analysis['questions'],
            'subtopics': structured_analysis['subtopics'],
            'suggested_sources': structured_analysis['sources'],
            'research_methodology': structured_analysis['methodology'],
            'estimated_complexity': structured_analysis['complexity']
        }
    
    def create_analysis_prompt(self, topic: str, depth: str, domain: str) -> str:
        """Create comprehensive analysis prompt for LLM"""
        return f"""
        Analyze the research topic: "{topic}"
        
        Research depth: {depth}
        Domain expertise: {domain}
        
        Please provide:
        1. 5-8 specific research questions that should be investigated
        2. Key subtopics that need to be explored
        3. Suggested types of sources (academic papers, reports, websites, etc.)
        4. Recommended research methodology
        5. Assessment of research complexity (1-10 scale)
        
        Format your response as structured JSON with the following keys:
        - questions: array of research questions
        - subtopics: array of subtopic strings
        - sources: array of source types
        - methodology: string describing approach
        - complexity: integer from 1-10
        """
    
    def rule_based_analysis(self, topic: str, depth: str) -> str:
        """Fallback rule-based topic analysis"""
        
        # Simple keyword-based analysis
        topic_words = topic.lower().split()
        
        questions = []
        subtopics = []
        
        # Generate basic questions
        question_templates = [
            f"What is {topic}?",
            f"How does {topic} work?",
            f"What are the benefits of {topic}?",
            f"What are the challenges with {topic}?",
            f"What is the future of {topic}?"
        ]
        
        if depth == 'deep':
            question_templates.extend([
                f"What is the history of {topic}?",
                f"How does {topic} compare to alternatives?",
                f"What are the economic implications of {topic}?"
            ])
        
        # Generate subtopics based on common patterns
        if any(word in topic_words for word in ['technology', 'ai', 'machine', 'digital']):
            subtopics.extend(['Technical Implementation', 'Industry Applications', 'Future Trends'])
        elif any(word in topic_words for word in ['policy', 'government', 'law', 'regulation']):
            subtopics.extend(['Legal Framework', 'Policy Implications', 'Stakeholder Impact'])
        else:
            subtopics.extend(['Overview', 'Current State', 'Future Outlook'])
        
        return json.dumps({
            'questions': question_templates[:5 if depth != 'deep' else 8],
            'subtopics': subtopics,
            'sources': ['Academic Papers', 'Industry Reports', 'News Articles', 'Official Websites'],
            'methodology': 'Multi-source research with cross-validation',
            'complexity': 5 if depth == 'medium' else 7
        })
    
    def parse_analysis_result(self, analysis_text: str) -> Dict:
        """Parse LLM analysis result into structured format"""
        try:
            return json.loads(analysis_text)
        except json.JSONDecodeError:
            # Fallback parsing for non-JSON responses
            return {
                'questions': ['What are the key aspects of this topic?'],
                'subtopics': ['Overview', 'Current State', 'Future Trends'],
                'sources': ['Academic Papers', 'Web Sources'],
                'methodology': 'General research approach',
                'complexity': 5
            }
```

### Web Research Agent

```python
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import quote_plus

class WebResearchAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.rate_limit_delay = 1  # seconds between requests
    
    def execute(self, input_data, context=None):
        """
        Conduct web research on specified topics
        
        Input: Research questions or topics list
        Context: max_sources, search_engines, content_types
        """
        research_queries = input_data if isinstance(input_data, list) else [input_data]
        max_sources = context.get('max_sources', 10)
        search_engines = context.get('search_engines', ['google', 'bing'])
        content_types = context.get('content_types', ['articles', 'reports', 'official_sites'])
        
        research_results = []
        
        for query in research_queries:
            query_results = self.research_query(query, max_sources, search_engines, content_types)
            research_results.extend(query_results)
            
            # Rate limiting
            time.sleep(self.rate_limit_delay)
        
        # Deduplicate and rank results
        unique_results = self.deduplicate_results(research_results)
        ranked_results = self.rank_results(unique_results)
        
        return {
            'total_queries': len(research_queries),
            'total_sources_found': len(unique_results),
            'research_results': ranked_results[:max_sources],
            'search_engines_used': search_engines,
            'status': 'completed'
        }
    
    def research_query(self, query: str, max_sources: int, engines: List[str], content_types: List[str]) -> List[Dict]:
        """Research a single query across multiple search engines"""
        
        results = []
        
        for engine in engines:
            try:
                engine_results = self.search_engine_query(query, engine, max_sources // len(engines))
                
                for result in engine_results:
                    # Extract and analyze content
                    content_data = self.extract_content(result['url'])
                    
                    if content_data and self.is_relevant_content(content_data, query, content_types):
                        results.append({
                            'query': query,
                            'title': result['title'],
                            'url': result['url'],
                            'snippet': result['snippet'],
                            'content': content_data['text'][:2000],  # Limit content length
                            'content_type': content_data['type'],
                            'word_count': content_data['word_count'],
                            'search_engine': engine,
                            'relevance_score': self.calculate_relevance(content_data['text'], query),
                            'extracted_at': datetime.now().isoformat()
                        })
            
            except Exception as e:
                self.logger.error(f"Error searching {engine} for '{query}': {str(e)}")
        
        return results
    
    def search_engine_query(self, query: str, engine: str, max_results: int) -> List[Dict]:
        """Query a specific search engine (simplified implementation)"""
        
        # This is a simplified implementation
        # In production, you would use proper search APIs like Google Custom Search API
        
        if engine == 'google':
            return self.google_search_simulation(query, max_results)
        elif engine == 'bing':
            return self.bing_search_simulation(query, max_results)
        else:
            return []
    
    def google_search_simulation(self, query: str, max_results: int) -> List[Dict]:
        """Simulate Google search results"""
        # In real implementation, use Google Custom Search API
        
        return [
            {
                'title': f'Research result for {query}',
                'url': f'https://example.com/article-{i}',
                'snippet': f'This article discusses various aspects of {query} including key findings and analysis.'
            }
            for i in range(min(max_results, 5))
        ]
    
    def bing_search_simulation(self, query: str, max_results: int) -> List[Dict]:
        """Simulate Bing search results"""
        # In real implementation, use Bing Search API
        
        return [
            {
                'title': f'Bing result for {query}',
                'url': f'https://example.org/research-{i}',
                'snippet': f'Comprehensive analysis of {query} with detailed insights and recommendations.'
            }
            for i in range(min(max_results, 5))
        ]
    
    def extract_content(self, url: str) -> Dict:
        """Extract content from a web page"""
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text content
            text = soup.get_text()
            
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Determine content type
            content_type = self.determine_content_type(soup, url)
            
            return {
                'text': text,
                'type': content_type,
                'word_count': len(text.split()),
                'title': soup.title.string if soup.title else '',
                'meta_description': self.get_meta_description(soup)
            }
        
        except Exception as e:
            self.logger.error(f"Error extracting content from {url}: {str(e)}")
            return None
    
    def determine_content_type(self, soup: BeautifulSoup, url: str) -> str:
        """Determine the type of content based on page structure and URL"""
        
        # Check URL patterns
        if any(domain in url for domain in ['arxiv.org', 'ieee.org', 'acm.org']):
            return 'academic_paper'
        elif any(domain in url for domain in ['gov', 'edu']):
            return 'official_source'
        elif 'news' in url or 'blog' in url:
            return 'news_article'
        elif 'wikipedia' in url:
            return 'encyclopedia'
        
        # Check page structure
        if soup.find('meta', {'name': 'citation_title'}):
            return 'academic_paper'
        elif len(soup.find_all('p')) > 10:
            return 'article'
        else:
            return 'webpage'
    
    def get_meta_description(self, soup: BeautifulSoup) -> str:
        """Extract meta description from page"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        return meta_desc.get('content', '') if meta_desc else ''
    
    def is_relevant_content(self, content_data: Dict, query: str, content_types: List[str]) -> bool:
        """Check if content is relevant to the query and desired content types"""
        
        # Check content type filter
        if content_data['type'] not in content_types and 'all' not in content_types:
            return False
        
        # Check minimum content length
        if content_data['word_count'] < 100:
            return False
        
        # Check query relevance (simple keyword matching)
        query_words = set(query.lower().split())
        content_words = set(content_data['text'].lower().split())
        
        overlap = len(query_words.intersection(content_words))
        relevance = overlap / len(query_words) if query_words else 0
        
        return relevance > 0.2  # At least 20% keyword overlap
    
    def calculate_relevance(self, content: str, query: str) -> float:
        """Calculate relevance score between content and query"""
        
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        # Calculate different relevance metrics
        keyword_overlap = len(query_words.intersection(content_words)) / len(query_words)
        
        # Simple TF-IDF-like scoring
        query_frequency = sum(1 for word in content.lower().split() if word in query_words)
        tf_score = query_frequency / len(content.split()) if content else 0
        
        # Combine scores
        relevance_score = (keyword_overlap * 0.6) + (tf_score * 0.4)
        
        return min(relevance_score, 1.0)
    
    def deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate results based on URL and content similarity"""
        
        unique_results = []
        seen_urls = set()
        
        for result in results:
            if result['url'] not in seen_urls:
                unique_results.append(result)
                seen_urls.add(result['url'])
        
        return unique_results
    
    def rank_results(self, results: List[Dict]) -> List[Dict]:
        """Rank results by relevance and quality indicators"""
        
        return sorted(results, key=lambda x: (
            x['relevance_score'],
            x['word_count'],
            1 if x['content_type'] in ['academic_paper', 'official_source'] else 0
        ), reverse=True)
```

### Fact Verification Agent

```python
class FactVerificationAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.verification_sources = [
            'fact_checking_sites',
            'academic_databases', 
            'official_sources',
            'cross_reference_check'
        ]
    
    def execute(self, input_data, context=None):
        """
        Verify facts and claims from research findings
        
        Input: Research findings with claims to verify
        Context: verification_threshold, trusted_sources
        """
        research_findings = input_data
        verification_threshold = context.get('verification_threshold', 0.8)
        trusted_sources = context.get('trusted_sources', [])
        
        verification_results = []
        
        for finding in research_findings:
            claims = self.extract_claims(finding)
            
            for claim in claims:
                verification_result = self.verify_claim(claim, trusted_sources)
                verification_results.append({
                    'claim': claim,
                    'source_finding': finding['title'],
                    'verification_score': verification_result['score'],
                    'verification_status': self.determine_status(verification_result['score'], verification_threshold),
                    'supporting_sources': verification_result['supporting_sources'],
                    'conflicting_sources': verification_result['conflicting_sources'],
                    'confidence_level': verification_result['confidence']
                })
        
        # Calculate overall verification metrics
        total_claims = len(verification_results)
        verified_claims = len([r for r in verification_results if r['verification_status'] == 'verified'])
        disputed_claims = len([r for r in verification_results if r['verification_status'] == 'disputed'])
        
        return {
            'total_claims_checked': total_claims,
            'verified_claims': verified_claims,
            'disputed_claims': disputed_claims,
            'unverified_claims': total_claims - verified_claims - disputed_claims,
            'overall_reliability_score': verified_claims / total_claims if total_claims > 0 else 0,
            'verification_details': verification_results
        }
    
    def extract_claims(self, finding: Dict) -> List[str]:
        """Extract verifiable claims from research finding"""
        
        content = finding.get('content', '')
        
        # Simple claim extraction based on sentence patterns
        sentences = content.split('.')
        claims = []
        
        # Look for factual statements
        claim_indicators = [
            'according to', 'research shows', 'studies indicate', 
            'data reveals', 'evidence suggests', 'experts believe',
            'statistics show', 'reports indicate'
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:  # Minimum length for a claim
                if any(indicator in sentence.lower() for indicator in claim_indicators):
                    claims.append(sentence)
                elif sentence.endswith(('percent', '%', 'million', 'billion', 'thousand')):
                    claims.append(sentence)  # Numerical claims
        
        return claims[:5]  # Limit to 5 claims per finding
    
    def verify_claim(self, claim: str, trusted_sources: List[str]) -> Dict:
        """Verify a specific claim against multiple sources"""
        
        verification_result = {
            'score': 0.0,
            'supporting_sources': [],
            'conflicting_sources': [],
            'confidence': 'low'
        }
        
        # Simulate fact-checking process
        # In real implementation, this would query actual fact-checking APIs and databases
        
        # Extract key elements from claim
        claim_keywords = self.extract_claim_keywords(claim)
        
        # Check against different verification sources
        for source_type in self.verification_sources:
            source_result = self.check_verification_source(claim, claim_keywords, source_type)
            
            if source_result['supports_claim']:
                verification_result['supporting_sources'].append({
                    'source_type': source_type,
                    'confidence': source_result['confidence'],
                    'details': source_result['details']
                })
            elif source_result['contradicts_claim']:
                verification_result['conflicting_sources'].append({
                    'source_type': source_type,
                    'confidence': source_result['confidence'],
                    'details': source_result['details']
                })
        
        # Calculate verification score
        supporting_weight = sum(s['confidence'] for s in verification_result['supporting_sources'])
        conflicting_weight = sum(s['confidence'] for s in verification_result['conflicting_sources'])
        total_weight = supporting_weight + conflicting_weight
        
        if total_weight > 0:
            verification_result['score'] = supporting_weight / total_weight
        
        # Determine confidence level
        if len(verification_result['supporting_sources']) >= 3:
            verification_result['confidence'] = 'high'
        elif len(verification_result['supporting_sources']) >= 2:
            verification_result['confidence'] = 'medium'
        
        return verification_result
    
    def extract_claim_keywords(self, claim: str) -> List[str]:
        """Extract key terms from a claim for verification"""
        
        # Simple keyword extraction
        words = claim.lower().split()
        
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        return keywords[:10]  # Limit to 10 keywords
    
    def check_verification_source(self, claim: str, keywords: List[str], source_type: str) -> Dict:
        """Check claim against a specific verification source"""
        
        # Simulate verification source checking
        # In real implementation, this would connect to actual APIs and databases
        
        if source_type == 'fact_checking_sites':
            return self.simulate_fact_checker_result(claim, keywords)
        elif source_type == 'academic_databases':
            return self.simulate_academic_verification(claim, keywords)
        elif source_type == 'official_sources':
            return self.simulate_official_source_check(claim, keywords)
        elif source_type == 'cross_reference_check':
            return self.simulate_cross_reference(claim, keywords)
        
        return {'supports_claim': False, 'contradicts_claim': False, 'confidence': 0.0, 'details': ''}
    
    def simulate_fact_checker_result(self, claim: str, keywords: List[str]) -> Dict:
        """Simulate fact-checking website results"""
        
        # Simulate based on claim characteristics
        if any(word in claim.lower() for word in ['statistics', 'percent', 'study', 'research']):
            return {
                'supports_claim': True,
                'contradicts_claim': False,
                'confidence': 0.8,
                'details': 'Fact-checking sites confirm statistical claims'
            }
        
        return {
            'supports_claim': False,
            'contradicts_claim': False,
            'confidence': 0.5,
            'details': 'No specific fact-check found'
        }
    
    def simulate_academic_verification(self, claim: str, keywords: List[str]) -> Dict:
        """Simulate academic database verification"""
        
        if len(keywords) >= 3:
            return {
                'supports_claim': True,
                'contradicts_claim': False,
                'confidence': 0.9,
                'details': 'Multiple academic sources support claim'
            }
        
        return {
            'supports_claim': False,
            'contradicts_claim': False,
            'confidence': 0.3,
            'details': 'Limited academic evidence'
        }
    
    def simulate_official_source_check(self, claim: str, keywords: List[str]) -> Dict:
        """Simulate official source verification"""
        
        if any(word in claim.lower() for word in ['government', 'official', 'policy', 'law']):
            return {
                'supports_claim': True,
                'contradicts_claim': False,
                'confidence': 0.95,
                'details': 'Official government sources confirm'
            }
        
        return {
            'supports_claim': False,
            'contradicts_claim': False,
            'confidence': 0.4,
            'details': 'No official source confirmation'
        }
    
    def simulate_cross_reference(self, claim: str, keywords: List[str]) -> Dict:
        """Simulate cross-reference verification"""
        
        return {
            'supports_claim': True,
            'contradicts_claim': False,
            'confidence': 0.7,
            'details': 'Cross-referenced across multiple sources'
        }
    
    def determine_status(self, score: float, threshold: float) -> str:
        """Determine verification status based on score and threshold"""
        
        if score >= threshold:
            return 'verified'
        elif score <= (1 - threshold):
            return 'disputed'
        else:
            return 'unverified'
```

### Research Synthesis Agent

```python
class ResearchSynthesisAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.llm_service = self.get_service('llm') if services else None
    
    def execute(self, input_data, context=None):
        """
        Synthesize research findings into coherent analysis
        
        Input: Verified research findings and fact-check results
        Context: synthesis_style, target_audience, output_format
        """
        research_data = input_data
        synthesis_style = context.get('synthesis_style', 'comprehensive')  # comprehensive, summary, analytical
        target_audience = context.get('target_audience', 'general')  # general, academic, business
        output_format = context.get('output_format', 'report')  # report, summary, presentation
        
        # Organize research findings
        organized_data = self.organize_research_data(research_data)
        
        # Generate synthesis
        synthesis_result = self.generate_synthesis(organized_data, synthesis_style, target_audience)
        
        # Format output
        formatted_output = self.format_synthesis_output(synthesis_result, output_format)
        
        # Generate metadata
        metadata = self.generate_synthesis_metadata(research_data, synthesis_result)
        
        return {
            'synthesis_content': formatted_output,
            'synthesis_metadata': metadata,
            'source_summary': organized_data['source_summary'],
            'confidence_assessment': organized_data['confidence_assessment'],
            'recommendations': synthesis_result.get('recommendations', []),
            'knowledge_gaps': synthesis_result.get('knowledge_gaps', [])
        }
    
    def organize_research_data(self, research_data: Dict) -> Dict:
        """Organize research findings by topic and reliability"""
        
        web_research = research_data.get('web_research', {}).get('research_results', [])
        fact_verification = research_data.get('fact_verification', {}).get('verification_details', [])
        
        # Group findings by topic/theme
        topic_groups = {}
        verified_facts = []
        disputed_facts = []
        
        # Process fact verification results
        for verification in fact_verification:
            if verification['verification_status'] == 'verified':
                verified_facts.append(verification)
            elif verification['verification_status'] == 'disputed':
                disputed_facts.append(verification)
        
        # Group web research by relevance and content type
        high_quality_sources = []
        supporting_sources = []
        
        for result in web_research:
            if result.get('relevance_score', 0) > 0.7:
                high_quality_sources.append(result)
            else:
                supporting_sources.append(result)
        
        # Calculate confidence assessment
        total_sources = len(web_research)
        verified_claims = len(verified_facts)
        disputed_claims = len(disputed_facts)
        
        confidence_score = (verified_claims / (verified_claims + disputed_claims)) if (verified_claims + disputed_claims) > 0 else 0.5
        
        return {
            'high_quality_sources': high_quality_sources,
            'supporting_sources': supporting_sources,
            'verified_facts': verified_facts,
            'disputed_facts': disputed_facts,
            'source_summary': {
                'total_sources': total_sources,
                'high_quality_count': len(high_quality_sources),
                'verified_claims': verified_claims,
                'disputed_claims': disputed_claims
            },
            'confidence_assessment': {
                'overall_confidence': confidence_score,
                'source_quality': 'high' if len(high_quality_sources) > 5 else 'medium',
                'fact_verification_rate': verified_claims / total_sources if total_sources > 0 else 0
            }
        }
    
    def generate_synthesis(self, organized_data: Dict, style: str, audience: str) -> Dict:
        """Generate synthesized analysis from organized research data"""
        
        if self.llm_service:
            return self.llm_based_synthesis(organized_data, style, audience)
        else:
            return self.template_based_synthesis(organized_data, style, audience)
    
    def llm_based_synthesis(self, data: Dict, style: str, audience: str) -> Dict:
        """Generate synthesis using LLM"""
        
        synthesis_prompt = self.create_synthesis_prompt(data, style, audience)
        
        synthesis_text = self.llm_service.generate(synthesis_prompt)
        
        # Parse synthesis result
        return self.parse_synthesis_result(synthesis_text)
    
    def create_synthesis_prompt(self, data: Dict, style: str, audience: str) -> str:
        """Create comprehensive synthesis prompt"""
        
        high_quality_sources = data['high_quality_sources']
        verified_facts = data['verified_facts']
        confidence_assessment = data['confidence_assessment']
        
        sources_text = "\n".join([
            f"- {source['title']}: {source['snippet']}"
            for source in high_quality_sources[:10]
        ])
        
        verified_facts_text = "\n".join([
            f"- {fact['claim']} (Confidence: {fact['confidence_level']})"
            for fact in verified_facts[:10]
        ])
        
        style_instructions = {
            'comprehensive': 'Provide a detailed, thorough analysis covering all aspects',
            'summary': 'Create a concise overview highlighting key points',
            'analytical': 'Focus on critical analysis, implications, and insights'
        }
        
        audience_instructions = {
            'general': 'Use clear, accessible language for general readers',
            'academic': 'Use scholarly tone with rigorous analysis',
            'business': 'Focus on practical implications and actionable insights'
        }
        
        return f"""
        Based on the research findings below, create a {style} synthesis for a {audience} audience.
        
        High-Quality Sources:
        {sources_text}
        
        Verified Facts:
        {verified_facts_text}
        
        Research Confidence: {confidence_assessment['overall_confidence']:.2f}
        
        Style: {style_instructions.get(style, '')}
        Audience: {audience_instructions.get(audience, '')}
        
        Please provide:
        1. Executive Summary (2-3 paragraphs)
        2. Key Findings (5-8 bullet points)
        3. Analysis and Implications
        4. Recommendations (3-5 actionable items)
        5. Knowledge Gaps (areas needing more research)
        6. Conclusion
        
        Format as structured text with clear headings.
        """
    
    def template_based_synthesis(self, data: Dict, style: str, audience: str) -> Dict:
        """Generate synthesis using template-based approach"""
        
        high_quality_sources = data['high_quality_sources']
        verified_facts = data['verified_facts']
        confidence = data['confidence_assessment']
        
        # Generate executive summary
        executive_summary = f"""
        Based on analysis of {len(high_quality_sources)} high-quality sources and verification of {len(verified_facts)} factual claims, 
        this research synthesis provides insights into the examined topic. The research demonstrates a confidence level of 
        {confidence['overall_confidence']:.1%} based on source quality and fact verification results.
        """
        
        # Generate key findings
        key_findings = []
        for source in high_quality_sources[:5]:
            key_findings.append(f"Research indicates: {source['snippet'][:100]}...")
        
        for fact in verified_facts[:3]:
            key_findings.append(f"Verified: {fact['claim'][:100]}...")
        
        # Generate recommendations
        recommendations = [
            "Continue monitoring developments in this area",
            "Seek additional verification for disputed claims",
            "Focus on high-confidence findings for decision making"
        ]
        
        if confidence['overall_confidence'] < 0.7:
            recommendations.append("Conduct additional research to improve confidence levels")
        
        # Identify knowledge gaps
        knowledge_gaps = []
        if len(high_quality_sources) < 5:
            knowledge_gaps.append("Limited high-quality sources available")
        
        if len(verified_facts) < len(data['verified_facts']) + len(data['disputed_facts']) * 0.8:
            knowledge_gaps.append("Significant number of unverified claims")
        
        return {
            'executive_summary': executive_summary,
            'key_findings': key_findings,
            'analysis': "Analysis reveals mixed evidence quality requiring careful interpretation of findings.",
            'recommendations': recommendations,
            'knowledge_gaps': knowledge_gaps,
            'conclusion': f"Research provides {confidence['source_quality']} quality insights with moderate to high confidence levels."
        }
    
    def parse_synthesis_result(self, synthesis_text: str) -> Dict:
        """Parse LLM synthesis result into structured format"""
        
        # Simple parsing - in production, use more sophisticated NLP
        sections = synthesis_text.split('\n\n')
        
        return {
            'executive_summary': sections[0] if sections else '',
            'key_findings': [],
            'analysis': synthesis_text,
            'recommendations': [],
            'knowledge_gaps': [],
            'conclusion': sections[-1] if len(sections) > 1 else ''
        }
    
    def format_synthesis_output(self, synthesis: Dict, format_type: str) -> str:
        """Format synthesis according to specified output format"""
        
        if format_type == 'report':
            return self.format_as_report(synthesis)
        elif format_type == 'summary':
            return self.format_as_summary(synthesis)
        elif format_type == 'presentation':
            return self.format_as_presentation(synthesis)
        
        return str(synthesis)
    
    def format_as_report(self, synthesis: Dict) -> str:
        """Format synthesis as comprehensive report"""
        
        report = f"""
# Research Synthesis Report

## Executive Summary
{synthesis.get('executive_summary', '')}

## Key Findings
"""
        
        for i, finding in enumerate(synthesis.get('key_findings', []), 1):
            report += f"{i}. {finding}\n"
        
        report += f"""
## Analysis and Implications
{synthesis.get('analysis', '')}

## Recommendations
"""
        
        for i, rec in enumerate(synthesis.get('recommendations', []), 1):
            report += f"{i}. {rec}\n"
        
        if synthesis.get('knowledge_gaps'):
            report += "\n## Knowledge Gaps\n"
            for gap in synthesis['knowledge_gaps']:
                report += f"- {gap}\n"
        
        report += f"""
## Conclusion
{synthesis.get('conclusion', '')}
"""
        
        return report
    
    def format_as_summary(self, synthesis: Dict) -> str:
        """Format synthesis as concise summary"""
        
        summary = f"""
**Research Summary**

{synthesis.get('executive_summary', '')}

**Key Points:**
"""
        
        for finding in synthesis.get('key_findings', [])[:3]:
            summary += f"• {finding}\n"
        
        if synthesis.get('recommendations'):
            summary += f"\n**Recommendations:** {'; '.join(synthesis['recommendations'][:3])}"
        
        return summary
    
    def format_as_presentation(self, synthesis: Dict) -> str:
        """Format synthesis for presentation"""
        
        presentation = f"""
# Research Findings Presentation

## Slide 1: Overview
{synthesis.get('executive_summary', '')}

## Slide 2: Key Findings
"""
        
        for finding in synthesis.get('key_findings', [])[:5]:
            presentation += f"• {finding}\n"
        
        presentation += """
## Slide 3: Recommendations
"""
        
        for rec in synthesis.get('recommendations', []):
            presentation += f"• {rec}\n"
        
        return presentation
    
    def generate_synthesis_metadata(self, research_data: Dict, synthesis: Dict) -> Dict:
        """Generate metadata about the synthesis process"""
        
        return {
            'synthesis_date': datetime.now().isoformat(),
            'sources_analyzed': len(research_data.get('web_research', {}).get('research_results', [])),
            'facts_verified': len(research_data.get('fact_verification', {}).get('verification_details', [])),
            'confidence_level': research_data.get('fact_verification', {}).get('overall_reliability_score', 0.5),
            'synthesis_length': len(str(synthesis)),
            'processing_time': 'simulated',
            'quality_indicators': {
                'source_diversity': 'medium',
                'fact_verification_rate': 0.8,
                'synthesis_completeness': 'high'
            }
        }
```

## CSV Workflow Configuration

### Complete Multi-Agent Research Workflow

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
MultiAgentResearch,InitializeResearch,,Initialize research coordination,research_coordinator,AnalyzeTopic,ErrorHandler,collection,research_plan,
MultiAgentResearch,AnalyzeTopic,,"{'research_depth': 'medium', 'domain_expertise': 'general'}",topic_analysis,ConductWebResearch,ErrorHandler,research_plan,topic_analysis_result,
MultiAgentResearch,ConductWebResearch,,"{'max_sources': 15, 'search_engines': ['google', 'bing'], 'content_types': ['articles', 'reports']}",web_research,ConductAcademicResearch,ErrorHandler,topic_analysis_result,web_research_result,
MultiAgentResearch,ConductAcademicResearch,,"{'databases': ['pubmed', 'arxiv'], 'max_papers': 10}",academic_research,VerifyFacts,ErrorHandler,topic_analysis_result,academic_research_result,
MultiAgentResearch,VerifyFacts,,"{'verification_threshold': 0.8, 'trusted_sources': ['gov', 'edu']}",fact_verification,SynthesizeFindings,ErrorHandler,web_research_result|academic_research_result,fact_verification_result,
MultiAgentResearch,SynthesizeFindings,,"{'synthesis_style': 'comprehensive', 'target_audience': 'general', 'output_format': 'report'}",research_synthesis,QualityAssurance,ErrorHandler,web_research_result|fact_verification_result,synthesis_result,
MultiAgentResearch,QualityAssurance,,"{'quality_criteria': ['completeness', 'accuracy', 'coherence'], 'min_score': 7}",quality_assurance,GenerateReport,ImproveSynthesis,synthesis_result,quality_assessment,
MultiAgentResearch,ImproveSynthesis,,Improve synthesis based on QA feedback,research_synthesis,QualityAssurance,ErrorHandler,synthesis_result|quality_assessment,improved_synthesis,
MultiAgentResearch,GenerateReport,,Generate final research report,report_generator,End,ErrorHandler,synthesis_result|quality_assessment,final_report,
MultiAgentResearch,End,,Research project complete,echo,,,final_report,completion_message,Multi-agent research completed successfully!
MultiAgentResearch,ErrorHandler,,Handle research errors,echo,End,,error,error_message,Research error encountered: {error}
```

### Agent Registration and Execution

```python
from agentmap import AgentMap

# Create AgentMap instance
agent_map = AgentMap()

# Register all research agents
agent_map.register_agent_type('research_coordinator', ResearchCoordinatorAgent)
agent_map.register_agent_type('topic_analysis', TopicAnalysisAgent)
agent_map.register_agent_type('web_research', WebResearchAgent)
agent_map.register_agent_type('academic_research', AcademicResearchAgent)
agent_map.register_agent_type('fact_verification', FactVerificationAgent)
agent_map.register_agent_type('research_synthesis', ResearchSynthesisAgent)
agent_map.register_agent_type('quality_assurance', QualityAssuranceAgent)
agent_map.register_agent_type('report_generator', ReportGeneratorAgent)

# Execute multi-agent research
research_topic = "The impact of artificial intelligence on healthcare diagnostics"

print(f"Starting multi-agent research on: {research_topic}")
result = agent_map.execute_csv(
    'multi_agent_research.csv', 
    initial_input=research_topic
)

print("Research completed!")
print(f"Final report: {result}")
```

### Interactive Research Session

```python
def interactive_research_session():
    """Run an interactive multi-agent research session"""
    
    agent_map = AgentMap()
    
    # Register agents
    agent_map.register_agent_type('research_coordinator', ResearchCoordinatorAgent)
    agent_map.register_agent_type('topic_analysis', TopicAnalysisAgent)
    agent_map.register_agent_type('web_research', WebResearchAgent)
    agent_map.register_agent_type('fact_verification', FactVerificationAgent)
    agent_map.register_agent_type('research_synthesis', ResearchSynthesisAgent)
    
    print("🔬 Multi-Agent Research System")
    print("=" * 40)
    
    while True:
        topic = input("\nEnter research topic (or 'quit' to exit): ")
        
        if topic.lower() in ['quit', 'exit']:
            break
        
        print(f"\n🚀 Starting research on: {topic}")
        print("Agents working...")
        
        # Coordinate research
        coordinator = ResearchCoordinatorAgent()
        research_plan = coordinator.execute(topic, {
            'research_depth': 'medium',
            'max_agents': 4
        })
        
        print(f"📋 Research plan created with {len(research_plan['research_plan']['agents_needed'])} agents")
        
        # Topic analysis
        topic_agent = TopicAnalysisAgent()
        topic_analysis = topic_agent.execute(topic)
        
        print(f"🎯 Generated {len(topic_analysis['research_questions'])} research questions")
        
        # Web research
        web_agent = WebResearchAgent()
        web_results = web_agent.execute(topic_analysis['research_questions'][:3])
        
        print(f"🌐 Found {web_results['total_sources_found']} web sources")
        
        # Fact verification
        fact_agent = FactVerificationAgent()
        verification_results = fact_agent.execute(web_results['research_results'])
        
        print(f"✅ Verified {verification_results['verified_claims']} claims")
        print(f"❌ Disputed {verification_results['disputed_claims']} claims")
        
        # Synthesis
        synthesis_agent = ResearchSynthesisAgent()
        synthesis = synthesis_agent.execute({
            'web_research': web_results,
            'fact_verification': verification_results
        })
        
        print("\n📊 Research Summary:")
        print("=" * 30)
        print(synthesis['synthesis_content'][:500] + "...")
        
        print(f"\n📈 Confidence Score: {synthesis['confidence_assessment']['overall_confidence']:.1%}")
        
        # Ask if user wants full report
        full_report = input("\nGenerate full report? (y/n): ")
        if full_report.lower() == 'y':
            print("\n" + "="*50)
            print("FULL RESEARCH REPORT")
            print("="*50)
            print(synthesis['synthesis_content'])

if __name__ == "__main__":
    interactive_research_session()
```

## Advanced Features

### 1. Collaborative Agent Communication

```python
class AgentCommunicationHub:
    def __init__(self):
        self.message_queue = []
        self.agent_status = {}
        self.shared_knowledge = {}
    
    def register_agent(self, agent_id: str, agent_type: str):
        """Register agent with communication hub"""
        self.agent_status[agent_id] = {
            'type': agent_type,
            'status': 'ready',
            'last_activity': datetime.now().isoformat()
        }
    
    def send_message(self, from_agent: str, to_agent: str, message_type: str, content: Any):
        """Send message between agents"""
        self.message_queue.append({
            'from': from_agent,
            'to': to_agent,
            'type': message_type,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
    
    def get_messages(self, agent_id: str) -> List[Dict]:
        """Get messages for specific agent"""
        return [msg for msg in self.message_queue if msg['to'] == agent_id]
    
    def update_shared_knowledge(self, agent_id: str, key: str, value: Any):
        """Update shared knowledge base"""
        if agent_id not in self.shared_knowledge:
            self.shared_knowledge[agent_id] = {}
        self.shared_knowledge[agent_id][key] = value
    
    def get_shared_knowledge(self, key: str) -> Any:
        """Retrieve shared knowledge"""
        for agent_data in self.shared_knowledge.values():
            if key in agent_data:
                return agent_data[key]
        return None
```

### 2. Research Quality Metrics

```python
class ResearchQualityAnalyzer:
    def __init__(self):
        self.quality_metrics = {
            'source_diversity': 0.0,
            'fact_verification_rate': 0.0,
            'content_depth': 0.0,
            'bias_detection': 0.0,
            'completeness_score': 0.0
        }
    
    def analyze_research_quality(self, research_results: Dict) -> Dict:
        """Comprehensive research quality analysis"""
        
        # Source diversity analysis
        source_diversity = self.calculate_source_diversity(research_results)
        
        # Fact verification rate
        fact_verification_rate = self.calculate_fact_verification_rate(research_results)
        
        # Content depth analysis
        content_depth = self.analyze_content_depth(research_results)
        
        # Bias detection
        bias_score = self.detect_bias(research_results)
        
        # Completeness assessment
        completeness = self.assess_completeness(research_results)
        
        overall_score = (
            source_diversity * 0.2 +
            fact_verification_rate * 0.3 +
            content_depth * 0.2 +
            bias_score * 0.1 +
            completeness * 0.2
        )
        
        return {
            'overall_quality_score': overall_score,
            'source_diversity': source_diversity,
            'fact_verification_rate': fact_verification_rate,
            'content_depth': content_depth,
            'bias_score': bias_score,
            'completeness_score': completeness,
            'quality_grade': self.assign_quality_grade(overall_score),
            'improvement_recommendations': self.generate_improvement_recommendations(overall_score)
        }
    
    def calculate_source_diversity(self, results: Dict) -> float:
        """Calculate diversity of information sources"""
        
        web_results = results.get('web_research', {}).get('research_results', [])
        
        if not web_results:
            return 0.0
        
        # Count unique domains
        domains = set()
        content_types = set()
        
        for result in web_results:
            url = result.get('url', '')
            domain = url.split('/')[2] if len(url.split('/')) > 2 else ''
            domains.add(domain)
            content_types.add(result.get('content_type', 'unknown'))
        
        # Calculate diversity score
        domain_diversity = min(len(domains) / 10, 1.0)  # Max score at 10 unique domains
        type_diversity = min(len(content_types) / 5, 1.0)  # Max score at 5 content types
        
        return (domain_diversity + type_diversity) / 2
    
    def calculate_fact_verification_rate(self, results: Dict) -> float:
        """Calculate rate of fact verification"""
        
        verification_results = results.get('fact_verification', {})
        
        total_claims = verification_results.get('total_claims_checked', 0)
        verified_claims = verification_results.get('verified_claims', 0)
        
        return verified_claims / total_claims if total_claims > 0 else 0.0
    
    def analyze_content_depth(self, results: Dict) -> float:
        """Analyze depth and comprehensiveness of content"""
        
        web_results = results.get('web_research', {}).get('research_results', [])
        
        if not web_results:
            return 0.0
        
        # Calculate average content length and quality indicators
        total_words = sum(result.get('word_count', 0) for result in web_results)
        avg_words = total_words / len(web_results)
        
        # Score based on content length and quality
        length_score = min(avg_words / 1000, 1.0)  # Max score at 1000 avg words
        
        # Check for quality indicators
        quality_indicators = ['academic_paper', 'official_source', 'encyclopedia']
        quality_sources = len([r for r in web_results if r.get('content_type') in quality_indicators])
        quality_score = min(quality_sources / len(web_results), 1.0)
        
        return (length_score + quality_score) / 2
    
    def detect_bias(self, results: Dict) -> float:
        """Detect potential bias in sources and content"""
        
        # Simplified bias detection
        # In production, use advanced NLP bias detection models
        
        web_results = results.get('web_research', {}).get('research_results', [])
        
        if not web_results:
            return 0.5  # Neutral score
        
        # Check source diversity as bias indicator
        domains = [result.get('url', '').split('/')[2] for result in web_results]
        unique_domains = len(set(domains))
        
        # Higher source diversity generally indicates lower bias
        bias_score = min(unique_domains / len(web_results), 1.0)
        
        return bias_score
    
    def assess_completeness(self, results: Dict) -> float:
        """Assess completeness of research coverage"""
        
        topic_analysis = results.get('topic_analysis', {})
        web_results = results.get('web_research', {})
        
        # Check if research questions were addressed
        research_questions = topic_analysis.get('research_questions', [])
        sources_found = web_results.get('total_sources_found', 0)
        
        if not research_questions:
            return 0.5
        
        # Score based on sources per question
        sources_per_question = sources_found / len(research_questions)
        completeness_score = min(sources_per_question / 3, 1.0)  # Max at 3 sources per question
        
        return completeness_score
    
    def assign_quality_grade(self, score: float) -> str:
        """Assign letter grade based on quality score"""
        
        if score >= 0.9:
            return 'A+'
        elif score >= 0.8:
            return 'A'
        elif score >= 0.7:
            return 'B+'
        elif score >= 0.6:
            return 'B'
        elif score >= 0.5:
            return 'C+'
        elif score >= 0.4:
            return 'C'
        else:
            return 'D'
    
    def generate_improvement_recommendations(self, score: float) -> List[str]:
        """Generate recommendations for improving research quality"""
        
        recommendations = []
        
        if score < 0.7:
            recommendations.append("Increase source diversity by searching multiple databases")
            recommendations.append("Enhance fact verification with additional cross-referencing")
        
        if score < 0.6:
            recommendations.append("Seek deeper, more comprehensive sources")
            recommendations.append("Include more academic and official sources")
        
        if score < 0.5:
            recommendations.append("Expand research scope to cover more aspects")
            recommendations.append("Implement stronger bias detection and mitigation")
        
        return recommendations
```

### 3. Real-time Research Monitoring

```python
class ResearchMonitoringDashboard:
    def __init__(self):
        self.active_research = {}
        self.performance_metrics = {}
    
    def start_monitoring(self, research_id: str, topic: str):
        """Start monitoring a research session"""
        self.active_research[research_id] = {
            'topic': topic,
            'start_time': datetime.now(),
            'agents_active': [],
            'progress_percentage': 0,
            'current_stage': 'initialization',
            'findings_count': 0,
            'issues_encountered': []
        }
    
    def update_agent_status(self, research_id: str, agent_name: str, status: str, progress: float):
        """Update agent status in monitoring dashboard"""
        if research_id in self.active_research:
            research = self.active_research[research_id]
            
            # Update agent status
            if agent_name not in research['agents_active']:
                research['agents_active'].append(agent_name)
            
            # Update overall progress
            research['progress_percentage'] = progress
            research['current_stage'] = status
    
    def log_finding(self, research_id: str, finding_type: str, content: str):
        """Log research finding"""
        if research_id in self.active_research:
            self.active_research[research_id]['findings_count'] += 1
    
    def log_issue(self, research_id: str, issue_type: str, description: str):
        """Log research issue"""
        if research_id in self.active_research:
            self.active_research[research_id]['issues_encountered'].append({
                'type': issue_type,
                'description': description,
                'timestamp': datetime.now().isoformat()
            })
    
    def generate_status_report(self, research_id: str) -> str:
        """Generate real-time status report"""
        if research_id not in self.active_research:
            return "Research session not found"
        
        research = self.active_research[research_id]
        elapsed_time = datetime.now() - research['start_time']
        
        report = f"""
Research Status Report
=====================
Topic: {research['topic']}
Elapsed Time: {elapsed_time}
Progress: {research['progress_percentage']:.1f}%
Current Stage: {research['current_stage']}
Active Agents: {', '.join(research['agents_active'])}
Findings Collected: {research['findings_count']}
Issues Encountered: {len(research['issues_encountered'])}
"""
        
        if research['issues_encountered']:
            report += "\nRecent Issues:\n"
            for issue in research['issues_encountered'][-3:]:
                report += f"- {issue['type']}: {issue['description']}\n"
        
        return report
```

This comprehensive multi-agent research system demonstrates AgentMap's capability to orchestrate complex, collaborative AI workflows. The system can be extended with additional specialized agents, enhanced communication protocols, and more sophisticated analysis capabilities.

For integration with real APIs and databases, see the [Building Custom Agents Tutorial](/docs/tutorials/building-custom-agents) and [Advanced Agent Development Guide](/docs/guides/development/agents/agent-development).
