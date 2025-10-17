"""
File Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for file operations, refactored from FileReaderAgent and FileWriterAgent functionality.
Supports text files, binary files, and document formats via LangChain loaders.
"""

import mimetypes
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode


class FileStorageService(BaseStorageService):
    """
    File storage service implementation.

    Provides storage operations for various file formats including:
    - Text files (.txt, .md, .html, .csv, .log, .py, .js, .json, .yaml)
    - Document files (.pdf, .docx, .doc) via LangChain loaders
    - Binary files (.png, .jpg, .zip, etc.) for basic read/write
    """

    def __init__(
        self,
        provider_name: str,
        configuration: StorageConfigService,  # StorageConfigService (avoid circular import)
        logging_service: LoggingService,  # LoggingService (avoid circular import)
        file_path_service: FilePathService,
        base_directory: Optional[str] = None,
    ):
        """
        Initialize JSONStorageService.

        Args:
            provider_name: Name of the storage provider
            configuration: Storage configuration service
            logging_service: Logging service for creating loggers
            file_path_service: Optional file path service for path validation
            base_directory: Optional base directory for system storage operations
        """
        # Call parent's __init__ with all parameters for injection support
        super().__init__(
            provider_name,
            configuration,
            logging_service,
            file_path_service,
            base_directory,
        )

    def _initialize_client(self) -> Dict[str, Any]:
        """
        Initialize file system client configuration.

        Returns:
            Configuration dict for file operations

        Raises:
            OSError: If base directory cannot be created or accessed
        """
        # Handle system storage (dict configuration) vs user storage (StorageConfigService)
        if self.provider_name.startswith("system_file"):
            # System storage: use dict access on configuration
            base_dir = self.configuration["base_directory"]
            encoding = self.configuration.get("encoding", "utf-8")
            chunk_size = int(self.configuration.get("chunk_size", 1000))
            chunk_overlap = int(self.configuration.get("chunk_overlap", 200))
            should_split = self.configuration.get("should_split", False)
            include_metadata = self.configuration.get("include_metadata", True)
            newline = self.configuration.get("newline")
            allow_binary = self.configuration.get("allow_binary", True)
            max_file_size = self.configuration.get("max_file_size")
        else:
            # User storage: use get_file_config() to get config dict, then dict.get()
            file_config = self.configuration.get_file_config()
            base_dir = file_config.get("base_directory", "./data/files")
            encoding = file_config.get("encoding", "utf-8")
            chunk_size = int(file_config.get("chunk_size", 1000))
            chunk_overlap = int(file_config.get("chunk_overlap", 200))
            should_split = file_config.get("should_split", False)
            include_metadata = file_config.get("include_metadata", True)
            newline = file_config.get("newline")
            allow_binary = file_config.get("allow_binary", True)
            max_file_size = file_config.get("max_file_size")

        # Ensure base directory exists - fail fast if we can't create it
        try:
            os.makedirs(base_dir, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise OSError(f"Cannot create base directory '{base_dir}': {e}")

        # Extract configuration options (based on FileReaderAgent/FileWriterAgent context)
        config = {
            "base_directory": base_dir,
            "encoding": encoding,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "should_split": should_split,
            "include_metadata": include_metadata,
            "newline": newline,
            "allow_binary": allow_binary,
            "max_file_size": max_file_size,
        }

        return config

    def _perform_health_check(self) -> bool:
        """
        Perform health check for file storage.

        Checks if base directory is accessible and we can perform
        basic file operations.

        Returns:
            True if healthy, False otherwise
        """
        try:
            base_dir = self.client["base_directory"]

            # Check if directory exists and is accessible
            if not os.path.exists(base_dir):
                return False

            if not os.access(base_dir, os.W_OK | os.R_OK):
                return False

            # Test basic file operation
            test_file = os.path.join(base_dir, ".health_check_test.tmp")
            try:
                with open(test_file, "w", encoding=self.client["encoding"]) as f:
                    f.write("test")

                with open(test_file, "r", encoding=self.client["encoding"]) as f:
                    content = f.read()

                os.remove(test_file)
                return content == "test"
            except Exception:
                # Clean up test file if it exists
                if os.path.exists(test_file):
                    try:
                        os.remove(test_file)
                    except Exception:
                        pass
                return False

        except Exception as e:
            self._logger.debug(f"File health check failed: {e}")
            return False

    def _validate_file_path(self, file_path: str) -> str:
        """
        Validate file path is within base directory bounds (security).

        Enhanced validation that checks for path traversal attacks,
        absolute paths, and dangerous characters across all platforms.

        Args:
            file_path: Path to validate

        Returns:
            Validated and normalized path

        Raises:
            ValueError: If path tries to escape base directory
        """

        # Check for null bytes and other dangerous characters
        if "\0" in file_path:
            raise ValueError(
                f"Path {file_path} is outside base directory (contains null bytes)"
            )

        # Check for obvious directory traversal patterns
        # Normalize separators for cross-platform compatibility
        normalized_path = file_path.replace("\\", "/").replace("//", "/")

        # Check for parent directory references
        if "../" in normalized_path or normalized_path.startswith("../"):
            raise ValueError(
                f"Path {file_path} is outside base directory (contains directory traversal)"
            )

        # Check if it's an absolute path that's clearly outside our base
        if Path(file_path).is_absolute():
            # On Windows, check for different drive letters or system paths
            if os.name == "nt":
                # Block access to Windows system directories
                lower_path = file_path.lower()
                dangerous_windows_paths = [
                    "c:\\windows",
                    "c:\\program files",
                    "c:\\system32",
                    "/windows",
                    "/program files",
                    "/system32",
                ]
                for dangerous in dangerous_windows_paths:
                    if dangerous in lower_path:
                        raise ValueError(
                            f"Path {file_path} is outside base directory (system path)"
                        )
            else:
                # On Unix-like systems, block access to system directories
                dangerous_unix_paths = [
                    "/etc",
                    "/usr",
                    "/var",
                    "/bin",
                    "/sbin",
                    "/root",
                    "/sys",
                    "/proc",
                ]
                for dangerous in dangerous_unix_paths:
                    if (
                        normalized_path.startswith(dangerous + "/")
                        or normalized_path == dangerous
                    ):
                        raise ValueError(
                            f"Path {file_path} is outside base directory (system path)"
                        )

        # Get base directory and resolve it
        base_dir_path = Path(self.client["base_directory"])
        base_dir = base_dir_path.resolve()

        raw_path = Path(file_path)
        if raw_path.is_absolute():
            full_path = raw_path.resolve()
        else:
            try:
                relative_suffix = raw_path.relative_to(base_dir_path)
            except ValueError:
                relative_suffix = raw_path
            full_path = (base_dir / relative_suffix).resolve()

        try:
            # Check if the resolved path is within base directory
            full_path.relative_to(base_dir)
            return str(full_path)
        except ValueError:
            raise ValueError(f"Path {file_path} is outside base directory {base_dir}")

    def _resolve_file_path(
        self, collection: str, document_id: Optional[str] = None
    ) -> Path:
        """
        Resolve full file path from collection and document_id.

        Args:
            collection: Directory path (collection)
            document_id: Filename (document_id)

        Returns:
            Full file path
        """
        base_dir = Path(self.client["base_directory"])

        if document_id is None:
            # Collection only - treat as directory
            return base_dir / collection
        else:
            # Collection + document_id - treat as directory + filename
            return base_dir / collection / document_id

    def _ensure_directory(self, directory_path: Path) -> None:
        """
        Create directory if it doesn't exist.

        Args:
            directory_path: Path to directory
        """
        directory_path.mkdir(parents=True, exist_ok=True)

    def _is_text_file(self, file_path: str) -> bool:
        """
        Check if file is a supported text file (from FileWriterAgent).

        Args:
            file_path: Path to file

        Returns:
            True if supported text file, False otherwise
        """
        ext = Path(file_path).suffix.lower()
        text_extensions = [
            ".txt",
            ".md",
            ".html",
            ".htm",
            ".csv",
            ".log",
            ".py",
            ".js",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".rst",
        ]
        return ext in text_extensions

    def _is_binary_file(self, file_path: str) -> bool:
        """
        Check if file should be handled as binary.

        Args:
            file_path: Path to file

        Returns:
            True if binary file, False otherwise
        """
        if not self.client["allow_binary"]:
            return False

        ext = Path(file_path).suffix.lower()
        binary_extensions = [
            ".pdf",
            ".docx",
            ".doc",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".zip",
            ".tar",
            ".gz",
            ".exe",
            ".dll",
        ]
        return ext in binary_extensions

    def _get_file_loader(self, file_path: str) -> Any:
        """
        Get appropriate LangChain document loader (refactored from FileReaderAgent).

        Args:
            file_path: Path to the document file

        Returns:
            LangChain document loader instance

        Raises:
            ValueError: For unsupported file types
            ImportError: When dependencies for a file type aren't installed
        """
        file_ext = Path(file_path).suffix.lower()

        try:
            if file_ext == ".txt":
                from langchain_community.document_loaders import TextLoader

                return TextLoader(file_path)
            elif file_ext == ".pdf":
                from langchain_community.document_loaders import PyPDFLoader

                return PyPDFLoader(file_path)
            elif file_ext == ".md":
                from langchain_community.document_loaders import (
                    UnstructuredMarkdownLoader,
                )

                return UnstructuredMarkdownLoader(file_path)
            elif file_ext in [".html", ".htm"]:
                from langchain_community.document_loaders import UnstructuredHTMLLoader

                return UnstructuredHTMLLoader(file_path)
            elif file_ext in [".docx", ".doc"]:
                from langchain_community.document_loaders import (
                    UnstructuredWordDocumentLoader,
                )

                return UnstructuredWordDocumentLoader(file_path)
            elif file_ext == ".csv":
                from langchain_community.document_loaders import CSVLoader

                return CSVLoader(file_path)
            else:
                # Default to text loader for unknown types
                from langchain_community.document_loaders import TextLoader

                return TextLoader(file_path)
        except ImportError as e:
            self._logger.warning(f"LangChain document loaders not available ({e})")
            return self._create_fallback_loader(file_path)
        except Exception as e:
            raise ValueError(f"Error creating loader for {file_path}: {e}")

    def _create_fallback_loader(self, file_path: str) -> Any:
        """
        Create fallback loader when LangChain unavailable (from FileReaderAgent).

        Args:
            file_path: Path to the document file

        Returns:
            Simple loader object with a load method
        """

        # Define a simple Document class for fallback
        class SimpleDocument:
            def __init__(self, content: str, metadata: Optional[Dict] = None):
                self.page_content = content
                self.metadata = metadata or {"source": file_path}

        # Create a simple loader
        class FallbackLoader:
            def __init__(self, file_path: str):
                self.file_path = file_path

            def load(self) -> List[SimpleDocument]:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return [SimpleDocument(content)]

        return FallbackLoader(file_path)

    def _filter_by_id(self, documents: List[Any], document_id: str) -> List[Any]:
        """
        Filter documents by ID or index (from FileReaderAgent).

        Args:
            documents: List of documents
            document_id: Document ID or index

        Returns:
            Filtered document list
        """
        # Try to filter by metadata ID
        filtered = [
            doc
            for doc in documents
            if hasattr(doc, "metadata") and doc.metadata.get("id") == document_id
        ]

        # If no matches by ID, try as index if it's numeric
        if not filtered and document_id.isdigit():
            idx = int(document_id)
            if 0 <= idx < len(documents):
                return [documents[idx]]

        return filtered

    def _apply_document_path(self, documents: Union[List[Any], Any], path: str) -> Any:
        """
        Extract content from document(s) at specified path (from FileReaderAgent).

        Args:
            documents: Document or list of documents
            path: Path expression (e.g., "metadata.source" or "0.content")

        Returns:
            Content at specified path
        """
        if not path:
            return documents

        result = []

        # Handle single document case
        if not isinstance(documents, list):
            documents = [documents]

        for doc in documents:
            # Check for metadata paths
            if path.startswith("metadata.") and hasattr(doc, "metadata"):
                meta_key = path.split(".", 1)[1]
                if meta_key in doc.metadata:
                    result.append(doc.metadata[meta_key])
            # Default to page content
            elif hasattr(doc, "page_content"):
                result.append(doc.page_content)
            else:
                result.append(doc)

        return result

    def _apply_query_filter(
        self, documents: List[Any], query: Union[Dict[str, Any], str]
    ) -> List[Any]:
        """
        Filter documents based on query parameters (from FileReaderAgent).

        Args:
            documents: List of documents
            query: Query string or dictionary

        Returns:
            Filtered document list
        """
        if not documents:
            return []

        filtered_docs = []

        if isinstance(query, dict):
            # Filter by metadata
            for doc in documents:
                if not hasattr(doc, "metadata"):
                    continue

                matches = True
                for k, v in query.items():
                    if doc.metadata.get(k) != v:
                        matches = False
                        break

                if matches:
                    filtered_docs.append(doc)

        elif isinstance(query, str):
            # Simple text search in content
            for doc in documents:
                if not hasattr(doc, "page_content"):
                    continue

                if query.lower() in doc.page_content.lower():
                    filtered_docs.append(doc)

        return filtered_docs

    def _prepare_content(self, data: Any) -> Union[str, bytes]:
        """
        Convert data to writable content (from FileWriterAgent, minus state lookup).

        Args:
            data: Input data in various formats

        Returns:
            String or bytes content for writing
        """
        if hasattr(data, "page_content"):
            # Single LangChain document
            return data.page_content
        elif isinstance(data, list) and data and hasattr(data[0], "page_content"):
            # List of LangChain documents
            return "\n\n".join(doc.page_content for doc in data)
        elif isinstance(data, dict):
            # Try to extract content from dictionary
            if "content" in data:
                return str(data["content"])
            else:
                # Convert whole dict to string
                return str(data)
        elif isinstance(data, bytes):
            # Binary data
            return data
        else:
            # Convert to string directly
            return str(data)

    def _read_text_file(self, file_path: Path, **kwargs) -> str:
        """
        Read text file content.

        Args:
            file_path: Path to text file
            **kwargs: Additional parameters

        Returns:
            File content as string
        """
        encoding = kwargs.get("encoding", self.client["encoding"])

        with open(file_path, "r", encoding=encoding) as f:
            return f.read()

    def _read_binary_file(self, file_path: Path, **kwargs) -> bytes:
        """
        Read binary file content.

        Args:
            file_path: Path to binary file
            **kwargs: Additional parameters

        Returns:
            File content as bytes
        """
        with open(file_path, "rb") as f:
            return f.read()

    def _write_text_file(
        self,
        file_path: Path,
        content: str,
        mode: WriteMode,
        file_exists: bool,
        collection: str,
        **kwargs,
    ) -> StorageResult:
        """
        Write content to text file (refactored from FileWriterAgent).

        Args:
            file_path: Path to file
            content: Content to write
            mode: Write mode
            file_exists: Whether file existed before operation
            collection: Collection name for error reporting
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        encoding = kwargs.get("encoding", self.client["encoding"])
        newline = kwargs.get("newline", self.client["newline"])

        try:
            # Handle different write modes
            if mode == WriteMode.WRITE:
                # Create or overwrite file
                with open(file_path, "w", encoding=encoding, newline=newline) as f:
                    f.write(content)

                return self._create_success_result(
                    "write",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.APPEND:
                # Append to existing file or create new
                with open(file_path, "a", encoding=encoding, newline=newline) as f:
                    if file_exists:
                        # Add a newline before appending if needed
                        f.write("\n\n")
                    f.write(content)

                return self._create_success_result(
                    "append",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.UPDATE:
                # For text files, update is the same as write for simplicity
                with open(file_path, "w", encoding=encoding, newline=newline) as f:
                    f.write(content)

                return self._create_success_result(
                    "update",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            # Other modes not supported for simple text files
            return self._create_error_result(
                "write",
                f"Unsupported write mode for text files: {mode}",
                collection=collection,
                file_path=str(file_path),
            )

        except (PermissionError, OSError) as e:
            # Handle permission and OS errors gracefully
            error_msg = f"Permission denied: {str(e)}"
            self._logger.error(
                f"[{self.provider_name}] {error_msg} (collection={collection}, file_path={file_path})"
            )
            return self._create_error_result(
                "write", error_msg, collection=collection, file_path=str(file_path)
            )

    def _write_binary_file(
        self,
        file_path: Path,
        content: bytes,
        mode: WriteMode,
        file_exists: bool,
        collection: str,
        **kwargs,
    ) -> StorageResult:
        """
        Write content to binary file.

        Args:
            file_path: Path to file
            content: Binary content to write
            mode: Write mode
            file_exists: Whether file existed before operation
            collection: Collection name for error reporting
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            # Handle different write modes
            if mode == WriteMode.WRITE:
                # Create or overwrite file
                with open(file_path, "wb") as f:
                    f.write(content)

                return self._create_success_result(
                    "write",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.APPEND:
                # Append to existing file or create new
                with open(file_path, "ab") as f:
                    f.write(content)

                return self._create_success_result(
                    "append",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.UPDATE:
                # For binary files, update is the same as write
                with open(file_path, "wb") as f:
                    f.write(content)

                return self._create_success_result(
                    "update",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            # Other modes not supported for binary files
            return self._create_error_result(
                "write",
                f"Unsupported write mode for binary files: {mode}",
                collection=collection,
                file_path=str(file_path),
            )

        except (PermissionError, OSError) as e:
            # Handle permission and OS errors gracefully
            error_msg = f"Permission denied: {str(e)}"
            self._logger.error(
                f"[{self.provider_name}] {error_msg} (collection={collection}, file_path={file_path})"
            )
            return self._create_error_result(
                "write", error_msg, collection=collection, file_path=str(file_path)
            )

    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Read file(s) - supports document loading via LangChain loaders.

        Args:
            collection: Directory path
            document_id: Filename (optional)
            query: Query parameters for filtering
            path: Path within document for extraction
            **kwargs: Additional parameters (format, binary_mode, etc.)

        Returns:
            File content or directory listing
        """
        try:
            file_path = self._resolve_file_path(collection, document_id)

            # Validate path security
            validated_path = self._validate_file_path(str(file_path))
            file_path = Path(validated_path)

            # Extract parameters
            output_format = kwargs.get("format", "default")
            binary_mode = kwargs.get("binary_mode", False)

            # Handle directory listing (no document_id)
            if document_id is None:
                if not file_path.exists():
                    return []

                if file_path.is_file():
                    # Single file case - treat as document reading
                    document_id = file_path.name
                    file_path = file_path
                else:
                    # Directory listing
                    files = []
                    for item in file_path.iterdir():
                        if item.is_file():
                            files.append(item.name)
                    return sorted(files)

            # Check if file exists
            if not file_path.exists():
                self._logger.debug(f"File does not exist: {file_path}")
                return None

            # Handle binary file reading
            if binary_mode or self._is_binary_file(str(file_path)):
                if not self.client["allow_binary"]:
                    raise ValueError("Binary file reading not allowed")

                content = self._read_binary_file(file_path, **kwargs)

                if output_format == "default" or output_format == "raw":
                    # Return raw content by default (consistent with other storage services)
                    return content
                elif output_format == "structured":
                    # Structured format returns data with metadata when explicitly requested
                    return {
                        "content": content,
                        "metadata": {
                            "source": str(file_path),
                            "size": len(content),
                            "type": "binary",
                        },
                    }
                else:
                    # Unknown format - default to raw content
                    return content

            # Handle text file reading - prioritize simple text reading over document loaders
            if self._is_text_file(str(file_path)):
                try:
                    content = self._read_text_file(file_path, **kwargs)

                    if (
                        output_format == "default"
                        or output_format == "text"
                        or output_format == "raw"
                    ):
                        # Return raw content by default (consistent with other storage services)
                        return content
                    elif output_format == "structured":
                        # Structured format returns data with metadata when explicitly requested
                        return {
                            "content": content,
                            "metadata": {
                                "source": str(file_path),
                                "size": len(content),
                                "type": "text",
                            },
                        }
                    else:
                        # Unknown format - default to raw content
                        return content
                except Exception as e:
                    # If simple text reading fails, fallback to document loaders
                    self._logger.debug(
                        f"Simple text reading failed for {file_path}, trying document loaders: {e}"
                    )

            # If we reach here, it's not a simple text file or text reading failed, try document loaders

            # Handle document files via LangChain loaders
            try:
                loader = self._get_file_loader(str(file_path))
                documents = loader.load()

                # Apply document ID filter if provided (for chunked documents)
                if query and query.get("document_index") is not None:
                    doc_idx = query["document_index"]
                    if isinstance(doc_idx, int) and 0 <= doc_idx < len(documents):
                        documents = [documents[doc_idx]]
                    else:
                        documents = []

                # Apply query filter if provided
                if query:
                    # Remove special parameters before filtering
                    filter_query = {
                        k: v
                        for k, v in query.items()
                        if k not in ["document_index", "format", "binary_mode"]
                    }
                    if filter_query:
                        documents = self._apply_query_filter(documents, filter_query)

                # Apply path extraction if provided
                if path:
                    return self._apply_document_path(documents, path)

                # Return format based on request
                if output_format == "raw":
                    return documents
                elif output_format == "default" or output_format == "text":
                    # Return raw content by default (consistent with other storage services)
                    if isinstance(documents, list):
                        return "\n\n".join(
                            doc.page_content
                            for doc in documents
                            if hasattr(doc, "page_content")
                        )
                    elif hasattr(documents, "page_content"):
                        return documents.page_content
                    else:
                        return str(documents)
                elif output_format == "structured":
                    # Structured format - return metadata when explicitly requested
                    # For specific document reads, return single document, not list
                    if isinstance(documents, list):
                        if len(documents) == 1:
                            # Single document case - return the document directly
                            doc = documents[0]
                            if hasattr(doc, "page_content"):
                                result = {"content": doc.page_content}
                                if self.client["include_metadata"] and hasattr(
                                    doc, "metadata"
                                ):
                                    result["metadata"] = doc.metadata
                                return result
                            else:
                                return str(doc)
                        else:
                            # Multiple documents - return list
                            formatted_docs = []
                            for i, doc in enumerate(documents):
                                if hasattr(doc, "page_content"):
                                    item = {"content": doc.page_content}
                                    if self.client["include_metadata"] and hasattr(
                                        doc, "metadata"
                                    ):
                                        item["metadata"] = doc.metadata
                                    formatted_docs.append(item)
                                else:
                                    formatted_docs.append(str(doc))
                            return formatted_docs
                    elif hasattr(documents, "page_content"):
                        # Single document case
                        result = {"content": documents.page_content}
                        if self.client["include_metadata"] and hasattr(
                            documents, "metadata"
                        ):
                            result["metadata"] = documents.metadata
                        return result
                    else:
                        return documents
                else:
                    # Unknown format - default to raw content
                    if isinstance(documents, list):
                        return "\n\n".join(
                            doc.page_content
                            for doc in documents
                            if hasattr(doc, "page_content")
                        )
                    elif hasattr(documents, "page_content"):
                        return documents.page_content
                    else:
                        return str(documents)

            except Exception as e:
                # Fallback to text reading
                self._logger.warning(
                    f"Document loader failed for {file_path}, falling back to text: {e}"
                )
                content = self._read_text_file(file_path, **kwargs)

                if (
                    output_format == "default"
                    or output_format == "text"
                    or output_format == "raw"
                ):
                    # Return raw content by default (consistent with other storage services)
                    return content
                elif output_format == "structured":
                    # Structured format returns data with metadata when explicitly requested
                    return {
                        "content": content,
                        "metadata": {
                            "source": str(file_path),
                            "size": len(content),
                            "type": "text",
                        },
                    }
                else:
                    # Unknown format - default to raw content
                    return content

        except Exception as e:
            self._handle_error(
                "read", e, collection=collection, document_id=document_id
            )

    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Write file - supports text and binary content.

        Args:
            collection: Directory path
            data: Content to write
            document_id: Filename
            mode: Write mode (write, append, update, delete)
            path: Not used for file operations
            **kwargs: Additional parameters (binary_mode, encoding, etc.)

        Returns:
            StorageResult with operation details
        """
        try:
            if document_id is None:
                return self._create_error_result(
                    "write",
                    "document_id (filename) is required for file write operations",
                    collection=collection,
                )

            file_path = self._resolve_file_path(collection, document_id)

            # Validate path security
            validated_path = self._validate_file_path(str(file_path))
            file_path = Path(validated_path)

            # Handle DELETE mode
            if mode == WriteMode.DELETE:
                if file_path.exists():
                    file_path.unlink()
                    return self._create_success_result(
                        "delete",
                        collection=collection,
                        file_path=str(file_path),
                        file_deleted=True,
                    )
                else:
                    return self._create_error_result(
                        "delete",
                        "File not found for deletion",
                        collection=collection,
                        file_path=str(file_path),
                    )

            # Ensure directory exists
            self._ensure_directory(file_path.parent)

            # Check if file exists (for reporting if we created a new file)
            file_exists = file_path.exists()

            # Prepare content
            content = self._prepare_content(data)

            # Extract parameters
            binary_mode = kwargs.get("binary_mode", False)

            # Determine if we should handle as binary
            if (
                binary_mode
                or isinstance(content, bytes)
                or self._is_binary_file(str(file_path))
            ):
                if not self.client["allow_binary"]:
                    return self._create_error_result(
                        "write",
                        "Binary file writing not allowed",
                        collection=collection,
                        file_path=str(file_path),
                    )

                # Ensure content is bytes
                if isinstance(content, str):
                    content = content.encode(
                        kwargs.get("encoding", self.client["encoding"])
                    )

                return self._write_binary_file(
                    file_path, content, mode, file_exists, collection, **kwargs
                )

            # Handle as text file
            if isinstance(content, bytes):
                content = content.decode(
                    kwargs.get("encoding", self.client["encoding"])
                )

            return self._write_text_file(
                file_path, content, mode, file_exists, collection, **kwargs
            )

        except Exception as e:
            self._handle_error(
                "write",
                e,
                collection=collection,
                document_id=document_id,
                mode=mode.value,
            )

    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Delete file or directory.

        Args:
            collection: Directory path
            document_id: Filename (optional)
            path: Not used for file operations
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            file_path = self._resolve_file_path(collection, document_id)

            # Validate path security
            validated_path = self._validate_file_path(str(file_path))
            file_path = Path(validated_path)

            if not file_path.exists():
                return self._create_error_result(
                    "delete",
                    f"File or directory not found: {file_path}",
                    collection=collection,
                    document_id=document_id,
                )

            if file_path.is_file():
                # Delete file
                file_path.unlink()
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=str(file_path),
                    file_deleted=True,
                )
            elif file_path.is_dir():
                # Delete directory (only if empty or kwargs allow recursive)
                if kwargs.get("recursive", False):
                    shutil.rmtree(file_path)
                else:
                    file_path.rmdir()  # Only works if empty

                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=str(file_path),
                    directory_deleted=True,
                )
            else:
                return self._create_error_result(
                    "delete",
                    f"Cannot delete: not a file or directory: {file_path}",
                    collection=collection,
                    document_id=document_id,
                )

        except Exception as e:
            self._handle_error(
                "delete", e, collection=collection, document_id=document_id
            )

    def exists(
        self, collection: str, document_id: Optional[str] = None, **kwargs
    ) -> bool:
        """
        Check if file or directory exists.

        Args:
            collection: Directory path
            document_id: Filename (optional)
            **kwargs: Additional parameters

        Returns:
            True if exists, False otherwise
        """
        try:
            file_path = self._resolve_file_path(collection, document_id)
            validated_path = self._validate_file_path(str(file_path))
            return Path(validated_path).exists()
        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False

    def get_file_metadata(
        self, collection: str, document_id: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Get detailed file metadata.

        Args:
            collection: Directory path
            document_id: Filename
            **kwargs: Additional parameters

        Returns:
            Dictionary with file metadata
        """
        try:
            file_path = self._resolve_file_path(collection, document_id)
            validated_path = self._validate_file_path(str(file_path))
            file_path = Path(validated_path)

            if not file_path.exists():
                return {}

            stat = file_path.stat()

            # Get MIME type
            mime_type, _ = mimetypes.guess_type(str(file_path))

            return {
                "name": file_path.name,
                "size": stat.st_size,
                "created_at": stat.st_ctime,
                "modified_at": stat.st_mtime,
                "is_directory": file_path.is_dir(),
                "is_file": file_path.is_file(),
                "extension": file_path.suffix,
                "mime_type": mime_type,
                "is_text": self._is_text_file(str(file_path)),
                "is_binary": self._is_binary_file(str(file_path)),
            }
        except Exception as e:
            self._logger.debug(f"Error getting file metadata: {e}")
            return {}

    def copy_file(
        self,
        source_collection: str,
        source_id: str,
        target_collection: str,
        target_id: str,
        **kwargs,
    ) -> StorageResult:
        """
        Copy file from source to target.

        Args:
            source_collection: Source directory
            source_id: Source filename
            target_collection: Target directory
            target_id: Target filename
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            source_path = self._resolve_file_path(source_collection, source_id)
            target_path = self._resolve_file_path(target_collection, target_id)

            # Validate paths
            validated_source = self._validate_file_path(str(source_path))
            validated_target = self._validate_file_path(str(target_path))

            source_path = Path(validated_source)
            target_path = Path(validated_target)

            if not source_path.exists():
                return self._create_error_result(
                    "copy",
                    f"Source file not found: {source_path}",
                    collection=source_collection,
                    document_id=source_id,
                )

            # Ensure target directory exists
            self._ensure_directory(target_path.parent)

            # Copy file
            shutil.copy2(source_path, target_path)

            return self._create_success_result(
                "copy",
                collection=target_collection,
                document_id=target_id,
                file_path=str(target_path),
                created_new=True,
            )

        except Exception as e:
            self._handle_error(
                "copy",
                e,
                source_collection=source_collection,
                source_id=source_id,
                target_collection=target_collection,
                target_id=target_id,
            )

    def list_collections(self, **kwargs) -> List[str]:
        """
        List all directories (collections) in base directory.

        Args:
            **kwargs: Additional parameters

        Returns:
            List of directory names
        """
        try:
            base_dir = Path(self.client["base_directory"])

            if not base_dir.exists():
                return []

            directories = []
            for item in base_dir.iterdir():
                if item.is_dir():
                    directories.append(item.name)

            return sorted(directories)

        except Exception as e:
            self._logger.debug(f"Error listing collections: {e}")
            return []
