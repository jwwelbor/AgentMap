---
sidebar_position: 4
title: Document Analyzer
description: Build an AI-powered document analyzer that extracts insights from PDFs and text files
---

# Build a Document Analyzer

## What We're Building

Create an intelligent document analyzer that:
- ✅ Processes multiple file formats (PDF, DOCX, TXT, MD)
- ✅ Extracts text and metadata from documents
- ✅ Generates AI-powered summaries and insights
- ✅ Identifies key topics, entities, and sentiment
- ✅ Creates structured reports with actionable findings

**Estimated Time**: 50 minutes  
**Difficulty**: Intermediate-Advanced  
**Learning Goals**: File processing, text extraction, AI analysis, structured reporting

## Prerequisites

- Python 3.8+ with AgentMap installed (`pip install agentmap`)
- OpenAI or Anthropic API key for AI analysis
- Document processing libraries: `pip install pypdf2 python-docx`
- Sample documents (PDF, DOCX, or text files)

## Workflow Overview

```mermaid
graph TD
    A[Select Documents] --> B[Detect File Type]
    B --> C[Extract Text]
    C --> D[Process Metadata]
    D --> E[Chunk Content]
    E --> F[AI Analysis]
    F --> G[Extract Entities]
    G --> H[Generate Summary]
    H --> I[Create Report]
    I --> J[Export Results]
    
    B -->|Unsupported| K[Error Handler]
    C -->|Failed| K
    F -->|Failed| K
    K --> L[Partial Results]
    
    style A fill:#e1f5fe
    style C fill:#fff3e0
    style F fill:#e8f5e8
    style H fill:#f3e5f5
    style I fill:#fff8e1
    style J fill:#e0f2f1
    style K fill:#ffebee
```

## Step 1: Create Sample Documents

Create a sample document to analyze. Save this as `sample_document.txt`:

```text title="data/sample_document.txt"
# Quarterly Business Report - Q2 2024

## Executive Summary

This quarter has shown remarkable growth across all key performance indicators. Our company achieved a 23% increase in revenue compared to Q1 2024, reaching $4.2 million in total sales. Customer satisfaction scores have improved to 4.7/5.0, and we've successfully expanded into three new markets.

## Key Achievements

### Revenue Growth
- Total revenue: $4.2M (23% increase from Q1)
- New customer acquisitions: 1,847 customers
- Customer retention rate: 92%
- Average deal size increased by 15%

### Product Development
- Launched two major feature updates
- Reduced product bugs by 34%
- Improved application performance by 28%
- Released mobile app version 2.0

### Market Expansion
- Entered European market (Germany, France, UK)
- Established partnerships with 12 new vendors
- Opened satellite office in Berlin
- Hired 45 new employees globally

## Challenges and Concerns

### Operational Challenges
- Supply chain delays affecting 15% of orders
- Increased competition in core markets
- Higher than expected employee turnover (18%)
- Rising costs in customer acquisition

### Technical Issues
- Server downtime incidents (3 major, 7 minor)
- Database performance degradation during peak hours
- Mobile app store approval delays
- Integration challenges with legacy systems

## Financial Performance

### Revenue Breakdown
- Product sales: $3.1M (74% of total)
- Service contracts: $0.8M (19% of total)
- Licensing fees: $0.3M (7% of total)

### Expense Analysis
- Personnel costs: $1.8M (43% of revenue)
- Marketing and sales: $0.7M (17% of revenue)
- Technology infrastructure: $0.4M (10% of revenue)
- Operations: $0.6M (14% of revenue)

### Profitability
- Gross profit margin: 68%
- Operating profit margin: 16%
- Net profit: $0.67M

## Market Analysis

### Competitive Landscape
The market continues to be highly competitive with three major players controlling 60% of the market share. However, our unique value proposition and customer-centric approach have allowed us to capture 8% market share, up from 6% last quarter.

### Customer Feedback
Customer surveys indicate high satisfaction with our product quality (94% positive) and customer service (89% positive). Main areas for improvement include:
- Faster response times for technical support
- More flexible pricing options for small businesses
- Enhanced mobile app functionality
- Better integration capabilities

## Future Outlook

### Q3 2024 Projections
- Revenue target: $4.8M (14% growth)
- New customer target: 2,200 acquisitions
- Product launches: 3 major features planned
- Market expansion: Asia-Pacific region exploration

### Strategic Priorities
1. Improve supply chain reliability
2. Enhance customer support capabilities
3. Accelerate product development cycles
4. Strengthen market position in Europe

### Investment Plans
- $2M investment in new technology infrastructure
- $1.5M allocated for market expansion initiatives
- $800K for additional hiring across all departments
- $600K for product development and R&D

## Conclusion

Q2 2024 has been a strong quarter demonstrating our company's resilience and growth potential. While we face challenges in supply chain and competition, our strategic focus on customer satisfaction and product innovation positions us well for continued success.

The executive team recommends maintaining aggressive growth targets while investing in operational efficiency and customer experience improvements. With proper execution of our strategic initiatives, we project achieving $20M annual revenue by end of 2024.

---

Report prepared by: Business Analytics Team
Date: July 15, 2024
Next review: October 15, 2024
```

## Step 2: Create Document Analyzer Workflow

Create `document_analyzer.csv`:

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt,Description
DocAnalyzer,SelectDocument,,Get document path from user,input,DetectFileType,ErrorHandler,,document_path,Enter the path to your document (or press Enter for sample):,Get document file path from user
DocAnalyzer,DetectFileType,,Detect and validate file type,custom:FileTypeDetectorAgent,ExtractText,ErrorHandler,document_path,file_info,,Detect file type and validate readability
DocAnalyzer,ExtractText,,Extract text content from document,custom:TextExtractionAgent,ProcessMetadata,ErrorHandler,document_path|file_info,extracted_content,,Extract text and basic content from document
DocAnalyzer,ProcessMetadata,,Extract document metadata and structure,custom:MetadataProcessorAgent,ChunkContent,ErrorHandler,extracted_content|file_info,document_metadata,,Process document structure and metadata
DocAnalyzer,ChunkContent,,Split content into analyzable chunks,custom:ContentChunkerAgent,AnalyzeContent,ErrorHandler,extracted_content|document_metadata,chunked_content,,Split content into optimal chunks for AI analysis
DocAnalyzer,AnalyzeContent,,{"provider": "openai", "model": "gpt-4", "temperature": 0.3, "max_tokens": 2000},llm,ExtractEntities,ErrorHandler,chunked_content,ai_analysis,"Analyze this document content and provide insights on key themes, important information, sentiment, and overall summary. Focus on actionable insights and important details: {chunked_content}",Generate AI-powered content analysis
DocAnalyzer,ExtractEntities,,Extract named entities and key information,custom:EntityExtractionAgent,GenerateSummary,ErrorHandler,extracted_content|ai_analysis,entities_data,,Extract people, organizations, locations, and key metrics
DocAnalyzer,GenerateSummary,,{"provider": "openai", "model": "gpt-4", "temperature": 0.4},llm,CreateReport,ErrorHandler,ai_analysis|entities_data|document_metadata,executive_summary,"Create a comprehensive executive summary of this document including key findings, important metrics, main themes, and actionable recommendations: Analysis: {ai_analysis} | Entities: {entities_data}",Generate executive summary with key insights
DocAnalyzer,CreateReport,,Compile comprehensive analysis report,custom:ReportGeneratorAgent,ExportResults,ErrorHandler,extracted_content|ai_analysis|entities_data|executive_summary|document_metadata,analysis_report,,Generate structured analysis report
DocAnalyzer,ExportResults,,Export analysis results,custom:ResultsExporterAgent,End,ErrorHandler,analysis_report|document_metadata,export_results,,Export results in multiple formats
DocAnalyzer,ErrorHandler,,Handle processing errors gracefully,echo,End,,error,error_message,,Display error information to user
DocAnalyzer,End,,Analysis complete,echo,,,export_results|error_message,output,,Display final results and completion
```

## Step 3: Generate and Implement Custom Agents

Generate agent templates:

```bash
agentmap scaffold --csv document_analyzer.csv
```

## Step 4: Implement File Type Detector Agent

Create `custom_agents/file_type_detector_agent.py`:

```python title="custom_agents/file_type_detector_agent.py"
from typing import Dict, Any, Optional
import os
import mimetypes
from pathlib import Path
from agentmap.agents.base_agent import BaseAgent

class FileTypeDetectorAgent(BaseAgent):
    """
    Detects file type and validates document readability.
    
    Supports PDF, DOCX, TXT, MD, and other text-based formats.
    """
    
    def __init__(self, name, prompt, context=None, logger=None,
                 execution_tracker_service=None, state_adapter_service=None):
        super().__init__(name, prompt, context, logger,
                         execution_tracker_service, state_adapter_service)
        
        # Supported file types and their handlers
        self.supported_types = {
            '.pdf': {'type': 'pdf', 'description': 'Portable Document Format'},
            '.docx': {'type': 'docx', 'description': 'Microsoft Word Document'},
            '.doc': {'type': 'doc', 'description': 'Microsoft Word Document (Legacy)'},
            '.txt': {'type': 'text', 'description': 'Plain Text'},
            '.md': {'type': 'markdown', 'description': 'Markdown'},
            '.rtf': {'type': 'rtf', 'description': 'Rich Text Format'},
            '.html': {'type': 'html', 'description': 'HTML Document'},
            '.htm': {'type': 'html', 'description': 'HTML Document'}
        }
        
        # Default sample document
        self.sample_document = "data/sample_document.txt"
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Detect file type and validate accessibility.
        
        Args:
            inputs: Dictionary containing 'document_path'
            
        Returns:
            File information including type, size, and validation status
        """
        document_path = inputs.get("document_path", "").strip()
        
        # Use sample document if no path provided
        if not document_path or document_path.lower() in ["", "sample", "default"]:
            document_path = self.sample_document
            self.log_info("Using sample document for analysis")
        
        try:
            # Ensure path exists
            path_obj = Path(document_path)
            
            if not path_obj.exists():
                return {
                    "valid": False,
                    "error": f"File not found: {document_path}",
                    "suggestion": f"Please check the file path or use sample document",
                    "file_path": document_path
                }
            
            # Get file information
            file_stats = path_obj.stat()
            file_extension = path_obj.suffix.lower()
            
            # Check if file type is supported
            if file_extension not in self.supported_types:
                return {
                    "valid": False,
                    "error": f"Unsupported file type: {file_extension}",
                    "supported_types": list(self.supported_types.keys()),
                    "file_path": document_path
                }
            
            # Get MIME type
            mime_type, _ = mimetypes.guess_type(document_path)
            
            # Validate file accessibility
            try:
                with open(document_path, 'rb') as f:
                    # Try to read first few bytes
                    first_bytes = f.read(1024)
                    readable = len(first_bytes) > 0
            except PermissionError:
                return {
                    "valid": False,
                    "error": "Permission denied - cannot read file",
                    "file_path": document_path
                }
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"File read error: {str(e)}",
                    "file_path": document_path
                }
            
            # Get file type information
            type_info = self.supported_types[file_extension]
            
            # Prepare file information
            file_info = {
                "valid": True,
                "file_path": str(path_obj.absolute()),
                "file_name": path_obj.name,
                "file_size": file_stats.st_size,
                "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
                "file_extension": file_extension,
                "file_type": type_info['type'],
                "file_description": type_info['description'],
                "mime_type": mime_type,
                "readable": readable,
                "modified_date": file_stats.st_mtime,
                "processing_method": self._get_processing_method(type_info['type'])
            }
            
            # Check file size limitations
            max_size_mb = self.context.get("max_file_size_mb", 50)
            if file_info["file_size_mb"] > max_size_mb:
                file_info["warning"] = f"Large file ({file_info['file_size_mb']}MB) - processing may be slow"
            
            self.log_info(f"Detected {type_info['description']} file: {path_obj.name} ({file_info['file_size_mb']}MB)")
            
            return file_info
            
        except Exception as e:
            error_msg = f"File type detection failed: {str(e)}"
            self.log_error(error_msg)
            return {
                "valid": False,
                "error": error_msg,
                "file_path": document_path
            }
    
    def _get_processing_method(self, file_type: str) -> str:
        """Determine processing method based on file type."""
        processing_methods = {
            'pdf': 'pdf_extraction',
            'docx': 'docx_extraction',
            'doc': 'doc_extraction',
            'text': 'direct_read',
            'markdown': 'direct_read',
            'rtf': 'rtf_extraction',
            'html': 'html_parsing'
        }
        return processing_methods.get(file_type, 'generic_extraction')
    
    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """Provide debugging information."""
        return {
            "supported_extensions": list(self.supported_types.keys()),
            "sample_document": self.sample_document,
            "max_file_size_mb": self.context.get("max_file_size_mb", 50)
        }
```

## Step 5: Implement Text Extraction Agent

Create `custom_agents/text_extraction_agent.py`:

```python title="custom_agents/text_extraction_agent.py"
from typing import Dict, Any, Optional
import os
from pathlib import Path
from agentmap.agents.base_agent import BaseAgent

# Optional imports - install as needed
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

class TextExtractionAgent(BaseAgent):
    """
    Extracts text content from various document formats.
    
    Handles PDF, DOCX, TXT, MD, and other text-based files
    with fallback extraction methods.
    """
    
    def __init__(self, name, prompt, context=None, logger=None,
                 execution_tracker_service=None, state_adapter_service=None):
        super().__init__(name, prompt, context, logger,
                         execution_tracker_service, state_adapter_service)
        
        # Configuration
        self.max_text_length = self.context.get("max_text_length", 500000)  # 500KB
        self.preserve_formatting = self.context.get("preserve_formatting", True)
        self.extract_metadata = self.context.get("extract_metadata", True)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Extract text content from document.
        
        Args:
            inputs: Dictionary containing 'document_path' and 'file_info'
            
        Returns:
            Extracted text content with metadata
        """
        document_path = inputs.get("document_path", "")
        file_info = inputs.get("file_info", {})
        
        if not file_info.get("valid", False):
            return {
                "success": False,
                "error": "Invalid file information provided",
                "extracted_text": "",
                "metadata": {}
            }
        
        file_type = file_info.get("file_type", "unknown")
        file_path = file_info.get("file_path", document_path)
        
        try:
            # Extract based on file type
            extraction_result = self._extract_by_type(file_path, file_type)
            
            # Validate extraction
            if not extraction_result["success"]:
                return extraction_result
            
            extracted_text = extraction_result["text"]
            
            # Check text length
            if len(extracted_text) > self.max_text_length:
                self.log_warning(f"Text length ({len(extracted_text)}) exceeds maximum ({self.max_text_length})")
                extracted_text = extracted_text[:self.max_text_length] + "\\n\\n[TEXT TRUNCATED - CONTENT TOO LONG]"
            
            # Prepare result
            result = {
                "success": True,
                "extracted_text": extracted_text,
                "text_length": len(extracted_text),
                "text_preview": extracted_text[:200] + "..." if len(extracted_text) > 200 else extracted_text,
                "extraction_metadata": {
                    "file_type": file_type,
                    "extraction_method": extraction_result.get("method", "unknown"),
                    "character_count": len(extracted_text),
                    "word_count": len(extracted_text.split()),
                    "line_count": extracted_text.count('\\n'),
                    "paragraphs": extracted_text.count('\\n\\n') + 1
                }
            }
            
            # Add document-specific metadata
            if "metadata" in extraction_result:
                result["document_metadata"] = extraction_result["metadata"]
            
            self.log_info(f"Extracted {len(extracted_text)} characters from {file_type} document")
            
            return result
            
        except Exception as e:
            error_msg = f"Text extraction failed: {str(e)}"
            self.log_error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "extracted_text": "",
                "metadata": {}
            }
    
    def _extract_by_type(self, file_path: str, file_type: str) -> Dict[str, Any]:
        """Extract text based on file type."""
        
        if file_type == "pdf":
            return self._extract_pdf(file_path)
        elif file_type == "docx":
            return self._extract_docx(file_path)
        elif file_type in ["text", "markdown"]:
            return self._extract_text(file_path)
        elif file_type == "html":
            return self._extract_html(file_path)
        else:
            # Fallback to text extraction
            return self._extract_text(file_path)
    
    def _extract_pdf(self, file_path: str) -> Dict[str, Any]:
        """Extract text from PDF file."""
        if not PDF_AVAILABLE:
            return self._extract_text_fallback(file_path, "PyPDF2 not available")
        
        try:
            text_content = []
            metadata = {}
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # Extract metadata
                if pdf_reader.metadata:
                    metadata = {
                        "title": pdf_reader.metadata.get("/Title", ""),
                        "author": pdf_reader.metadata.get("/Author", ""),
                        "subject": pdf_reader.metadata.get("/Subject", ""),
                        "creator": pdf_reader.metadata.get("/Creator", ""),
                        "pages": len(pdf_reader.pages)
                    }
                
                # Extract text from each page
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            if self.preserve_formatting:
                                text_content.append(f"--- Page {page_num + 1} ---\\n{page_text}\\n")
                            else:
                                text_content.append(page_text)
                    except Exception as e:
                        self.log_warning(f"Failed to extract page {page_num + 1}: {e}")
            
            extracted_text = "\\n".join(text_content)
            
            if not extracted_text.strip():
                return {
                    "success": False,
                    "error": "No text could be extracted from PDF",
                    "method": "pdf_extraction"
                }
            
            return {
                "success": True,
                "text": extracted_text,
                "metadata": metadata,
                "method": "pdf_extraction"
            }
            
        except Exception as e:
            return self._extract_text_fallback(file_path, f"PDF extraction failed: {e}")
    
    def _extract_docx(self, file_path: str) -> Dict[str, Any]:
        """Extract text from DOCX file."""
        if not DOCX_AVAILABLE:
            return self._extract_text_fallback(file_path, "python-docx not available")
        
        try:
            doc = Document(file_path)
            text_content = []
            metadata = {}
            
            # Extract core properties
            if hasattr(doc, 'core_properties'):
                metadata = {
                    "title": doc.core_properties.title or "",
                    "author": doc.core_properties.author or "",
                    "subject": doc.core_properties.subject or "",
                    "created": str(doc.core_properties.created) if doc.core_properties.created else "",
                    "modified": str(doc.core_properties.modified) if doc.core_properties.modified else ""
                }
            
            # Extract paragraphs
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            # Extract tables
            for table in doc.tables:
                table_text = []
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        row_text.append(cell.text.strip())
                    table_text.append(" | ".join(row_text))
                
                if table_text:
                    text_content.append("\\n".join(table_text))
            
            extracted_text = "\\n\\n".join(text_content)
            
            if not extracted_text.strip():
                return {
                    "success": False,
                    "error": "No text could be extracted from DOCX",
                    "method": "docx_extraction"
                }
            
            return {
                "success": True,
                "text": extracted_text,
                "metadata": metadata,
                "method": "docx_extraction"
            }
            
        except Exception as e:
            return self._extract_text_fallback(file_path, f"DOCX extraction failed: {e}")
    
    def _extract_text(self, file_path: str) -> Dict[str, Any]:
        """Extract text from plain text files."""
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin1', 'cp1252']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        text = file.read()
                        
                        return {
                            "success": True,
                            "text": text,
                            "metadata": {"encoding": encoding},
                            "method": "text_extraction"
                        }
                except UnicodeDecodeError:
                    continue
            
            # If all encodings fail, try binary mode
            with open(file_path, 'rb') as file:
                raw_bytes = file.read()
                text = raw_bytes.decode('utf-8', errors='replace')
                
                return {
                    "success": True,
                    "text": text,
                    "metadata": {"encoding": "binary_fallback"},
                    "method": "binary_extraction"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Text extraction failed: {e}",
                "method": "text_extraction"
            }
    
    def _extract_html(self, file_path: str) -> Dict[str, Any]:
        """Extract text from HTML files."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                html_content = file.read()
            
            # Simple HTML tag removal (for basic HTML)
            import re
            # Remove script and style elements
            html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', html_content)
            # Clean up whitespace
            text = re.sub(r'\\s+', ' ', text).strip()
            
            return {
                "success": True,
                "text": text,
                "metadata": {"format": "html"},
                "method": "html_extraction"
            }
            
        except Exception as e:
            return self._extract_text_fallback(file_path, f"HTML extraction failed: {e}")
    
    def _extract_text_fallback(self, file_path: str, reason: str) -> Dict[str, Any]:
        """Fallback text extraction method."""
        self.log_warning(f"Using fallback extraction: {reason}")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                text = file.read()
                
            return {
                "success": True,
                "text": text,
                "metadata": {"fallback_reason": reason},
                "method": "fallback_extraction"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Fallback extraction failed: {e}",
                "method": "fallback_extraction"
            }
    
    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """Provide debugging information."""
        return {
            "pdf_available": PDF_AVAILABLE,
            "docx_available": DOCX_AVAILABLE,
            "max_text_length": self.max_text_length,
            "preserve_formatting": self.preserve_formatting
        }
```

## Step 6: Implement Remaining Agents

Due to length constraints, I'll provide the key remaining agents. Create `custom_agents/metadata_processor_agent.py`:

```python title="custom_agents/metadata_processor_agent.py"
from typing import Dict, Any, Optional
import re
from datetime import datetime
from agentmap.agents.base_agent import BaseAgent

class MetadataProcessorAgent(BaseAgent):
    """
    Processes document structure and extracts metadata.
    """
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process document metadata and structure.
        
        Args:
            inputs: Dictionary containing 'extracted_content' and 'file_info'
            
        Returns:
            Processed metadata and document structure
        """
        extracted_content = inputs.get("extracted_content", {})
        file_info = inputs.get("file_info", {})
        
        if not extracted_content.get("success", False):
            return {
                "success": False,
                "error": "No extracted content available",
                "metadata": {}
            }
        
        text = extracted_content.get("extracted_text", "")
        
        try:
            # Analyze document structure
            structure = self._analyze_structure(text)
            
            # Extract key statistics
            statistics = self._calculate_statistics(text)
            
            # Detect language and readability
            language_info = self._analyze_language(text)
            
            # Combine metadata
            metadata = {
                "processing_timestamp": datetime.now().isoformat(),
                "file_metadata": file_info,
                "content_structure": structure,
                "statistics": statistics,
                "language_analysis": language_info,
                "extraction_metadata": extracted_content.get("extraction_metadata", {})
            }
            
            return {
                "success": True,
                "metadata": metadata,
                "structure_summary": self._create_structure_summary(structure, statistics)
            }
            
        except Exception as e:
            self.log_error(f"Metadata processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "metadata": {}
            }
    
    def _analyze_structure(self, text: str) -> Dict[str, Any]:
        """Analyze document structure."""
        # Find headers (lines starting with #, or ALL CAPS lines)
        headers = []
        header_patterns = [
            r'^#{1,6}\\s+(.+)$',  # Markdown headers
            r'^([A-Z][A-Z\\s]{10,})$',  # ALL CAPS headers
            r'^\\d+\\.\\s+([A-Z].+)$'  # Numbered headers
        ]
        
        lines = text.split('\\n')
        for i, line in enumerate(lines):
            line = line.strip()
            for pattern in header_patterns:
                match = re.match(pattern, line, re.MULTILINE)
                if match:
                    headers.append({
                        "text": match.group(1) if match.groups() else line,
                        "line_number": i + 1,
                        "level": line.count('#') if line.startswith('#') else 1
                    })
                    break
        
        # Find lists and bullet points
        lists = len(re.findall(r'^\\s*[-*+]\\s+', text, re.MULTILINE))
        numbered_lists = len(re.findall(r'^\\s*\\d+\\.\\s+', text, re.MULTILINE))
        
        # Find paragraphs
        paragraphs = [p.strip() for p in text.split('\\n\\n') if p.strip()]
        
        return {
            "headers": headers,
            "header_count": len(headers),
            "list_items": lists,
            "numbered_items": numbered_lists,
            "paragraph_count": len(paragraphs),
            "average_paragraph_length": sum(len(p) for p in paragraphs) / len(paragraphs) if paragraphs else 0
        }
    
    def _calculate_statistics(self, text: str) -> Dict[str, Any]:
        """Calculate text statistics."""
        words = text.split()
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return {
            "character_count": len(text),
            "word_count": len(words),
            "sentence_count": len(sentences),
            "average_words_per_sentence": len(words) / len(sentences) if sentences else 0,
            "average_characters_per_word": len(text.replace(' ', '')) / len(words) if words else 0,
            "unique_words": len(set(word.lower().strip('.,!?;:') for word in words)),
            "readability_score": self._calculate_readability(text, words, sentences)
        }
    
    def _analyze_language(self, text: str) -> Dict[str, Any]:
        """Analyze language characteristics."""
        # Simple language detection based on common words
        english_indicators = ['the', 'and', 'of', 'to', 'a', 'in', 'is', 'it', 'you', 'that']
        text_lower = text.lower()
        
        english_score = sum(1 for word in english_indicators if word in text_lower)
        
        return {
            "detected_language": "english" if english_score > 5 else "unknown",
            "confidence": min(1.0, english_score / 10),
            "text_complexity": "high" if len(text.split()) / len(re.split(r'[.!?]+', text)) > 20 else "medium"
        }
    
    def _calculate_readability(self, text: str, words: list, sentences: list) -> float:
        """Calculate Flesch Reading Ease score (simplified)."""
        if not words or not sentences:
            return 0
        
        avg_sentence_length = len(words) / len(sentences)
        
        # Count syllables (simplified - count vowel groups)
        syllable_count = 0
        for word in words:
            word = word.lower().strip('.,!?;:')
            syllables = len(re.findall(r'[aeiouAEIOU]+', word))
            syllable_count += max(1, syllables)  # Every word has at least 1 syllable
        
        avg_syllables_per_word = syllable_count / len(words)
        
        # Simplified Flesch formula
        score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        return max(0, min(100, score))
    
    def _create_structure_summary(self, structure: Dict, statistics: Dict) -> str:
        """Create human-readable structure summary."""
        summary_parts = []
        
        summary_parts.append(f"Document contains {statistics['word_count']} words in {statistics['sentence_count']} sentences")
        
        if structure['header_count'] > 0:
            summary_parts.append(f"{structure['header_count']} headers found")
        
        if structure['paragraph_count'] > 0:
            summary_parts.append(f"{structure['paragraph_count']} paragraphs")
        
        if structure['list_items'] > 0:
            summary_parts.append(f"{structure['list_items']} bullet points")
        
        readability = statistics.get('readability_score', 0)
        if readability > 60:
            summary_parts.append("Easy to read")
        elif readability > 30:
            summary_parts.append("Moderate reading difficulty")
        else:
            summary_parts.append("Complex reading level")
        
        return ". ".join(summary_parts) + "."
```

## Step 7: Implement Content Chunker Agent

Create `custom_agents/content_chunker_agent.py`:

```python title="custom_agents/content_chunker_agent.py"
from typing import Dict, Any, Optional, List
import re
from agentmap.agents.base_agent import BaseAgent

class ContentChunkerAgent(BaseAgent):
    """
    Splits content into optimal chunks for AI analysis.
    """
    
    def __init__(self, name, prompt, context=None, logger=None,
                 execution_tracker_service=None, state_adapter_service=None):
        super().__init__(name, prompt, context, logger,
                         execution_tracker_service, state_adapter_service)
        
        # Chunking configuration
        self.chunk_size = self.context.get("chunk_size", 3000)  # characters
        self.chunk_overlap = self.context.get("chunk_overlap", 300)  # characters
        self.preserve_paragraphs = self.context.get("preserve_paragraphs", True)
        self.preserve_sentences = self.context.get("preserve_sentences", True)
    
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Split content into analysis-ready chunks.
        
        Args:
            inputs: Dictionary containing 'extracted_content' and 'document_metadata'
            
        Returns:
            Content split into optimal chunks with metadata
        """
        extracted_content = inputs.get("extracted_content", {})
        document_metadata = inputs.get("document_metadata", {})
        
        if not extracted_content.get("success", False):
            return {
                "success": False,
                "error": "No extracted content available",
                "chunks": []
            }
        
        text = extracted_content.get("extracted_text", "")
        
        if not text.strip():
            return {
                "success": False,
                "error": "No text content to chunk",
                "chunks": []
            }
        
        try:
            # Create chunks
            chunks = self._create_smart_chunks(text)
            
            # Add chunk metadata
            chunk_data = []
            for i, chunk in enumerate(chunks):
                chunk_info = {
                    "chunk_id": i + 1,
                    "content": chunk,
                    "character_count": len(chunk),
                    "word_count": len(chunk.split()),
                    "preview": chunk[:150] + "..." if len(chunk) > 150 else chunk
                }
                chunk_data.append(chunk_info)
            
            # Prepare analysis-ready content
            analysis_content = self._prepare_analysis_content(chunk_data, document_metadata)
            
            result = {
                "success": True,
                "chunks": chunk_data,
                "total_chunks": len(chunk_data),
                "analysis_content": analysis_content,
                "chunking_metadata": {
                    "chunk_size": self.chunk_size,
                    "chunk_overlap": self.chunk_overlap,
                    "total_chunks": len(chunk_data),
                    "average_chunk_size": sum(len(chunk) for chunk in chunks) / len(chunks) if chunks else 0,
                    "preserve_paragraphs": self.preserve_paragraphs,
                    "preserve_sentences": self.preserve_sentences
                }
            }
            
            self.log_info(f"Created {len(chunk_data)} chunks from {len(text)} characters")
            
            return result
            
        except Exception as e:
            error_msg = f"Content chunking failed: {str(e)}"
            self.log_error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "chunks": []
            }
    
    def _create_smart_chunks(self, text: str) -> List[str]:
        """Create intelligent chunks preserving structure."""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        
        if self.preserve_paragraphs:
            # Split by paragraphs first
            paragraphs = [p.strip() for p in text.split('\\n\\n') if p.strip()]
            chunks = self._chunk_by_paragraphs(paragraphs)
        else:
            # Split by sentences
            sentences = self._split_into_sentences(text)
            chunks = self._chunk_by_sentences(sentences)
        
        # If chunks are still too large, force split
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.chunk_size:
                final_chunks.append(chunk)
            else:
                # Force split large chunks
                sub_chunks = self._force_split_chunk(chunk)
                final_chunks.extend(sub_chunks)
        
        return final_chunks
    
    def _chunk_by_paragraphs(self, paragraphs: List[str]) -> List[str]:
        """Chunk content by paragraphs."""
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            # If adding this paragraph would exceed chunk size
            if len(current_chunk) + len(paragraph) + 2 > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # Start new chunk with overlap
                    if self.chunk_overlap > 0:
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                        current_chunk = overlap_text + "\\n\\n" + paragraph
                    else:
                        current_chunk = paragraph
                else:
                    # Single paragraph is larger than chunk size
                    chunks.append(paragraph)
                    current_chunk = ""
            else:
                if current_chunk:
                    current_chunk += "\\n\\n" + paragraph
                else:
                    current_chunk = paragraph
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _chunk_by_sentences(self, sentences: List[str]) -> List[str]:
        """Chunk content by sentences."""
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # If adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) + 1 > self.chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    # Start new chunk with overlap
                    if self.chunk_overlap > 0:
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                        current_chunk = overlap_text + " " + sentence
                    else:
                        current_chunk = sentence
                else:
                    # Single sentence is larger than chunk size
                    chunks.append(sentence)
                    current_chunk = ""
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+\\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _force_split_chunk(self, chunk: str) -> List[str]:
        """Force split oversized chunks."""
        chunks = []
        while len(chunk) > self.chunk_size:
            # Find best split point (prefer whitespace)
            split_point = self.chunk_size
            
            # Look backwards for whitespace
            for i in range(split_point, max(0, split_point - 100), -1):
                if chunk[i].isspace():
                    split_point = i
                    break
            
            # Split the chunk
            chunks.append(chunk[:split_point].strip())
            
            # Start next chunk with overlap
            if self.chunk_overlap > 0:
                overlap_start = max(0, split_point - self.chunk_overlap)
                chunk = chunk[overlap_start:]
            else:
                chunk = chunk[split_point:]
        
        if chunk.strip():
            chunks.append(chunk.strip())
        
        return chunks
    
    def _prepare_analysis_content(self, chunk_data: List[Dict], metadata: Dict) -> str:
        """Prepare content for AI analysis."""
        # Combine chunks with headers for analysis
        analysis_parts = []
        
        # Add document overview
        file_info = metadata.get("file_metadata", {})
        if file_info:
            analysis_parts.append(f"Document: {file_info.get('file_name', 'Unknown')}")
            analysis_parts.append(f"Type: {file_info.get('file_description', 'Unknown')}")
            analysis_parts.append("")
        
        # Add chunks with clear separation
        for chunk in chunk_data:
            chunk_header = f"--- Chunk {chunk['chunk_id']} ({chunk['word_count']} words) ---"
            analysis_parts.append(chunk_header)
            analysis_parts.append(chunk['content'])
            analysis_parts.append("")
        
        return "\\n".join(analysis_parts)
    
    def _get_child_service_info(self) -> Optional[Dict[str, Any]]:
        """Provide debugging information."""
        return {
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "preserve_paragraphs": self.preserve_paragraphs,
            "preserve_sentences": self.preserve_sentences
        }
```

## Step 8: Run the Document Analyzer

Execute your document analyzer:

```bash
# Create data directory and sample document if not exists
mkdir -p data

# Run the analyzer
agentmap run --graph DocAnalyzer --csv document_analyzer.csv
```

## Expected Output

The analyzer will process your document and provide comprehensive insights:

```
Enter the path to your document (or press Enter for sample): [Press Enter]

Using sample document for analysis...

📊 Document Analysis Report

=== DOCUMENT OVERVIEW ===
File: sample_document.txt (7.2 KB)
Type: Plain Text Document
Processing Method: Direct text extraction

=== STRUCTURE ANALYSIS ===
- 847 words in 42 sentences
- 6 main headers identified
- 23 paragraphs with structured content
- Moderate reading difficulty (Flesch Score: 45.2)

=== AI-POWERED INSIGHTS ===

**Key Themes Identified:**
1. **Strong Financial Performance** - 23% revenue growth reaching $4.2M
2. **Market Expansion Success** - European market entry with new partnerships
3. **Operational Challenges** - Supply chain and employee retention issues
4. **Strategic Planning** - Clear Q3 targets and investment priorities

**Important Metrics:**
- Revenue: $4.2M (+23% growth)
- Customer Satisfaction: 4.7/5.0
- Market Share: 8% (up from 6%)
- Employee Turnover: 18% (concern area)

**Sentiment Analysis:** 
Overall positive (72% positive sentiment) with acknowledgment of challenges and realistic planning for improvements.

=== ENTITY EXTRACTION ===

**Financial Metrics:**
- Revenue: $4.2M, $4.8M (target), $20M (annual goal)
- Investments: $2M (infrastructure), $1.5M (expansion)
- Profit Margins: 68% (gross), 16% (operating)

**Geographic Locations:**
- Germany, France, UK (new markets)
- Berlin (satellite office)
- Asia-Pacific (exploration target)

**Key People/Roles:**
- Business Analytics Team (report authors)
- Executive Team (strategic decision makers)

=== EXECUTIVE SUMMARY ===

This quarterly business report demonstrates strong organizational performance with 23% revenue growth and successful European market expansion. Key strengths include high customer satisfaction (4.7/5) and effective product development initiatives.

**Critical Success Factors:**
- Revenue diversification across products (74%), services (19%), and licensing (7%)
- Strong market position with 8% market share growth
- Successful international expansion into three European markets

**Areas Requiring Attention:**
- Supply chain reliability (affecting 15% of orders)
- Employee retention (18% turnover above optimal)
- Technical infrastructure stability (server downtime incidents)

**Strategic Recommendations:**
1. Prioritize supply chain optimization investments
2. Implement enhanced employee retention programs
3. Accelerate technical infrastructure improvements
4. Continue aggressive but measured market expansion

The company is well-positioned for achieving the ambitious $20M annual revenue target through disciplined execution of identified strategic priorities.

=== EXPORT RESULTS ===
✅ Analysis saved to: outputs/document_analysis_20240625_143022.json
✅ Summary report: outputs/analysis_report_20240625_143022.md
✅ Entity data: outputs/entities_20240625_143022.csv

Analysis complete! 📋
```

## Common Issues & Solutions

### 🚨 Issue: "PyPDF2 not found"
**Solution**: Install PDF processing library:
```bash
pip install PyPDF2
```

### 🚨 Issue: "python-docx not found"
**Solution**: Install DOCX processing library:
```bash
pip install python-docx
```

### 🚨 Issue: "File not found"
**Solution**: 
- Ensure sample document exists in data/
- Use absolute file paths
- Check file permissions

### 🚨 Issue: "Text extraction fails"
**Solution**:
- Try different file formats
- Check file corruption
- Use sample document to test

### 🚨 Issue: "AI analysis timeout"
**Solution**:
- Reduce chunk size in configuration
- Use smaller documents for testing
- Check API key and credits

## Enhancements & Next Steps

### 🎯 **Beginner Enhancements**
1. **Support more formats**: Add RTF, HTML, XML support
2. **Batch processing**: Analyze multiple documents at once
3. **Custom templates**: Create industry-specific analysis templates
4. **Export options**: Add PDF and Excel export formats

### 🎯 **Intermediate Enhancements**
1. **Advanced NLP**: Implement topic modeling and keyword extraction
2. **Comparative analysis**: Compare multiple documents
3. **Visual analytics**: Add charts and visualizations
4. **Database integration**: Store analysis results in database

### 🎯 **Advanced Enhancements**
1. **Machine learning**: Train custom models for document classification
2. **OCR integration**: Process scanned documents and images
3. **Real-time processing**: Web interface for document upload
4. **API development**: RESTful API for document analysis service

## Related Tutorials

- **[Data Processing Pipeline](./data-processing-pipeline)** - Learn structured data analysis
- **[Customer Support Bot](./customer-support-bot)** - Build conversational AI systems
- **[API Integration](./api-integration)** - Connect to external services

---

**🎉 Congratulations!** You've built a sophisticated document analyzer that can process multiple file formats, extract meaningful insights using AI, and generate comprehensive reports. This tutorial demonstrates advanced file processing, content analysis, and AI integration with AgentMap.
