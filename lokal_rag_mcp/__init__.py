"""
Lokal-RAG MCP Server

Model Context Protocol (MCP) server for Lokal-RAG with intelligent re-ranking.
Provides AI assistants with access to your local knowledge base through
standardized MCP tools.

Key Features:
- Two-stage search (Hybrid Search + Re-Ranking)
- Notes management with vector search
- Contextual chat with RAG
- Multilingual support (Russian/English)
- Apple Silicon optimized

Version: 2.0.0
"""

__version__ = "2.0.0"
__author__ = "Ponyol"
__license__ = "MIT"

# Public API
__all__ = [
    "__version__",
    "__author__",
    "__license__",
]
