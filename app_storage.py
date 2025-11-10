"""
Application Storage Layer

This module encapsulates all stateful storage operations:
1. Vector database (ChromaDB) for embeddings and similarity search
2. File system operations for saving Markdown files

The StorageService class is the only stateful component in the application.
It manages the lifecycle of heavy objects (embedding model, vector DB client).

File I/O operations are provided as pure functions where possible.
"""

import atexit
import logging
from pathlib import Path
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.docstore.document import Document

from app_config import AppConfig


# Configure logging for this module
logger = logging.getLogger(__name__)


# ============================================================================
# Storage Service (Stateful)
# ============================================================================


class StorageService:
    """
    Manages persistent storage for the application.

    This class encapsulates the heavy, stateful objects:
    - HuggingFaceEmbeddings: The sentence transformer model for creating embeddings
    - ChromaDB: The vector database for storing and retrieving documents

    These objects are initialized once and reused throughout the application lifecycle.
    """

    def __init__(self, config: AppConfig):
        """
        Initialize the storage service with embedding model and vector database.

        Args:
            config: Application configuration

        Raises:
            Exception: If embedding model fails to load
        """
        self.config = config
        self._embeddings: Optional[HuggingFaceEmbeddings] = None
        self._vectorstore: Optional[Chroma] = None
        self._chroma_client = None  # Store reference to underlying ChromaDB client

        logger.info("Initializing StorageService")
        self._initialize_embeddings()
        self._initialize_vectorstore()

        # Register cleanup handler to run at program exit
        atexit.register(self._cleanup_at_exit)

    def _initialize_embeddings(self) -> None:
        """
        Initialize the HuggingFace embedding model.

        This loads the model into memory. The first call will download the model
        from HuggingFace Hub if not already cached.

        NOTE: This operation is slow (~1-2 seconds) and memory-intensive (~500MB).
        """
        try:
            logger.info(f"Loading embedding model: {self.config.EMBEDDING_MODEL}")

            self._embeddings = HuggingFaceEmbeddings(
                model_name=self.config.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},  # Use CPU for compatibility
                encode_kwargs={"normalize_embeddings": True},
            )

            logger.info("Embedding model loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def _initialize_vectorstore(self) -> None:
        """
        Initialize the ChromaDB vector store.

        If the database already exists at config.VECTOR_DB_PATH, it will be loaded.
        Otherwise, a new database will be created.
        """
        try:
            # Ensure the directory exists
            self.config.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)

            logger.info(f"Initializing vector database at: {self.config.VECTOR_DB_PATH}")

            self._vectorstore = Chroma(
                collection_name="lokal_rag_collection",
                embedding_function=self._embeddings,
                persist_directory=str(self.config.VECTOR_DB_PATH),
            )

            # Store reference to underlying ChromaDB client for cleanup
            if hasattr(self._vectorstore, '_client'):
                self._chroma_client = self._vectorstore._client

            logger.info("Vector database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize vector database: {e}")
            raise

    def get_vectorstore(self) -> Chroma:
        """
        Get the ChromaDB vector store instance.

        Returns:
            Chroma: The vector store instance

        Example:
            >>> storage = StorageService(config)
            >>> vectorstore = storage.get_vectorstore()
            >>> docs = vectorstore.similarity_search("query", k=4)
        """
        if self._vectorstore is None:
            raise RuntimeError("Vector store not initialized")
        return self._vectorstore

    def add_documents(self, docs: list[Document]) -> None:
        """
        Add documents to the vector database.

        This is a stateful operation that:
        1. Generates embeddings for each document
        2. Stores the embeddings and documents in ChromaDB
        3. Persists the changes to disk

        Args:
            docs: List of LangChain Document objects to add

        Raises:
            RuntimeError: If vector store is not initialized
            Exception: If document addition fails

        Example:
            >>> storage = StorageService(config)
            >>> docs = [Document(page_content="Text", metadata={"source": "file.pdf"})]
            >>> storage.add_documents(docs)
        """
        if self._vectorstore is None:
            raise RuntimeError("Vector store not initialized")

        if not docs:
            logger.warning("No documents to add")
            return

        try:
            logger.info(f"Adding {len(docs)} documents to vector database")

            # Add documents and generate embeddings
            self._vectorstore.add_documents(docs)

            logger.info("Documents added successfully")

        except Exception as e:
            logger.error(f"Failed to add documents to vector database: {e}")
            raise

    def search_similar_documents(
        self, query: str, k: Optional[int] = None
    ) -> list[Document]:
        """
        Search for documents similar to the query.

        Args:
            query: The search query text
            k: Number of documents to retrieve (defaults to config.RAG_TOP_K)

        Returns:
            list[Document]: List of similar documents, sorted by relevance

        Example:
            >>> storage = StorageService(config)
            >>> docs = storage.search_similar_documents("machine learning", k=4)
        """
        if self._vectorstore is None:
            raise RuntimeError("Vector store not initialized")

        if k is None:
            k = self.config.RAG_TOP_K

        try:
            logger.debug(f"Searching for {k} similar documents for query: {query[:50]}...")
            docs = self._vectorstore.similarity_search(query, k=k)
            logger.debug(f"Found {len(docs)} documents")
            return docs

        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            raise

    def get_document_count(self) -> int:
        """
        Get the total number of documents in the vector database.

        Returns:
            int: Number of documents

        Example:
            >>> storage = StorageService(config)
            >>> count = storage.get_document_count()
            >>> print(f"Database contains {count} documents")
        """
        if self._vectorstore is None:
            raise RuntimeError("Vector store not initialized")

        try:
            # ChromaDB's way to get collection size
            collection = self._vectorstore._collection
            return collection.count()
        except Exception as e:
            logger.warning(f"Could not get document count: {e}")
            return 0

    def cleanup(self) -> None:
        """
        Clean up resources held by the storage service.

        This method should be called when the application is shutting down
        to properly close ChromaDB connections and free resources.

        NOTE: This prevents the "leaked semaphore objects" warning from
        multiprocessing.resource_tracker on application exit.
        """
        try:
            logger.info("Cleaning up StorageService resources...")

            # ChromaDB cleanup - more aggressive approach
            if self._chroma_client is not None:
                try:
                    # Try multiple cleanup methods
                    if hasattr(self._chroma_client, 'clear_system_cache'):
                        self._chroma_client.clear_system_cache()
                        logger.debug("ChromaDB system cache cleared")

                    if hasattr(self._chroma_client, 'reset'):
                        # Note: reset() clears the database, so we don't use it
                        pass

                    # Try to close the client's heartbeat if it exists
                    if hasattr(self._chroma_client, '_identifier_to_system'):
                        systems = self._chroma_client._identifier_to_system
                        if systems:
                            for system in systems.values():
                                if hasattr(system, 'stop'):
                                    system.stop()
                                    logger.debug("Stopped ChromaDB system component")

                    logger.info("ChromaDB client cleaned up")
                except Exception as e:
                    logger.warning(f"Could not close ChromaDB client cleanly: {e}")

                self._chroma_client = None

            # Clear vectorstore reference
            if self._vectorstore is not None:
                self._vectorstore = None

            # Clear embeddings
            if self._embeddings is not None:
                self._embeddings = None

            logger.info("StorageService cleanup complete")

        except Exception as e:
            logger.error(f"Error during StorageService cleanup: {e}")

    def _cleanup_at_exit(self) -> None:
        """
        Cleanup handler registered with atexit.

        This ensures cleanup happens even if the normal shutdown path fails.
        """
        try:
            self.cleanup()
        except Exception as e:
            # Suppress errors during exit to avoid cluttering output
            pass


# ============================================================================
# File System Operations (Pure Functions)
# ============================================================================


def fn_save_markdown_to_disk(
    text: str,
    tag: str,
    filename: str,
    config: AppConfig,
) -> Path:
    """
    Save Markdown content to disk in a tag-based directory structure.

    This is a pure function (aside from the I/O side effect of writing the file).
    It creates the directory structure if it doesn't exist.

    Directory structure:
        output_markdown/
        ├── python/
        │   ├── document1.md
        │   └── document2.md
        └── machine-learning/
            └── document3.md

    Args:
        text: The Markdown content to save
        tag: The category tag (used as subdirectory name)
        filename: The base filename (without extension)
        config: Application configuration

    Returns:
        Path: The path to the created file

    Raises:
        OSError: If file creation fails

    Example:
        >>> config = AppConfig()
        >>> path = fn_save_markdown_to_disk("# Title", "python", "doc1", config)
        >>> print(path)
        output_markdown/python/doc1.md
    """
    # Sanitize tag for use as directory name
    safe_tag = tag.replace(" ", "-").lower()
    safe_tag = "".join(c for c in safe_tag if c.isalnum() or c in ("-", "_"))

    # Create the output directory structure
    output_dir = config.MARKDOWN_OUTPUT_PATH / safe_tag
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create the output file path
    output_path = output_dir / f"{filename}.md"

    # Write the file
    try:
        logger.info(f"Saving Markdown to: {output_path}")
        output_path.write_text(text, encoding="utf-8")
        logger.info("Markdown saved successfully")
        return output_path

    except Exception as e:
        logger.error(f"Failed to save Markdown to {output_path}: {e}")
        raise


def fn_ensure_directories_exist(config: AppConfig) -> None:
    """
    Ensure all required directories exist.

    This is a setup function that should be called at application startup.

    Args:
        config: Application configuration

    Example:
        >>> config = AppConfig()
        >>> fn_ensure_directories_exist(config)
    """
    config.VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)
    config.MARKDOWN_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    logger.info("All required directories created")
