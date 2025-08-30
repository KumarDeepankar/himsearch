"""
Search module for the himsearch application.

This module contains all search-related functionality including:
- Search engine abstraction
- Search indexing operations
- Search models and utilities
"""

from .engine import SearchEngine
from .indexer import SimpleSearchIndexer

__all__ = ['SearchEngine', 'SimpleSearchIndexer']