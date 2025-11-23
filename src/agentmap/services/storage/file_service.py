"""
File Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for file operations, refactored from FileReaderAgent and FileWriterAgent functionality.
Supports text files, binary files, and document formats via LangChain loaders.

Refactored Architecture:
- FilePathValidator: Path validation and security
- FileTypeDetector: File type detection
- DocumentLoaderHandler: LangChain document loading
- FileIOHandler: Low-level file I/O operations
- ContentProcessor: Content preparation and conversion
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
from agentmap.services.storage.content_processor import ContentProcessor
from agentmap.services.storage.decorators import ensure_handlers_initialized
from agentmap.services.storage.document_loader_handler import DocumentLoaderHandler
from agentmap.services.storage.file_io_handler import FileIOHandler
from agentmap.services.storage.file_path_validator import FilePathValidator
from agentmap.services.storage.file_type_detector import FileTypeDetector
from agentmap.services.storage.types import StorageResult, WriteMode


class FileStorageService(BaseStorageService):
    """
    File storage service implementation.

    Provides storage operations for various file formats including:
    - Text files (.txt, .md, .html, .csv, .log, .py, .js, .json, .yaml)
    - Document files (.pdf, .docx, .doc) via LangChain loaders
    - Binary files (.png, .jpg, .zip, etc.) for basic read/write

    The service is now composed of specialized handlers:
    - Path validation and security
    - File type detection
    - Document loading (LangChain integration)
    - Low-level file I/O operations
    - Content processing
    """

    def __init__(
        self,
        provider_name: str,
        configuration: StorageConfigService,
        logging_service: LoggingService,
        file_path_service: FilePathService,
        base_directory: Optional[str] = None,
    ):
        """
        Initialize FileStorageService.

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

        # Initialize specialized handlers (lazy initialization after client setup)
        self._path_validator: Optional[FilePathValidator] = None
        self._type_detector: Optional[FileTypeDetector] = None
        self._document_loader: Optional[DocumentLoaderHandler] = None
        self._io_handler: Optional[FileIOHandler] = None
        self._content_processor = ContentProcessor()

    def _initialize_handlers(self) -> None:
        """Initialize specialized handlers after client is configured."""
        if self._path_validator is None:
            base_dir = self.client["base_directory"]
            allow_binary = self.client["allow_binary"]
            encoding = self.client["encoding"]
            newline = self.client["newline"]

            self._path_validator = FilePathValidator(base_dir, self._logger)
            self._type_detector = FileTypeDetector(allow_binary)
            self._document_loader = DocumentLoaderHandler(self._logger)
            self._io_handler = FileIOHandler(encoding, newline, self._logger)

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

        # Extract configuration options
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

    # Delegated methods for backwards compatibility
    @ensure_handlers_initialized
    def _validate_file_path(self, file_path: str) -> str:
        """Validate file path (delegates to FilePathValidator)."""
        return self._path_validator.validate_file_path(file_path)

    @ensure_handlers_initialized
    def _resolve_file_path(
        self, collection: str, document_id: Optional[str] = None
    ) -> Path:
        """Resolve file path (delegates to FilePathValidator)."""
        return self._path_validator.resolve_file_path(collection, document_id)

    @ensure_handlers_initialized
    def _ensure_directory(self, directory_path: Path) -> None:
        """Ensure directory exists (delegates to FilePathValidator)."""
        self._path_validator.ensure_directory(directory_path)

    @ensure_handlers_initialized
    def _is_text_file(self, file_path: str) -> bool:
        """Check if text file (delegates to FileTypeDetector)."""
        return self._type_detector.is_text_file(file_path)

    @ensure_handlers_initialized
    def _is_binary_file(self, file_path: str) -> bool:
        """Check if binary file (delegates to FileTypeDetector)."""
        return self._type_detector.is_binary_file(file_path)

    @ensure_handlers_initialized
    def _get_file_loader(self, file_path: str) -> Any:
        """Get document loader (delegates to DocumentLoaderHandler)."""
        return self._document_loader.get_file_loader(file_path)

    @ensure_handlers_initialized
    def _create_fallback_loader(self, file_path: str) -> Any:
        """Create fallback loader (delegates to DocumentLoaderHandler)."""
        return self._document_loader.create_fallback_loader(file_path)

    @ensure_handlers_initialized
    def _filter_by_id(self, documents: List[Any], document_id: str) -> List[Any]:
        """Filter documents by ID (delegates to DocumentLoaderHandler)."""
        return self._document_loader.filter_by_id(documents, document_id)

    @ensure_handlers_initialized
    def _apply_document_path(self, documents: Union[List[Any], Any], path: str) -> Any:
        """Apply document path (delegates to DocumentLoaderHandler)."""
        return self._document_loader.apply_document_path(documents, path)

    @ensure_handlers_initialized
    def _apply_query_filter(
        self, documents: List[Any], query: Union[Dict[str, Any], str]
    ) -> List[Any]:
        """Apply query filter (delegates to DocumentLoaderHandler)."""
        return self._document_loader.apply_query_filter(documents, query)

    def _prepare_content(self, data: Any) -> Union[str, bytes]:
        """Prepare content for writing (delegates to ContentProcessor)."""
        return self._content_processor.prepare_content(data)

    @ensure_handlers_initialized
    def _read_text_file(self, file_path: Path, **kwargs) -> str:
        """Read text file (delegates to FileIOHandler)."""
        encoding = kwargs.get("encoding", self.client["encoding"])
        return self._io_handler.read_text_file(file_path, encoding)

    @ensure_handlers_initialized
    def _read_binary_file(self, file_path: Path, **kwargs) -> bytes:
        """Read binary file (delegates to FileIOHandler)."""
        return self._io_handler.read_binary_file(file_path)

    @ensure_handlers_initialized
    def _write_text_file(
        self,
        file_path: Path,
        content: str,
        mode: WriteMode,
        file_exists: bool,
        collection: str,
        **kwargs,
    ) -> StorageResult:
        """Write text file (delegates to FileIOHandler)."""
        encoding = kwargs.get("encoding", self.client["encoding"])
        newline = kwargs.get("newline", self.client["newline"])

        return self._io_handler.write_text_file(
            file_path,
            content,
            mode,
            file_exists,
            collection,
            encoding,
            newline,
            self._create_error_result,
            self._create_success_result,
        )

    @ensure_handlers_initialized
    def _write_binary_file(
        self,
        file_path: Path,
        content: bytes,
        mode: WriteMode,
        file_exists: bool,
        collection: str,
        **kwargs,
    ) -> StorageResult:
        """Write binary file (delegates to FileIOHandler)."""
        return self._io_handler.write_binary_file(
            file_path,
            content,
            mode,
            file_exists,
            collection,
            self._create_error_result,
            self._create_success_result,
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
                    return content
                elif output_format == "structured":
                    return {
                        "content": content,
                        "metadata": {
                            "source": str(file_path),
                            "size": len(content),
                            "type": "binary",
                        },
                    }
                else:
                    return content

            # Handle text file reading - prioritize simple text reading
            if self._is_text_file(str(file_path)):
                try:
                    content = self._read_text_file(file_path, **kwargs)

                    if (
                        output_format == "default"
                        or output_format == "text"
                        or output_format == "raw"
                    ):
                        return content
                    elif output_format == "structured":
                        return {
                            "content": content,
                            "metadata": {
                                "source": str(file_path),
                                "size": len(content),
                                "type": "text",
                            },
                        }
                    else:
                        return content
                except Exception as e:
                    self._logger.debug(
                        f"Simple text reading failed for {file_path}, trying document loaders: {e}"
                    )

            # Try document loaders
            try:
                loader = self._get_file_loader(str(file_path))
                documents = loader.load()

                # Apply document ID filter if provided
                if query and query.get("document_index") is not None:
                    doc_idx = query["document_index"]
                    if isinstance(doc_idx, int) and 0 <= doc_idx < len(documents):
                        documents = [documents[doc_idx]]
                    else:
                        documents = []

                # Apply query filter if provided
                if query:
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
                    if isinstance(documents, list):
                        if len(documents) == 1:
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
                        result = {"content": documents.page_content}
                        if self.client["include_metadata"] and hasattr(
                            documents, "metadata"
                        ):
                            result["metadata"] = documents.metadata
                        return result
                    else:
                        return documents
                else:
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
                    return content
                elif output_format == "structured":
                    return {
                        "content": content,
                        "metadata": {
                            "source": str(file_path),
                            "size": len(content),
                            "type": "text",
                        },
                    }
                else:
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

            # Check if file exists
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
                # Delete directory
                if kwargs.get("recursive", False):
                    shutil.rmtree(file_path)
                else:
                    file_path.rmdir()

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
