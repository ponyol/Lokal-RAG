"""
Application Storage Layer

This module encapsulates all stateful storage operations:
1. Vector database (ChromaDB) for embeddings and similarity search
2. File system operations for saving Markdown files

The StorageService class is the only stateful component in the application.
It manages the lifecycle of heavy objects (embedding model, vector DB client).

File I/O operations are provided as pure functions where possible.
"""

import logging
from pathlib import Path
from typing import Optional

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

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
        self._bm25_retriever: Optional[BM25Retriever] = None
        self._all_documents: list[Document] = []  # Store all docs for BM25

        logger.info("Initializing StorageService")
        self._initialize_embeddings()
        self._initialize_vectorstore()
        self._initialize_bm25_retriever()

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

        NOTE: ChromaDB 1.3+ uses a modern architecture without multiprocessing,
        so no special cleanup is required (unlike 0.4.x versions).
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

            logger.info("Vector database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize vector database: {e}")
            raise

    def _initialize_bm25_retriever(self) -> None:
        """
        Initialize the BM25 retriever for keyword-based search.

        This method loads all existing documents from ChromaDB and creates
        a BM25Retriever for hybrid search (BM25 + Vector).

        NOTE: BM25 requires all documents in memory, so this may be slow
        for large databases (10k+ documents).
        """
        try:
            if self._vectorstore is None:
                logger.warning("Vector store not initialized, skipping BM25 initialization")
                return

            # Load all documents from ChromaDB
            logger.info("Loading all documents for BM25 index...")

            # Get all documents from ChromaDB (without similarity search)
            collection = self._vectorstore._collection
            results = collection.get(include=["documents", "metadatas"])

            if results and results["documents"]:
                # Reconstruct Document objects
                self._all_documents = [
                    Document(
                        page_content=content,
                        metadata=metadata or {}
                    )
                    for content, metadata in zip(results["documents"], results["metadatas"])
                ]

                logger.info(f"Loaded {len(self._all_documents)} documents for BM25")

                # Create BM25 retriever
                if self._all_documents:
                    self._bm25_retriever = BM25Retriever.from_documents(self._all_documents)
                    self._bm25_retriever.k = self.config.RAG_TOP_K
                    logger.info("BM25 retriever initialized successfully")
                else:
                    logger.info("No documents found, BM25 retriever will be created when documents are added")
            else:
                logger.info("No documents in database yet, BM25 retriever will be created when documents are added")

        except Exception as e:
            logger.warning(f"Failed to initialize BM25 retriever: {e}. Will continue with vector-only search.")
            self._bm25_retriever = None

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

            # Log first 500 chars of each document for debugging
            for i, doc in enumerate(docs[:5], 1):  # Only log first 5 to avoid spam
                source = doc.metadata.get('source', 'unknown')
                preview = doc.page_content[:500].replace('\n', ' ')
                logger.info(f"  Chunk {i}/{len(docs)}: {source}")
                logger.info(f"    Content preview: {preview}...")
                # Check if date keywords present
                if any(month in doc.page_content.lower() for month in ['август', 'august', 'июль', 'july', 'сентябр', 'september']):
                    logger.info(f"    ✅ Contains date keywords!")

            # Add documents and generate embeddings to vector store
            self._vectorstore.add_documents(docs)

            # Add documents to BM25 index
            self._all_documents.extend(docs)
            logger.info(f"Total documents in BM25 index: {len(self._all_documents)}")

            # Rebuild BM25 retriever with updated document list
            try:
                self._bm25_retriever = BM25Retriever.from_documents(self._all_documents)
                self._bm25_retriever.k = self.config.RAG_TOP_K
                logger.info("BM25 retriever rebuilt successfully")
            except Exception as bm25_error:
                logger.warning(f"Failed to rebuild BM25 retriever: {bm25_error}")
                self._bm25_retriever = None

            logger.info("Documents added successfully (vector + BM25)")

        except Exception as e:
            logger.error(f"Failed to add documents to vector database: {e}")
            raise

    def search_similar_documents(
        self, query: str, k: Optional[int] = None
    ) -> list[Document]:
        """
        Search for documents using hybrid search (BM25 + Vector).

        This method combines keyword-based search (BM25) and semantic search (vector)
        to improve retrieval quality, especially for queries with:
        - Exact matches (dates, numbers, codes, names)
        - Semantic meaning (concepts, topics)

        The results are fused using weighted ensemble (30% BM25, 70% Vector).

        Args:
            query: The search query text
            k: Number of documents to retrieve (defaults to config.RAG_TOP_K)

        Returns:
            list[Document]: List of similar documents, sorted by relevance

        Example:
            >>> storage = StorageService(config)
            >>> docs = storage.search_similar_documents("документы за август", k=10)
        """
        if self._vectorstore is None:
            raise RuntimeError("Vector store not initialized")

        if k is None:
            k = self.config.RAG_TOP_K

        try:
            # If BM25 retriever is not available, fallback to vector-only search
            if self._bm25_retriever is None or not self._all_documents:
                logger.info("BM25 not available, using vector-only search")
                docs = self._vectorstore.similarity_search(query, k=k)
                logger.info(f"Found {len(docs)} documents (vector-only)")
                return docs

            # Hybrid search: BM25 + Vector
            logger.info(f"Using hybrid search (BM25 + Vector) for query: {query[:50]}...")

            # Create vector retriever
            vector_retriever = self._vectorstore.as_retriever(
                search_kwargs={"k": k}
            )

            # Update BM25 retriever k
            self._bm25_retriever.k = k

            # Create ensemble retriever (hybrid)
            # Weights: 30% BM25 (keyword), 70% Vector (semantic)
            ensemble_retriever = EnsembleRetriever(
                retrievers=[self._bm25_retriever, vector_retriever],
                weights=[0.3, 0.7]
            )

            # Execute hybrid search
            docs = ensemble_retriever.get_relevant_documents(query)

            logger.info(f"Found {len(docs)} documents (hybrid: BM25 + Vector)")
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
        to free memory and close connections gracefully.

        NOTE: Even ChromaDB 1.3+ and sentence-transformers may use multiprocessing
        internally (PyTorch DataLoader), which can cause semaphore warnings.
        We clean up what we can, but some warnings may persist - they are harmless.
        """
        try:
            logger.info("Cleaning up StorageService resources...")

            # Clear vectorstore reference
            if self._vectorstore is not None:
                # Try to close ChromaDB client if accessible
                try:
                    if hasattr(self._vectorstore, '_client'):
                        client = self._vectorstore._client
                        if hasattr(client, 'close'):
                            client.close()
                            logger.debug("ChromaDB client closed")
                except Exception as e:
                    logger.debug(f"ChromaDB client cleanup skipped: {e}")

                self._vectorstore = None

            # Clear embeddings and underlying PyTorch resources
            if self._embeddings is not None:
                try:
                    # Try to cleanup sentence-transformers model
                    if hasattr(self._embeddings, 'client'):
                        model = self._embeddings.client
                        if hasattr(model, 'stop_multi_process_pool'):
                            model.stop_multi_process_pool()
                            logger.debug("Sentence-transformers pool stopped")
                        # Move model to CPU and clear cache
                        if hasattr(model, 'to'):
                            model.to('cpu')
                        # Clear PyTorch CUDA cache if available
                        try:
                            import torch
                            if torch.cuda.is_available():
                                torch.cuda.empty_cache()
                        except ImportError:
                            pass
                except Exception as e:
                    logger.debug(f"Embeddings cleanup skipped: {e}")

                self._embeddings = None

            # Force garbage collection
            import gc
            gc.collect()

            logger.info("StorageService cleanup complete")

        except Exception as e:
            logger.error(f"Error during StorageService cleanup: {e}")


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
