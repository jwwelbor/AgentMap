from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent

class VectorReaderAgent(VectorAgent):
    """Agent for searching vector databases with similarity search"""
    
    def __init__(self, name, prompt, context=None):
        super().__init__(name, prompt, context)
        self.k = int(context.get("k", 4)) if context else 4
    
    def process(self, inputs):
        """Search for documents similar to the query"""
        # Check for LangChain availability
        if not self._check_langchain():
            return {"error": "LangChain not installed. Install with 'pip install langchain langchain-openai'"}
        
        # Get vector store
        vector_store = self._get_or_create_vectorstore(inputs)
        if isinstance(vector_store, dict) and "error" in vector_store:
            return vector_store  # Return error if vector store creation failed
        
        # Get query from inputs
        query = inputs.get(self.input_fields[0])
        if not query:
            return {"error": "No query provided for vector search"}
            
        # Perform search
        try:
            results = vector_store.similarity_search(query, k=self.k)
            
            # Return formatted results
            return {
                "status": "success",
                "query": query,
                "results": [
                    {"content": doc.page_content, "metadata": doc.metadata}
                    for doc in results
                ]
            }
        except Exception as e:
            return {"error": f"Search failed: {str(e)}"}