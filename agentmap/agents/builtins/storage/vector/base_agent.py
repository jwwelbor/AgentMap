from agentmap.agents.base_agent import BaseAgent

import os

class VectorAgent(BaseAgent):
    """Base class for vector storage operations with LangChain"""
    
    def __init__(self, name, prompt, context=None):
        super().__init__(name, prompt, context or {})
        self.store_key = context.get("store_key", "_vector_store")
        self.persist_directory = context.get("persist_directory", "./.vectorstore")
        self.provider = context.get("provider", "chroma")
        self.embedding_model = context.get("embedding_model", "openai")
    
    def _check_langchain(self):
        """Check if LangChain is available"""
        try:
            import langchain
            return True
        except ImportError:
            return False
    
    def _get_or_create_vectorstore(self, inputs):
        """Get or create vector store based on configuration"""
        # Check if vector store exists in context
        if self.store_key in inputs:
            return inputs[self.store_key]
        
        # Get embeddings model
        embeddings = self._create_embeddings()
        if isinstance(embeddings, dict) and "error" in embeddings:
            return embeddings  # Return error if embedding creation failed
        
        # Create store based on provider
        provider = self.provider.lower()
        
        try:
            if provider == "chroma":
                return self._create_chroma_store(embeddings, inputs)
            elif provider == "faiss":
                return self._create_faiss_store(embeddings, inputs)
            else:
                return {"error": f"Unsupported vector store provider: {provider}"}
        except Exception as e:
            return {"error": f"Failed to initialize vector store: {str(e)}"}
    
    def _create_embeddings(self):
        """Create embeddings model based on configuration"""
        embedding_type = self.embedding_model.lower()
        
        try:
            if embedding_type == "openai":
                from langchain.embeddings import OpenAIEmbeddings
                return OpenAIEmbeddings()
            else:
                return {"error": f"Unsupported embedding model: {embedding_type}"}
        except Exception as e:
            return {"error": f"Failed to initialize embeddings: {str(e)}"}
    
    def _create_chroma_store(self, embeddings, inputs):
        """Create Chroma vector store"""
        try:
            from langchain.vectorstores import Chroma
            
            # Create directory if needed
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Create vector store
            vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=embeddings
            )
            
            # Store in context
            inputs[self.store_key] = vector_store
            
            return vector_store
        except ImportError:
            return {"error": "Chroma not installed. Install with 'pip install chromadb'"}
    
    def _create_faiss_store(self, embeddings, inputs):
        """Create FAISS vector store"""
        try:
            from langchain.vectorstores import FAISS
            
            # Create directory if needed
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Check if FAISS index already exists
            import os.path
            index_file = os.path.join(self.persist_directory, "index.faiss")
            
            if os.path.exists(index_file):
                # Load existing index
                vector_store = FAISS.load_local(self.persist_directory, embeddings)
            else:
                # Create empty index with a placeholder document
                vector_store = FAISS.from_texts(
                    ["This is a placeholder document for initialization"], 
                    embeddings
                )
                # Save the index
                vector_store.save_local(self.persist_directory)
            
            # Store in context
            inputs[self.store_key] = vector_store
            
            return vector_store
        except ImportError:
            return {"error": "FAISS not installed. Install with 'pip install faiss-cpu'"}