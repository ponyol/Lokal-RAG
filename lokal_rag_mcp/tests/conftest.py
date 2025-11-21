"""
Pytest configuration and fixtures
"""

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")


@pytest.fixture
def sample_documents():
    """Sample documents for testing."""
    return [
        {
            "id": "doc1",
            "title": "Machine Learning Basics",
            "content": "Machine learning is a subset of AI that uses statistical techniques.",
            "tags": ["ml", "ai"],
            "type": "document",
        },
        {
            "id": "doc2",
            "title": "Deep Learning",
            "content": "Deep learning uses neural networks with multiple layers.",
            "tags": ["dl", "neural-networks"],
            "type": "document",
        },
        {
            "id": "doc3",
            "title": "Random Note",
            "content": "The quick brown fox jumps over the lazy dog.",
            "tags": ["random"],
            "type": "note",
        },
    ]


@pytest.fixture
def sample_query():
    """Sample query for testing."""
    return "machine learning and neural networks"
