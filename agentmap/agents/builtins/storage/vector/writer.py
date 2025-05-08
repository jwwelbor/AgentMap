from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent

class VectorWriterAgent(VectorAgent):
    """Agent for storing documents in vector databases"""
    
    def __init__(self, name, prompt, context=None):
        super().__init__(name, prompt, context)
        self.should_persist = context.get("should_persist", True) if context else True
    
    def process(self, inputs):
        """Store documents in vector database"""
        # Check for LangChain availability
        if not self._check_langchain():
            return {"error": "LangChain not installed. Install with 'pip install langchain langchain-openai'"}
        
        # Get vector store
        vector_store = self._get_or_create_vectorstore(inputs)
        if isinstance(vector_store, dict) and "error" in vector_store:
            return vector_store  # Return error if vector store creation failed
        
        # Get documents from inputs
        docs = inputs.get(self.input_fields[0])
        if not docs:
            return {"error": "No documents provided"}
        
        try:
            # Handle different document formats
            if hasattr(docs, 'page_content'):  # Single LangChain document
                ids = vector_store.add_documents([docs])
            elif isinstance(docs, list) and docs and hasattr(docs[0], 'page_content'):
                ids = vector_store.add_documents(docs)
            else:
                # Convert to text and add
                if not isinstance(docs, list):
                    docs = [docs]
                ids = vector_store.add_texts([str(doc) for doc in docs])
            
            # Persist changes
            if self.should_persist and hasattr(vector_store, "persist"):
                vector_store.persist()
                
            return {
                "status": "success",
                "stored_count": len(docs) if isinstance(docs, list) else 1,
                "ids": ids
            }
        except Exception as e:
            return {"error": f"Failed to store documents: {str(e)}"}