"""
Storage Wrapper for MCP Server

Thin wrapper around the existing StorageService from app_storage.py.
Provides MCP-friendly interface while reusing all existing functionality.

This module ensures minimal code duplication and maintains compatibility
with the main Lokal-RAG application.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path to import from main app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app_config import AppConfig, create_config_from_settings
from app_storage import StorageService

logger = logging.getLogger(__name__)


def create_storage_service(config: Optional[AppConfig] = None) -> StorageService:
    """
    Factory function to create a StorageService instance.

    Args:
        config: Optional AppConfig (if None, loads from settings file)

    Returns:
        StorageService: Initialized storage service

    Example:
        >>> storage = create_storage_service()
        >>> print(storage.get_document_count())
        42
    """
    if config is None:
        logger.info("Loading configuration from settings file")
        config = create_config_from_settings()

    logger.info("Initializing StorageService")
    storage = StorageService(config)

    logger.info(
        f"StorageService initialized: {storage.get_document_count()} documents in database"
    )

    return storage


def get_document_by_id(
    storage_service: StorageService, doc_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a document by ID.

    Args:
        storage_service: StorageService instance
        doc_id: Document ID

    Returns:
        Dict with document data, or None if not found

    NOTE: This searches through all documents in the vector store.
    For large databases, this may be slow. Consider caching or indexing.

    Example:
        >>> doc = get_document_by_id(storage, "doc_123")
        >>> print(doc['title'])
        'Machine Learning Basics'
    """
    try:
        # Get vectorstore
        vectorstore = storage_service.get_vectorstore()

        # Search by ID in metadata
        results = vectorstore.similarity_search(
            "", k=1, filter={"id": doc_id}  # Empty query, filter by ID
        )

        if not results:
            logger.debug(f"Document not found: {doc_id}")
            return None

        doc = results[0]

        return {
            "id": doc.metadata.get("id", ""),
            "title": doc.metadata.get("title", ""),
            "content": doc.page_content,
            "type": doc.metadata.get("type", "document"),
            "tags": doc.metadata.get("tags", []),
            "language": doc.metadata.get("language", "en"),
            "created_at": doc.metadata.get("created_at", ""),
            "updated_at": doc.metadata.get("updated_at", ""),
            "source": doc.metadata.get("source"),
            "metadata": {
                "source_type": doc.metadata.get("source_type", "unknown"),
                "original_filename": doc.metadata.get("original_filename"),
                "url": doc.metadata.get("url"),
                "processed_at": doc.metadata.get("processed_at"),
                "images_processed": doc.metadata.get("images_processed", 0),
            },
        }

    except Exception as e:
        logger.error(f"Failed to retrieve document {doc_id}: {e}")
        return None


def list_all_documents(
    storage_service: StorageService,
    doc_type: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    List all documents with pagination and filtering.

    Args:
        storage_service: StorageService instance
        doc_type: Optional type filter ("document", "note")
        tags: Optional list of tags to filter by
        limit: Max results per page
        offset: Pagination offset

    Returns:
        Dict with items and pagination info

    NOTE: This is a simplified implementation. For production, consider
    using a dedicated metadata store (SQLite, PostgreSQL) for efficient querying.

    Example:
        >>> results = list_all_documents(storage, doc_type="note", limit=20)
        >>> print(len(results['items']))
        20
        >>> print(results['pagination']['has_more'])
        True
    """
    try:
        # Get vectorstore
        vectorstore = storage_service.get_vectorstore()

        # Build filter
        filter_dict = {}
        if doc_type:
            filter_dict["type"] = doc_type

        # Get all documents (this is inefficient for large databases)
        # TODO: Consider using ChromaDB's get() method with filters
        all_docs = vectorstore.similarity_search(
            "", k=10000, filter=filter_dict if filter_dict else None  # Empty query
        )

        # Filter by tags if specified
        if tags:
            all_docs = [
                doc
                for doc in all_docs
                if any(tag in doc.metadata.get("tags", []) for tag in tags)
            ]

        # Apply pagination
        total = len(all_docs)
        paginated_docs = all_docs[offset : offset + limit]

        # Format results
        items = []
        for idx, doc in enumerate(paginated_docs):
            # DEBUG: Log first document metadata to see available fields
            if idx == 0:
                logger.debug(
                    f"LIST_DOCS_SAMPLE: First document metadata keys: {list(doc.metadata.keys())}"
                )
                logger.debug(
                    f"LIST_DOCS_SAMPLE: created_at='{doc.metadata.get('created_at', '')}', "
                    f"updated_at='{doc.metadata.get('updated_at', '')}'"
                )

            items.append(
                {
                    "id": doc.metadata.get("id", ""),
                    "type": doc.metadata.get("type", "document"),
                    "title": doc.metadata.get("title", ""),
                    "excerpt": doc.page_content[:200],  # First 200 chars
                    "tags": doc.metadata.get("tags", []),
                    "language": doc.metadata.get("language", "en"),
                    "created_at": doc.metadata.get("created_at", ""),
                    "updated_at": doc.metadata.get("updated_at", ""),
                }
            )

        logger.debug(f"LIST_DOCS_RESULT: Returning {len(items)} items out of {total} total")

        return {
            "items": items,
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            },
        }

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return {"items": [], "pagination": {"total": 0, "limit": limit, "offset": offset, "has_more": False}}


def get_storage_stats(storage_service: StorageService) -> Dict[str, Any]:
    """
    Get statistics about the storage.

    Args:
        storage_service: StorageService instance

    Returns:
        Dict with statistics

    Example:
        >>> stats = get_storage_stats(storage)
        >>> print(stats['overview']['total_documents'])
        42
    """
    try:
        total_docs = storage_service.get_document_count()

        # Get vectorstore to analyze documents
        vectorstore = storage_service.get_vectorstore()

        # Sample documents to get stats
        # NOTE: This is inefficient for large databases
        sample_docs = vectorstore.similarity_search("", k=1000)

        # Count by type
        doc_count = sum(1 for doc in sample_docs if doc.metadata.get("type") == "document")
        note_count = sum(1 for doc in sample_docs if doc.metadata.get("type") == "note")

        # Count by language
        en_count = sum(1 for doc in sample_docs if doc.metadata.get("language") == "en")
        ru_count = sum(1 for doc in sample_docs if doc.metadata.get("language") == "ru")

        # Count tags
        all_tags = []
        for doc in sample_docs:
            all_tags.extend(doc.metadata.get("tags", []))

        unique_tags = len(set(all_tags))

        return {
            "overview": {
                "total_documents": doc_count,
                "total_notes": note_count,
                "total_items": total_docs,
                "total_tags": unique_tags,
            },
            "documents": {
                "total": doc_count,
                "by_language": {"en": en_count, "ru": ru_count},
            },
            "notes": {"total": note_count, "by_language": {"en": en_count, "ru": ru_count}},
        }

    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        return {
            "overview": {
                "total_documents": 0,
                "total_notes": 0,
                "total_items": 0,
                "total_tags": 0,
            },
            "documents": {"total": 0, "by_language": {"en": 0, "ru": 0}},
            "notes": {"total": 0, "by_language": {"en": 0, "ru": 0}},
        }


def create_note(
    storage_service: StorageService,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    language: str = "en",
) -> Dict[str, Any]:
    """
    Create a new note in the knowledge base.

    Args:
        storage_service: StorageService instance
        title: Note title
        content: Note content (markdown)
        tags: Optional list of tags
        language: Content language ("en" or "ru")

    Returns:
        Dict with note ID and metadata

    Example:
        >>> result = create_note(
        ...     storage,
        ...     title="Meeting Notes",
        ...     content="# Key Points\n- Item 1\n- Item 2",
        ...     tags=["meeting", "ai"],
        ...     language="en"
        ... )
        >>> print(result['id'])
        'note_abc123'
    """
    try:
        from datetime import datetime
        import uuid

        # Generate note ID
        note_id = f"note_{uuid.uuid4().hex[:12]}"

        # Create note path
        notes_dir = storage_service.config.NOTES_DIR
        notes_dir.mkdir(parents=True, exist_ok=True)
        note_path = notes_dir / f"{note_id}.md"

        # Save note to disk
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(content)

        # Add to vector database
        storage_service.add_note(note_content=content, note_path=note_path)

        logger.info(f"Note created: {note_id}")

        return {
            "id": note_id,
            "title": title,
            "created_at": datetime.now().isoformat(),
            "message": f"Note created successfully: {note_id}",
        }

    except Exception as e:
        logger.error(f"Failed to create note: {e}")
        raise


def update_note(
    storage_service: StorageService,
    note_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Update an existing note.

    Args:
        storage_service: StorageService instance
        note_id: Note ID
        title: New title (optional)
        content: New content (optional)
        tags: New tags (optional)

    Returns:
        Dict with update status

    NOTE: This is a simplified implementation. For production, consider
    implementing proper update logic in the StorageService.

    Example:
        >>> result = update_note(storage, "note_123", content="Updated content")
        >>> print(result['message'])
        'Note updated successfully'
    """
    # TODO: Implement proper note update logic
    # For now, this is a placeholder
    logger.warning("Note update not fully implemented yet")
    raise NotImplementedError("Note update feature coming soon")


def delete_note(
    storage_service: StorageService, note_id: str, confirm: bool = False
) -> Dict[str, Any]:
    """
    Delete a note from the knowledge base.

    Args:
        storage_service: StorageService instance
        note_id: Note ID
        confirm: Confirmation flag (must be True)

    Returns:
        Dict with deletion status

    NOTE: This is a simplified implementation. For production, consider
    implementing proper deletion logic in the StorageService.

    Example:
        >>> result = delete_note(storage, "note_123", confirm=True)
        >>> print(result['deleted'])
        True
    """
    if not confirm:
        return {"deleted": False, "message": "Confirmation required (set confirm=True)"}

    # TODO: Implement proper note deletion logic
    # For now, this is a placeholder
    logger.warning("Note deletion not fully implemented yet")
    raise NotImplementedError("Note deletion feature coming soon")
