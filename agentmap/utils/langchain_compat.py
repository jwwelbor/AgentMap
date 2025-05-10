"""Compatibility layer for LangChain imports."""

# Document loaders
try:
    from langchain_community.document_loaders import (
        CSVLoader, TextLoader, PyPDFLoader, DirectoryLoader,
        UnstructuredFileLoader, Docx2txtLoader, JSONLoader
    )
except ImportError:
    try:
        from langchain.document_loaders import (
            CSVLoader, TextLoader, PyPDFLoader, DirectoryLoader,
            UnstructuredFileLoader, Docx2txtLoader, JSONLoader
        )
    except ImportError:
        # Define dummy classes if neither import works
        class DummyLoader:
            """Placeholder when loaders are not available."""
            def __init__(self, *args, **kwargs):
                raise ImportError("Document loaders not available. Please install langchain-community.")
                
        CSVLoader = TextLoader = PyPDFLoader = DirectoryLoader = \
        UnstructuredFileLoader = Docx2txtLoader = JSONLoader = DummyLoader

# Memory classes
try:
    from langchain.memory import (
        ConversationBufferMemory, ConversationBufferWindowMemory,
        ConversationSummaryMemory, ConversationTokenBufferMemory
    )
except ImportError:
    # Define dummy memory classes
    class DummyMemory:
        """Placeholder when memory classes are not available."""
        def __init__(self, *args, **kwargs):
            raise ImportError("Memory modules not available. Please install langchain.")
            
    ConversationBufferMemory = ConversationBufferWindowMemory = \
    ConversationSummaryMemory = ConversationTokenBufferMemory = DummyMemory