---
sidebar_position: 4
title: Building a RAG Chatbot
description: Create an intelligent RAG (Retrieval Augmented Generation) chatbot using AgentMap with vector databases, document ingestion, and conversational AI.
keywords: [RAG chatbot, retrieval augmented generation, vector database, document chat, AI chatbot, conversational AI, AgentMap tutorial]
---

# Building a RAG Chatbot with AgentMap

Learn how to build a sophisticated RAG (Retrieval Augmented Generation) chatbot that can answer questions about your documents using vector databases and large language models. This tutorial demonstrates AgentMap's powerful capabilities for building intelligent, context-aware AI systems.

## What is RAG?

RAG (Retrieval Augmented Generation) combines the power of information retrieval with generative AI to create chatbots that can:
- Answer questions about specific documents or knowledge bases
- Provide accurate, contextual responses with source attribution
- Handle large document collections efficiently
- Maintain conversation context and memory

## Architecture Overview

Our RAG chatbot will consist of several specialized agents:

1. **Document Ingestion Agent** - Processes and chunks documents
2. **Vector Storage Agent** - Stores document embeddings in vector database
3. **Query Processing Agent** - Handles user questions and retrieval
4. **Context Assembly Agent** - Combines retrieved documents with queries
5. **Response Generation Agent** - Generates final answers using LLM
6. **Conversation Memory Agent** - Maintains chat history and context

## Prerequisites

### Required Dependencies

```bash
pip install openai pinecone-client chromadb sentence-transformers
pip install pypdf2 python-docx markdown beautifulsoup4
```

### Environment Setup

```bash
# OpenAI API for LLM
export OPENAI_API_KEY="your_openai_api_key"

# Vector Database (choose one)
export PINECONE_API_KEY="your_pinecone_api_key"
export PINECONE_ENVIRONMENT="your_pinecone_environment"

# Or use local ChromaDB (no API key needed)
export VECTOR_DB_TYPE="chroma"  # or "pinecone"
```

## Step 1: Document Ingestion System

### Document Processing Agent

```python
import os
import hashlib
from pathlib import Path
from typing import List, Dict
import PyPDF2
import docx
import markdown
from bs4 import BeautifulSoup
from agentmap.agents import BaseAgent

class DocumentIngestionAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.supported_formats = {'.pdf', '.docx', '.txt', '.md', '.html'}
        self.chunk_size = 1000
        self.chunk_overlap = 200
    
    def execute(self, input_data, context=None):
        """
        Process documents and extract text chunks
        
        Input: File path or directory path
        Context: chunk_size, chunk_overlap, file_filters
        """
        file_path = input_data
        chunk_size = context.get('chunk_size', self.chunk_size)
        chunk_overlap = context.get('chunk_overlap', self.chunk_overlap)
        
        if os.path.isfile(file_path):
            documents = [self.process_single_file(file_path, chunk_size, chunk_overlap)]
        elif os.path.isdir(file_path):
            documents = self.process_directory(file_path, chunk_size, chunk_overlap)
        else:
            raise ValueError(f"Invalid path: {file_path}")
        
        return {
            'documents': documents,
            'total_chunks': sum(len(doc['chunks']) for doc in documents),
            'processed_files': len(documents)
        }
    
    def process_single_file(self, file_path: str, chunk_size: int, chunk_overlap: int) -> Dict:
        """Process a single file and return document chunks"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension not in self.supported_formats:
            raise ValueError(f"Unsupported file format: {file_extension}")
        
        # Extract text based on file type
        if file_extension == '.pdf':
            text = self.extract_pdf_text(file_path)
        elif file_extension == '.docx':
            text = self.extract_docx_text(file_path)
        elif file_extension == '.md':
            text = self.extract_markdown_text(file_path)
        elif file_extension == '.html':
            text = self.extract_html_text(file_path)
        else:  # .txt
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        
        # Create document chunks
        chunks = self.create_chunks(text, chunk_size, chunk_overlap)
        
        return {
            'file_path': file_path,
            'file_name': Path(file_path).name,
            'file_type': file_extension,
            'total_length': len(text),
            'chunks': chunks,
            'metadata': {
                'source': file_path,
                'processed_at': datetime.now().isoformat(),
                'chunk_count': len(chunks)
            }
        }
    
    def extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF file"""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX file"""
        doc = docx.Document(file_path)
        return "\n".join([paragraph.text for paragraph in doc.paragraphs])
    
    def extract_markdown_text(self, file_path: str) -> str:
        """Extract text from Markdown file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        # Convert markdown to HTML then extract text
        html = markdown.markdown(md_content)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text()
    
    def extract_html_text(self, file_path: str) -> str:
        """Extract text from HTML file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        soup = BeautifulSoup(html_content, 'html.parser')
        return soup.get_text()
    
    def create_chunks(self, text: str, chunk_size: int, overlap: int) -> List[Dict]:
        """Split text into overlapping chunks"""
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            
            # Try to break at sentence boundaries
            if end < len(text):
                last_period = chunk_text.rfind('.')
                last_newline = chunk_text.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > start + chunk_size * 0.5:  # Don't break too early
                    end = start + break_point + 1
                    chunk_text = text[start:end]
            
            # Create chunk with metadata
            chunk_id = hashlib.md5(chunk_text.encode()).hexdigest()
            chunks.append({
                'id': chunk_id,
                'text': chunk_text.strip(),
                'start_index': start,
                'end_index': end,
                'length': len(chunk_text)
            })
            
            start = end - overlap
        
        return chunks
    
    def process_directory(self, dir_path: str, chunk_size: int, chunk_overlap: int) -> List[Dict]:
        """Process all supported files in a directory"""
        documents = []
        
        for file_path in Path(dir_path).rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_formats:
                try:
                    doc = self.process_single_file(str(file_path), chunk_size, chunk_overlap)
                    documents.append(doc)
                except Exception as e:
                    self.logger.error(f"Error processing {file_path}: {str(e)}")
        
        return documents
```

## Step 2: Vector Storage System

### Vector Database Agent

```python
import openai
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
import pinecone

class VectorStorageAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.db_type = os.getenv('VECTOR_DB_TYPE', 'chroma')
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize vector database
        if self.db_type == 'pinecone':
            self.init_pinecone()
        else:
            self.init_chroma()
    
    def init_pinecone(self):
        """Initialize Pinecone vector database"""
        pinecone.init(
            api_key=os.getenv('PINECONE_API_KEY'),
            environment=os.getenv('PINECONE_ENVIRONMENT')
        )
        
        index_name = "agentmap-rag-chatbot"
        
        # Create index if it doesn't exist
        if index_name not in pinecone.list_indexes():
            pinecone.create_index(
                name=index_name,
                dimension=384,  # all-MiniLM-L6-v2 dimension
                metric='cosine'
            )
        
        self.index = pinecone.Index(index_name)
    
    def init_chroma(self):
        """Initialize ChromaDB vector database"""
        self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.chroma_client.get_or_create_collection(
            name="rag_documents"
        )
    
    def execute(self, input_data, context=None):
        """
        Store document chunks in vector database
        
        Input: Document processing results from DocumentIngestionAgent
        """
        documents_data = input_data['documents']
        operation = context.get('operation', 'store')  # store, query, delete
        
        if operation == 'store':
            return self.store_documents(documents_data)
        elif operation == 'query':
            query_text = context.get('query_text')
            top_k = context.get('top_k', 5)
            return self.query_similar_chunks(query_text, top_k)
        elif operation == 'delete':
            collection_name = context.get('collection_name', 'all')
            return self.delete_documents(collection_name)
    
    def store_documents(self, documents_data: List[Dict]) -> Dict:
        """Store document chunks in vector database"""
        total_stored = 0
        
        for doc in documents_data:
            chunks = doc['chunks']
            
            # Prepare chunk data for storage
            texts = [chunk['text'] for chunk in chunks]
            embeddings = self.embedding_model.encode(texts)
            
            # Create metadata for each chunk
            metadatas = []
            ids = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc['file_name']}_{chunk['id']}"
                ids.append(chunk_id)
                
                metadata = {
                    'source_file': doc['file_name'],
                    'file_path': doc['file_path'],
                    'file_type': doc['file_type'],
                    'chunk_index': i,
                    'start_index': chunk['start_index'],
                    'end_index': chunk['end_index'],
                    'length': chunk['length']
                }
                metadatas.append(metadata)
            
            # Store in vector database
            if self.db_type == 'pinecone':
                # Prepare vectors for Pinecone
                vectors = []
                for i, embedding in enumerate(embeddings):
                    vectors.append({
                        'id': ids[i],
                        'values': embedding.tolist(),
                        'metadata': metadatas[i]
                    })
                
                # Upsert in batches
                batch_size = 100
                for i in range(0, len(vectors), batch_size):
                    batch = vectors[i:i + batch_size]
                    self.index.upsert(vectors=batch)
            
            else:  # ChromaDB
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings.tolist(),
                    documents=texts,
                    metadatas=metadatas
                )
            
            total_stored += len(chunks)
        
        return {
            'status': 'success',
            'total_chunks_stored': total_stored,
            'documents_processed': len(documents_data)
        }
    
    def query_similar_chunks(self, query_text: str, top_k: int = 5) -> Dict:
        """Query for similar document chunks"""
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query_text])
        
        if self.db_type == 'pinecone':
            # Query Pinecone
            results = self.index.query(
                vector=query_embedding[0].tolist(),
                top_k=top_k,
                include_metadata=True
            )
            
            similar_chunks = []
            for match in results['matches']:
                similar_chunks.append({
                    'id': match['id'],
                    'score': match['score'],
                    'text': match['metadata'].get('text', ''),
                    'metadata': match['metadata']
                })
        
        else:  # ChromaDB
            results = self.collection.query(
                query_embeddings=query_embedding.tolist(),
                n_results=top_k
            )
            
            similar_chunks = []
            for i in range(len(results['ids'][0])):
                similar_chunks.append({
                    'id': results['ids'][0][i],
                    'score': 1 - results['distances'][0][i],  # Convert distance to similarity
                    'text': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i]
                })
        
        return {
            'query': query_text,
            'similar_chunks': similar_chunks,
            'total_results': len(similar_chunks)
        }
```

## Step 3: Query Processing and Response Generation

### RAG Query Agent

```python
class RAGQueryAgent(BaseAgent):
    def __init__(self, services=None):
        super().__init__(services)
        self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.max_context_length = 4000
        self.conversation_memory = []
    
    def execute(self, input_data, context=None):
        """
        Process user query and generate RAG response
        
        Input: User question/query
        Context: conversation_history, system_prompt, model_settings
        """
        user_query = input_data
        conversation_history = context.get('conversation_history', [])
        system_prompt = context.get('system_prompt', self.get_default_system_prompt())
        model = context.get('model', 'gpt-3.5-turbo')
        
        # Step 1: Retrieve relevant documents
        retrieval_results = self.retrieve_relevant_context(user_query)
        
        # Step 2: Assemble context with retrieved documents
        context_text = self.assemble_context(retrieval_results['similar_chunks'])
        
        # Step 3: Generate response using LLM
        response = self.generate_response(
            user_query, 
            context_text, 
            conversation_history,
            system_prompt,
            model
        )
        
        # Step 4: Update conversation memory
        self.update_conversation_memory(user_query, response, retrieval_results)
        
        return {
            'user_query': user_query,
            'response': response,
            'sources': self.extract_sources(retrieval_results['similar_chunks']),
            'context_used': len(retrieval_results['similar_chunks']),
            'conversation_length': len(self.conversation_memory)
        }
    
    def retrieve_relevant_context(self, query: str) -> Dict:
        """Retrieve relevant document chunks for the query"""
        # Use VectorStorageAgent to find similar chunks
        vector_agent = VectorStorageAgent()
        
        return vector_agent.execute(
            input_data={'documents': []},  # Not used for query operation
            context={
                'operation': 'query',
                'query_text': query,
                'top_k': 5
            }
        )
    
    def assemble_context(self, similar_chunks: List[Dict]) -> str:
        """Assemble retrieved chunks into context text"""
        context_parts = []
        current_length = 0
        
        for chunk in similar_chunks:
            chunk_text = chunk['text']
            chunk_length = len(chunk_text)
            
            # Check if adding this chunk would exceed context limit
            if current_length + chunk_length > self.max_context_length:
                break
            
            # Add source information
            source_info = f"[Source: {chunk['metadata']['source_file']}]"
            context_part = f"{source_info}\n{chunk_text}\n"
            
            context_parts.append(context_part)
            current_length += len(context_part)
        
        return "\n---\n".join(context_parts)
    
    def generate_response(self, query: str, context: str, history: List, system_prompt: str, model: str) -> str:
        """Generate response using OpenAI LLM"""
        
        # Prepare conversation history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (last 5 exchanges to manage context)
        for exchange in history[-5:]:
            messages.append({"role": "user", "content": exchange['user']})
            messages.append({"role": "assistant", "content": exchange['assistant']})
        
        # Add current query with context
        user_message = f"""Context information:
{context}

Question: {query}

Please answer the question based on the provided context. If the context doesn't contain enough information to answer the question, please say so."""
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def get_default_system_prompt(self) -> str:
        """Default system prompt for RAG chatbot"""
        return """You are a helpful AI assistant that answers questions based on provided context information. 

Guidelines:
- Always base your answers on the provided context
- If the context doesn't contain enough information, clearly state this
- Cite specific sources when possible
- Be concise but comprehensive
- If asked about something not in the context, politely explain that you need more information
- Maintain a friendly and professional tone"""
    
    def update_conversation_memory(self, query: str, response: str, retrieval_results: Dict):
        """Update conversation memory with current exchange"""
        self.conversation_memory.append({
            'user': query,
            'assistant': response,
            'sources': self.extract_sources(retrieval_results['similar_chunks']),
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep memory manageable (last 10 exchanges)
        if len(self.conversation_memory) > 10:
            self.conversation_memory = self.conversation_memory[-10:]
    
    def extract_sources(self, chunks: List[Dict]) -> List[Dict]:
        """Extract source information from retrieved chunks"""
        sources = []
        seen_sources = set()
        
        for chunk in chunks:
            source_file = chunk['metadata']['source_file']
            if source_file not in seen_sources:
                sources.append({
                    'file': source_file,
                    'file_path': chunk['metadata']['file_path'],
                    'relevance_score': chunk['score']
                })
                seen_sources.add(source_file)
        
        return sources
```

## Step 4: CSV Workflow Configuration

### Complete RAG Chatbot Workflow

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
RAGChatbot,InitializeSystem,,Initialize RAG system,echo,LoadDocuments,,collection,init_message,RAG Chatbot System Initializing...
RAGChatbot,LoadDocuments,,"{'chunk_size': 1000, 'chunk_overlap': 200}",document_ingestion,StoreVectors,ErrorHandler,collection,documents_data,
RAGChatbot,StoreVectors,,"{'operation': 'store'}",vector_storage,StartChat,ErrorHandler,documents_data,storage_result,
RAGChatbot,StartChat,,Ready for user interaction,echo,ProcessQuery,,storage_result,chat_ready,RAG Chatbot ready! Ask me anything about your documents.
RAGChatbot,ProcessQuery,,"{'conversation_history': [], 'model': 'gpt-3.5-turbo'}",rag_query,FormatResponse,ErrorHandler,collection,rag_response,
RAGChatbot,FormatResponse,,Format final response with sources,echo,WaitForNextQuery,,rag_response,formatted_response,
RAGChatbot,WaitForNextQuery,,Wait for next user input,input,ProcessQuery,,collection,user_input,Enter your question:
RAGChatbot,ErrorHandler,,Handle system errors,echo,StartChat,,error,error_message,Error occurred: {error}. Please try again.
```

### Interactive Chat Workflow

```csv
GraphName,Node,Edge,Context,AgentType,Success_Next,Failure_Next,Input_Fields,Output_Field,Prompt
ChatSession,WelcomeUser,,Welcome message,echo,GetUserQuery,,collection,welcome_msg,Welcome to AgentMap RAG Chatbot! What would you like to know?
ChatSession,GetUserQuery,,Get user question,input,ProcessRAGQuery,,collection,user_query,Your question:
ChatSession,ProcessRAGQuery,,"{'model': 'gpt-4', 'system_prompt': 'You are a helpful document assistant.'}",rag_query,DisplayResponse,ErrorHandler,user_query,response_data,
ChatSession,DisplayResponse,,Show response and sources,echo,ContinueChat,,response_data,display_result,
ChatSession,ContinueChat,,Ask if user wants to continue,input,CheckContinue,,display_result,continue_choice,Would you like to ask another question? (yes/no):
ChatSession,CheckContinue,,Check if user wants to continue,branching,GetUserQuery,EndChat,continue_choice,routing_decision,
ChatSession,EndChat,,End chat session,echo,,,routing_decision,goodbye_msg,Thank you for using AgentMap RAG Chatbot! Goodbye!
ChatSession,ErrorHandler,,Handle chat errors,echo,GetUserQuery,,error,error_msg,I apologize, but I encountered an error: {error}. Please try asking your question again.
```

## Step 5: Setup and Execution

### Agent Registration

```python
from agentmap import AgentMap

# Create AgentMap instance
agent_map = AgentMap()

# Register custom RAG agents
agent_map.register_agent_type('document_ingestion', DocumentIngestionAgent)
agent_map.register_agent_type('vector_storage', VectorStorageAgent)
agent_map.register_agent_type('rag_query', RAGQueryAgent)

# Initialize RAG system with documents
print("Initializing RAG Chatbot...")
result = agent_map.execute_csv(
    'rag_setup.csv', 
    initial_input='./documents'  # Path to your document directory
)

print("Setup complete! Starting chat session...")

# Start interactive chat
chat_result = agent_map.execute_csv('chat_session.csv')
```

### Document Preparation Script

```python
def prepare_documents_for_rag(documents_path: str):
    """Prepare documents for RAG system"""
    
    # Create AgentMap instance
    agent_map = AgentMap()
    agent_map.register_agent_type('document_ingestion', DocumentIngestionAgent)
    agent_map.register_agent_type('vector_storage', VectorStorageAgent)
    
    print(f"Processing documents from: {documents_path}")
    
    # Process documents
    ingestion_agent = DocumentIngestionAgent()
    documents_result = ingestion_agent.execute(
        documents_path,
        context={'chunk_size': 1000, 'chunk_overlap': 200}
    )
    
    print(f"Processed {documents_result['processed_files']} files")
    print(f"Created {documents_result['total_chunks']} text chunks")
    
    # Store in vector database
    storage_agent = VectorStorageAgent()
    storage_result = storage_agent.execute(
        documents_result,
        context={'operation': 'store'}
    )
    
    print(f"Stored {storage_result['total_chunks_stored']} chunks in vector database")
    print("RAG system ready for queries!")
    
    return storage_result

# Example usage
if __name__ == "__main__":
    # Prepare your documents
    prepare_documents_for_rag('./my_documents')
    
    # Start chatbot
    print("\n" + "="*50)
    print("RAG CHATBOT READY")
    print("="*50)
    
    agent_map = AgentMap()
    agent_map.register_agent_type('rag_query', RAGQueryAgent)
    
    # Interactive chat loop
    rag_agent = RAGQueryAgent()
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("Chatbot: Goodbye!")
            break
        
        response = rag_agent.execute(user_input)
        print(f"\nChatbot: {response['response']}")
        
        if response['sources']:
            print("\nSources:")
            for source in response['sources']:
                print(f"  - {source['file']} (relevance: {source['relevance_score']:.2f})")
```

## Advanced Features

### 1. Multi-Modal Document Support

```python
class MultiModalIngestionAgent(DocumentIngestionAgent):
    def extract_image_text(self, image_path: str) -> str:
        """Extract text from images using OCR"""
        import pytesseract
        from PIL import Image
        
        image = Image.open(image_path)
        return pytesseract.image_to_string(image)
    
    def process_single_file(self, file_path: str, chunk_size: int, chunk_overlap: int):
        """Enhanced to handle images"""
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension in {'.jpg', '.jpeg', '.png', '.tiff'}:
            text = self.extract_image_text(file_path)
            chunks = self.create_chunks(text, chunk_size, chunk_overlap)
            
            return {
                'file_path': file_path,
                'file_name': Path(file_path).name,
                'file_type': file_extension,
                'total_length': len(text),
                'chunks': chunks,
                'metadata': {
                    'source': file_path,
                    'content_type': 'image_ocr',
                    'processed_at': datetime.now().isoformat()
                }
            }
        else:
            return super().process_single_file(file_path, chunk_size, chunk_overlap)
```

### 2. Question Classification

```python
class QuestionClassifierAgent(BaseAgent):
    def execute(self, input_data, context=None):
        """Classify user questions to improve retrieval"""
        question = input_data
        
        # Simple rule-based classification
        question_lower = question.lower()
        
        if any(word in question_lower for word in ['how', 'process', 'steps', 'procedure']):
            question_type = 'procedural'
        elif any(word in question_lower for word in ['what', 'define', 'definition', 'meaning']):
            question_type = 'definitional'
        elif any(word in question_lower for word in ['why', 'reason', 'because', 'cause']):
            question_type = 'causal'
        elif any(word in question_lower for word in ['when', 'time', 'date', 'schedule']):
            question_type = 'temporal'
        else:
            question_type = 'general'
        
        return {
            'question': question,
            'question_type': question_type,
            'enhanced_query': self.enhance_query_for_type(question, question_type)
        }
    
    def enhance_query_for_type(self, question: str, question_type: str) -> str:
        """Enhance query based on question type"""
        if question_type == 'procedural':
            return f"steps process procedure {question}"
        elif question_type == 'definitional':
            return f"definition meaning concept {question}"
        elif question_type == 'causal':
            return f"reason why cause because {question}"
        elif question_type == 'temporal':
            return f"time when date schedule {question}"
        else:
            return question
```

### 3. Response Quality Evaluation

```python
class ResponseEvaluationAgent(BaseAgent):
    def execute(self, input_data, context=None):
        """Evaluate response quality and provide feedback"""
        response_data = input_data
        
        user_query = response_data['user_query']
        response = response_data['response']
        sources = response_data['sources']
        
        # Evaluate different aspects
        relevance_score = self.evaluate_relevance(user_query, response)
        completeness_score = self.evaluate_completeness(response)
        source_quality_score = self.evaluate_source_quality(sources)
        
        overall_score = (relevance_score + completeness_score + source_quality_score) / 3
        
        return {
            'overall_score': overall_score,
            'relevance_score': relevance_score,
            'completeness_score': completeness_score,
            'source_quality_score': source_quality_score,
            'feedback': self.generate_feedback(overall_score),
            'response_data': response_data
        }
    
    def evaluate_relevance(self, query: str, response: str) -> float:
        """Simple relevance evaluation based on keyword overlap"""
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        
        overlap = len(query_words.intersection(response_words))
        total_query_words = len(query_words)
        
        return min(overlap / total_query_words, 1.0) if total_query_words > 0 else 0.0
    
    def evaluate_completeness(self, response: str) -> float:
        """Evaluate response completeness based on length and structure"""
        word_count = len(response.split())
        
        if word_count < 10:
            return 0.3
        elif word_count < 50:
            return 0.6
        elif word_count < 100:
            return 0.8
        else:
            return 1.0
    
    def evaluate_source_quality(self, sources: List[Dict]) -> float:
        """Evaluate quality of retrieved sources"""
        if not sources:
            return 0.0
        
        # Average relevance score of sources
        total_score = sum(source['relevance_score'] for source in sources)
        return total_score / len(sources)
    
    def generate_feedback(self, score: float) -> str:
        """Generate feedback based on overall score"""
        if score >= 0.8:
            return "Excellent response quality"
        elif score >= 0.6:
            return "Good response quality"
        elif score >= 0.4:
            return "Moderate response quality - could be improved"
        else:
            return "Poor response quality - needs improvement"
```

## Testing and Evaluation

### Unit Tests

```python
import unittest
from unittest.mock import Mock, patch

class TestRAGChatbot(unittest.TestCase):
    def setUp(self):
        self.ingestion_agent = DocumentIngestionAgent()
        self.vector_agent = VectorStorageAgent()
        self.rag_agent = RAGQueryAgent()
    
    def test_document_ingestion(self):
        # Test with sample text file
        test_file = 'test_document.txt'
        with open(test_file, 'w') as f:
            f.write("This is a test document for RAG chatbot testing.")
        
        result = self.ingestion_agent.execute(test_file)
        
        self.assertEqual(result['processed_files'], 1)
        self.assertGreater(result['total_chunks'], 0)
        
        # Cleanup
        os.remove(test_file)
    
    @patch('openai.OpenAI')
    def test_rag_query_generation(self, mock_openai):
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices[0].message.content = "This is a test response."
        mock_openai.return_value.chat.completions.create.return_value = mock_response
        
        # Test query processing
        result = self.rag_agent.execute("What is AgentMap?")
        
        self.assertIn('response', result)
        self.assertIn('sources', result)
        self.assertEqual(result['response'], "This is a test response.")
```

### Performance Metrics

```python
import time
import psutil
import tracemalloc

class RAGPerformanceMonitor:
    def __init__(self):
        self.metrics = {}
    
    def measure_ingestion_performance(self, documents_path: str):
        """Measure document ingestion performance"""
        tracemalloc.start()
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        # Run ingestion
        agent = DocumentIngestionAgent()
        result = agent.execute(documents_path)
        
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        self.metrics['ingestion'] = {
            'processing_time': end_time - start_time,
            'memory_used': (end_memory - start_memory) / 1024 / 1024,  # MB
            'peak_memory': peak_memory / 1024 / 1024,  # MB
            'documents_processed': result['processed_files'],
            'chunks_created': result['total_chunks'],
            'throughput': result['total_chunks'] / (end_time - start_time)
        }
    
    def measure_query_performance(self, queries: List[str]):
        """Measure query processing performance"""
        agent = RAGQueryAgent()
        
        total_time = 0
        successful_queries = 0
        
        for query in queries:
            start_time = time.time()
            try:
                result = agent.execute(query)
                end_time = time.time()
                total_time += (end_time - start_time)
                successful_queries += 1
            except Exception as e:
                print(f"Query failed: {query}, Error: {e}")
        
        self.metrics['query'] = {
            'total_queries': len(queries),
            'successful_queries': successful_queries,
            'average_response_time': total_time / successful_queries if successful_queries > 0 else 0,
            'success_rate': successful_queries / len(queries)
        }
    
    def generate_report(self):
        """Generate performance report"""
        print("RAG Chatbot Performance Report")
        print("=" * 40)
        
        if 'ingestion' in self.metrics:
            ing = self.metrics['ingestion']
            print(f"Document Ingestion:")
            print(f"  Processing Time: {ing['processing_time']:.2f} seconds")
            print(f"  Memory Used: {ing['memory_used']:.2f} MB")
            print(f"  Peak Memory: {ing['peak_memory']:.2f} MB")
            print(f"  Documents Processed: {ing['documents_processed']}")
            print(f"  Chunks Created: {ing['chunks_created']}")
            print(f"  Throughput: {ing['throughput']:.2f} chunks/second")
        
        if 'query' in self.metrics:
            qry = self.metrics['query']
            print(f"\nQuery Processing:")
            print(f"  Total Queries: {qry['total_queries']}")
            print(f"  Successful Queries: {qry['successful_queries']}")
            print(f"  Success Rate: {qry['success_rate']:.1%}")
            print(f"  Average Response Time: {qry['average_response_time']:.2f} seconds")
```

## Deployment and Scaling

### Production Configuration

```python
# production_config.py
PRODUCTION_CONFIG = {
    'vector_db': {
        'type': 'pinecone',  # Use Pinecone for production
        'index_name': 'production-rag-chatbot',
        'dimension': 384,
        'metric': 'cosine',
        'pod_type': 'p1.x1'
    },
    'llm': {
        'model': 'gpt-4',
        'temperature': 0.7,
        'max_tokens': 500,
        'timeout': 30
    },
    'ingestion': {
        'chunk_size': 1000,
        'chunk_overlap': 200,
        'batch_size': 100,
        'max_file_size_mb': 50
    },
    'retrieval': {
        'top_k': 5,
        'min_similarity_threshold': 0.7,
        'rerank_results': True
    },
    'performance': {
        'cache_responses': True,
        'cache_ttl_hours': 24,
        'max_concurrent_queries': 10,
        'rate_limit_per_minute': 60
    }
}
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["python", "rag_chatbot_server.py"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  rag-chatbot:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - PINECONE_API_KEY=${PINECONE_API_KEY}
      - PINECONE_ENVIRONMENT=${PINECONE_ENVIRONMENT}
      - VECTOR_DB_TYPE=pinecone
    volumes:
      - ./documents:/app/documents
      - ./chroma_db:/app/chroma_db
    depends_on:
      - redis
  
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
```

This comprehensive RAG chatbot tutorial demonstrates AgentMap's power for building sophisticated AI systems. The modular agent architecture makes it easy to customize, test, and scale your chatbot for production use.

For more advanced RAG patterns and optimizations, see the [Multi-Agent Research Tutorial](/docs/tutorials/multi-agent-research) and [Advanced Agent Development Guide](/docs/guides/development/agents/agent-development).
