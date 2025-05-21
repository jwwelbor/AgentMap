"""
Direct imports from LangChain packages.

This module provides direct imports from the latest LangChain packages
without any compatibility layers or fallbacks.
"""

# Document loaders
from langchain_community.document_loaders import (
    CSVLoader, TextLoader, PyPDFLoader, DirectoryLoader,
    UnstructuredFileLoader, Docx2txtLoader, JSONLoader
)

# Memory classes
from langchain.memory import (
    ConversationBufferMemory, 
    ConversationBufferWindowMemory,
    ConversationSummaryMemory, 
    ConversationTokenBufferMemory
)