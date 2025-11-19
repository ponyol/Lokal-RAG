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
from langchain_classic.retrievers import EnsembleRetriever

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
        Initialize the storage service with embedding model and vector databases.

        Creates two separate ChromaDB instances:
        - chroma_db_en: For English documents
        - chroma_db_ru: For Russian documents

        The selected database (based on config.DATABASE_LANGUAGE) is used for search,
        but documents are always added to both databases.

        Args:
            config: Application configuration

        Raises:
            Exception: If embedding model fails to load
        """
        self.config = config
        self._embeddings: Optional[HuggingFaceEmbeddings] = None

        # Two separate vectorstores for English and Russian
        self._vectorstore_en: Optional[Chroma] = None
        self._vectorstore_ru: Optional[Chroma] = None

        # Active vectorstore for search (based on DATABASE_LANGUAGE)
        self._vectorstore: Optional[Chroma] = None

        self._bm25_retriever: Optional[BM25Retriever] = None
        self._all_documents: list[Document] = []  # Store all docs for BM25

        logger.info("Initializing StorageService with dual-language databases")
        self._initialize_embeddings()
        self._initialize_vectorstores()
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

    def _initialize_vectorstores(self) -> None:
        """
        Initialize two separate ChromaDB vector stores (English and Russian).

        Creates two databases:
        - chroma_db_en: For English documents
        - chroma_db_ru: For Russian documents

        The active database for search is selected based on config.DATABASE_LANGUAGE.

        NOTE: ChromaDB 1.3+ uses a modern architecture without multiprocessing,
        so no special cleanup is required (unlike 0.4.x versions).
        """
        try:
            # Paths for both databases (from config)
            db_path_en = self.config.VECTOR_DB_PATH_EN
            db_path_ru = self.config.VECTOR_DB_PATH_RU

            # Ensure directories exist
            db_path_en.mkdir(parents=True, exist_ok=True)
            db_path_ru.mkdir(parents=True, exist_ok=True)

            logger.info(f"Initializing English vector database at: {db_path_en}")
            self._vectorstore_en = Chroma(
                collection_name="lokal_rag_en",
                embedding_function=self._embeddings,
                persist_directory=str(db_path_en),
            )
            logger.info("English vector database initialized successfully")

            logger.info(f"Initializing Russian vector database at: {db_path_ru}")
            self._vectorstore_ru = Chroma(
                collection_name="lokal_rag_ru",
                embedding_function=self._embeddings,
                persist_directory=str(db_path_ru),
            )
            logger.info("Russian vector database initialized successfully")

            # Set active vectorstore based on DATABASE_LANGUAGE
            if self.config.DATABASE_LANGUAGE == "ru":
                self._vectorstore = self._vectorstore_ru
                logger.info("Active database: Russian (ru)")
            else:
                self._vectorstore = self._vectorstore_en
                logger.info("Active database: English (en)")

        except Exception as e:
            logger.error(f"Failed to initialize vector databases: {e}")
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
        Add documents to BOTH vector databases (English and Russian).

        This is a stateful operation that:
        1. Generates embeddings for each document
        2. Stores the embeddings and documents in BOTH ChromaDB instances
        3. Persists the changes to disk

        NOTE: Documents are always added to both databases, regardless of
        config.DATABASE_LANGUAGE setting. This ensures all documents are
        searchable when switching languages.

        Args:
            docs: List of LangChain Document objects to add

        Raises:
            RuntimeError: If vector stores are not initialized
            Exception: If document addition fails

        Example:
            >>> storage = StorageService(config)
            >>> docs = [Document(page_content="Text", metadata={"source": "file.pdf"})]
            >>> storage.add_documents(docs)
        """
        if self._vectorstore_en is None or self._vectorstore_ru is None:
            raise RuntimeError("Vector stores not initialized")

        if not docs:
            logger.warning("No documents to add")
            return

        try:
            logger.info(f"Adding {len(docs)} documents to BOTH databases (en + ru)")

            # Add type metadata to all documents
            for doc in docs:
                doc.metadata["type"] = "document"

            # Log first 500 chars of each document for debugging
            for i, doc in enumerate(docs[:5], 1):  # Only log first 5 to avoid spam
                source = doc.metadata.get('source', 'unknown')
                preview = doc.page_content[:500].replace('\n', ' ')
                logger.info(f"  Chunk {i}/{len(docs)}: {source}")
                logger.info(f"    Content preview: {preview}...")
                # Check if date keywords present
                if any(month in doc.page_content.lower() for month in ['август', 'august', 'июль', 'july', 'сентябр', 'september']):
                    logger.info(f"    ✅ Contains date keywords!")

            # Add documents to BOTH databases
            logger.info("  → Adding to English database...")
            self._vectorstore_en.add_documents(docs)
            logger.info("  ✓ Added to English database")

            logger.info("  → Adding to Russian database...")
            self._vectorstore_ru.add_documents(docs)
            logger.info("  ✓ Added to Russian database")

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

            logger.info("Documents added successfully to BOTH databases (en + ru + BM25)")

        except Exception as e:
            logger.error(f"Failed to add documents to vector databases: {e}")
            raise

    def add_note(self, note_content: str, note_path: Path) -> None:
        """
        Add a note to BOTH vector databases (English and Russian).

        Notes are stored with metadata type="note" to distinguish them from
        regular documents (type="document").

        NOTE: Notes are always added to both databases, regardless of
        config.DATABASE_LANGUAGE setting.

        Args:
            note_content: The text content of the note
            note_path: Path to the note file (for metadata)

        Raises:
            RuntimeError: If vector stores are not initialized
            Exception: If note addition fails

        Example:
            >>> storage = StorageService(config)
            >>> storage.add_note("Заметка о проекте", Path("notes/note_2025-11-11.md"))
        """
        if self._vectorstore_en is None or self._vectorstore_ru is None:
            raise RuntimeError("Vector stores not initialized")

        if not note_content.strip():
            logger.warning("Empty note content, skipping")
            return

        try:
            logger.info(f"Adding note to BOTH databases: {note_path.name}")

            # Import chunking function and metadata extraction
            from app_services import fn_create_text_chunks, fn_extract_title_from_markdown

            # Extract title from note
            title = fn_extract_title_from_markdown(note_content, fallback=note_path.stem)

            # Create chunks with rich metadata (notes can be long too)
            # Notes are language-agnostic, use "en" as default
            chunks = fn_create_text_chunks(
                text=note_content,
                source_file=str(note_path),
                config=self.config,
                language="en",  # Notes are typically English
                title=title,
                file_path=str(note_path),
            )

            # Add type="note" and filename to all chunks
            for chunk in chunks:
                chunk.metadata["type"] = "note"
                chunk.metadata["filename"] = note_path.name

            logger.info(f"  Created {len(chunks)} chunks for note")

            # Add note chunks to BOTH vector stores
            logger.info("  → Adding to English database...")
            self._vectorstore_en.add_documents(chunks)
            logger.info("  ✓ Added to English database")

            logger.info("  → Adding to Russian database...")
            self._vectorstore_ru.add_documents(chunks)
            logger.info("  ✓ Added to Russian database")

            # Add note chunks to BM25 index
            self._all_documents.extend(chunks)
            logger.info(f"Total documents in BM25 index: {len(self._all_documents)}")

            # Rebuild BM25 retriever with updated document list
            try:
                self._bm25_retriever = BM25Retriever.from_documents(self._all_documents)
                self._bm25_retriever.k = self.config.RAG_TOP_K
                logger.info("BM25 retriever rebuilt successfully")
            except Exception as bm25_error:
                logger.warning(f"Failed to rebuild BM25 retriever: {bm25_error}")
                self._bm25_retriever = None

            logger.info("Note added successfully to BOTH databases (en + ru + BM25)")

        except Exception as e:
            logger.error(f"Failed to add note to vector databases: {e}")
            raise

    def search_similar_documents(
        self, query: str, k: Optional[int] = None, search_type: Optional[str] = None
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
            search_type: Filter by type - "document", "note", or None (all)

        Returns:
            list[Document]: List of similar documents, sorted by relevance

        Example:
            >>> storage = StorageService(config)
            >>> docs = storage.search_similar_documents("документы за август", k=10)
            >>> notes = storage.search_similar_documents("проект", k=5, search_type="note")
        """
        if self._vectorstore is None:
            raise RuntimeError("Vector store not initialized")

        if k is None:
            k = self.config.RAG_TOP_K

        try:
            # Filter documents by type if needed
            if search_type:
                filtered_docs = [
                    doc for doc in self._all_documents
                    if doc.metadata.get("type") == search_type
                ]
                logger.info(f"Filtered to {len(filtered_docs)} documents of type '{search_type}'")
            else:
                filtered_docs = self._all_documents
                logger.info(f"Searching all {len(filtered_docs)} documents (no type filter)")

            # If BM25 retriever is not available or no filtered docs, fallback to vector-only search
            if self._bm25_retriever is None or not filtered_docs:
                logger.info("BM25 not available or no filtered docs, using vector-only search")

                # Use ChromaDB filtering for vector search
                if search_type:
                    docs = self._vectorstore.similarity_search(
                        query, k=k, filter={"type": search_type}
                    )
                else:
                    docs = self._vectorstore.similarity_search(query, k=k)

                logger.info(f"Found {len(docs)} documents (vector-only)")
                return docs

            # Hybrid search: BM25 + Vector
            logger.info(f"Using hybrid search (BM25 + Vector) for query: {query[:50]}...")

            # Create filtered BM25 retriever
            filtered_bm25_retriever = BM25Retriever.from_documents(filtered_docs)
            filtered_bm25_retriever.k = k

            # Create vector retriever with filter
            if search_type:
                vector_retriever = self._vectorstore.as_retriever(
                    search_kwargs={"k": k, "filter": {"type": search_type}}
                )
            else:
                vector_retriever = self._vectorstore.as_retriever(
                    search_kwargs={"k": k}
                )

            # Create ensemble retriever (hybrid)
            # Weights: 30% BM25 (keyword), 70% Vector (semantic)
            ensemble_retriever = EnsembleRetriever(
                retrievers=[filtered_bm25_retriever, vector_retriever],
                weights=[0.3, 0.7]
            )

            # Execute hybrid search
            docs = ensemble_retriever.invoke(query)

            logger.info(f"Found {len(docs)} documents (hybrid: BM25 + Vector)")
            return docs

        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            raise

    def get_all_chunks_by_document_id(self, document_id: str) -> list[Document]:
        """
        Retrieve ALL chunks of a specific document by its document_id.

        This method is crucial for full document retrieval - it gets every chunk
        of the document and returns them sorted by chunk_index.

        Args:
            document_id: The unique identifier of the document

        Returns:
            list[Document]: All chunks of the document, sorted by chunk_index

        Example:
            >>> storage = StorageService(config)
            >>> chunks = storage.get_all_chunks_by_document_id("abc-123-def")
            >>> print(f"Document has {len(chunks)} chunks")
            >>> # Chunks are in order: 0, 1, 2, ...
        """
        if self._vectorstore is None:
            raise RuntimeError("Vector store not initialized")

        try:
            # Get all chunks with matching document_id from ChromaDB
            # Note: ChromaDB's get() with where filter returns all matching documents
            collection = self._vectorstore._collection
            results = collection.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"]
            )

            if not results or not results['documents']:
                logger.warning(f"No chunks found for document_id: {document_id}")
                return []

            # Create Document objects
            docs = [
                Document(
                    page_content=content,
                    metadata=metadata
                )
                for content, metadata in zip(results['documents'], results['metadatas'])
            ]

            # Sort by chunk_index to preserve document order
            sorted_docs = sorted(docs, key=lambda x: x.metadata.get('chunk_index', 0))

            logger.info(f"Retrieved {len(sorted_docs)} chunks for document_id: {document_id}")
            return sorted_docs

        except Exception as e:
            logger.error(f"Failed to retrieve chunks for document_id {document_id}: {e}")
            return []

    def search_with_full_document(
        self,
        query: str,
        k: Optional[int] = None,
        search_type: Optional[str] = None,
        include_full_doc: bool = False
    ) -> list[Document]:
        """
        Search for documents with option to retrieve the full document.

        This is the "smart retrieval" method that can automatically expand
        a search result to include ALL chunks of the document.

        Workflow:
        1. Perform hybrid search to find top-K relevant chunks
        2. If include_full_doc=True:
           - Take the first (most relevant) chunk
           - Get its document_id
           - Retrieve ALL chunks of that document
           - Return them sorted by chunk_index

        Args:
            query: The search query text
            k: Number of documents to retrieve in initial search
            search_type: Filter by type - "document", "note", or None (all)
            include_full_doc: If True, expand to include ALL chunks of the top document

        Returns:
            list[Document]: Either top-K chunks OR all chunks of the top document

        Example:
            >>> storage = StorageService(config)
            >>> # Normal search: get top 10 relevant chunks
            >>> chunks = storage.search_with_full_document("Claude Code", k=10)
            >>> # Full document search: get ALL chunks of the most relevant document
            >>> full_doc = storage.search_with_full_document("Claude Code", include_full_doc=True)
            >>> print(f"Full document has {len(full_doc)} chunks")
        """
        # Step 1: Perform normal hybrid search
        top_chunks = self.search_similar_documents(query, k=k, search_type=search_type)

        # Step 2: If full document requested and we have results
        if include_full_doc and top_chunks:
            # Get document_id from the most relevant chunk
            first_chunk_meta = top_chunks[0].metadata
            doc_id = first_chunk_meta.get('document_id')

            if doc_id:
                logger.info(f"Expanding search to full document (document_id: {doc_id})")
                # Retrieve ALL chunks of this document
                all_chunks = self.get_all_chunks_by_document_id(doc_id)

                if all_chunks:
                    logger.info(f"Retrieved full document: {len(all_chunks)} chunks")
                    return all_chunks
                else:
                    logger.warning(f"Failed to retrieve full document, returning top chunks")
                    return top_chunks
            else:
                logger.warning("No document_id in top chunk metadata, returning top chunks")
                return top_chunks

        # Step 3: Return normal search results
        return top_chunks

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

        Cleans up BOTH vector databases (English and Russian).

        NOTE: Even ChromaDB 1.3+ and sentence-transformers may use multiprocessing
        internally (PyTorch DataLoader), which can cause semaphore warnings.
        We clean up what we can, but some warnings may persist - they are harmless.
        """
        try:
            logger.info("Cleaning up StorageService resources...")

            # Clear English vectorstore
            if self._vectorstore_en is not None:
                try:
                    if hasattr(self._vectorstore_en, '_client'):
                        client = self._vectorstore_en._client
                        if hasattr(client, 'close'):
                            client.close()
                            logger.debug("English ChromaDB client closed")
                except Exception as e:
                    logger.debug(f"English ChromaDB client cleanup skipped: {e}")
                self._vectorstore_en = None

            # Clear Russian vectorstore
            if self._vectorstore_ru is not None:
                try:
                    if hasattr(self._vectorstore_ru, '_client'):
                        client = self._vectorstore_ru._client
                        if hasattr(client, 'close'):
                            client.close()
                            logger.debug("Russian ChromaDB client closed")
                except Exception as e:
                    logger.debug(f"Russian ChromaDB client cleanup skipped: {e}")
                self._vectorstore_ru = None

            # Clear active vectorstore reference
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

            logger.info("StorageService cleanup complete (both databases)")

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
    language: str = "en",
) -> Path:
    """
    Save Markdown content to disk in a language and tag-based directory structure.

    This is a pure function (aside from the I/O side effect of writing the file).
    It creates the directory structure if it doesn't exist.

    Directory structure:
        output_markdown/
        ├── en/
        │   ├── python/
        │   │   ├── document1.md
        │   │   └── document2.md
        │   └── machine-learning/
        │       └── document3.md
        └── ru/
            ├── python/
            │   ├── document1_ru.md
            │   └── document2_ru.md
            └── machine-learning/
                └── document3_ru.md

    Args:
        text: The Markdown content to save
        tag: The category tag (used as subdirectory name)
        filename: The base filename (without extension)
        config: Application configuration
        language: Language code ("en" or "ru") for subdirectory

    Returns:
        Path: The path to the created file

    Raises:
        OSError: If file creation fails

    Example:
        >>> config = AppConfig()
        >>> path = fn_save_markdown_to_disk("# Title", "python", "doc1", config, "en")
        >>> print(path)
        output_markdown/en/python/doc1.md
    """
    # Sanitize tag for use as directory name
    safe_tag = tag.replace(" ", "-").lower()
    safe_tag = "".join(c for c in safe_tag if c.isalnum() or c in ("-", "_"))

    # Create the output directory structure with language subfolder
    output_dir = config.MARKDOWN_OUTPUT_PATH / language / safe_tag
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
    config.VECTOR_DB_PATH_EN.mkdir(parents=True, exist_ok=True)
    config.VECTOR_DB_PATH_RU.mkdir(parents=True, exist_ok=True)
    config.MARKDOWN_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    logger.info("All required directories created")
