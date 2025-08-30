import requests
import logging
import os
from fastapi import HTTPException
from typing import Optional, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
SEARCH_ENGINE_URL = os.getenv("SEARCH_ENGINE_URL", "http://localhost:9200")
INDEX_NAME = os.getenv("INDEX_NAME", "stories")
USERNAME = os.getenv("SEARCH_USERNAME", None)
PASSWORD = os.getenv("SEARCH_PASSWORD", None)


class SearchEngine:
    def __init__(self, url: str, username: Optional[str] = None, password: Optional[str] = None):
        self.url = url.rstrip('/')
        self.auth = (username, password) if username and password else None
        self.engine_type = self._detect_engine_type()
        logger.info(f"Detected search engine: {self.engine_type}")

    def _detect_engine_type(self) -> str:
        """Detect if we're connecting to Elasticsearch or OpenSearch"""
        try:
            response = requests.get(f"{self.url}/", auth=self.auth, timeout=5)
            response.raise_for_status()
            info = response.json()

            # Check version info to determine engine type
            if "version" in info:
                version_info = info["version"]
                if "distribution" in version_info and version_info["distribution"] == "opensearch":
                    return "OpenSearch"
                elif "build_flavor" in version_info or "lucene_version" in version_info:
                    return "Elasticsearch"

            # Fallback: check cluster name or other indicators
            if "cluster_name" in info:
                return "Elasticsearch"  # Default assumption

            return "Unknown"
        except Exception as e:
            logger.warning(f"Could not detect search engine type: {e}")
            return "Unknown"

    def search(self, query: str, field: str = "all", size: int = 10) -> Dict[Any, Any]:
        """Perform search query"""
        search_body = self._build_search_query(query, field, size)

        try:
            response = requests.post(
                f"{self.url}/{INDEX_NAME}/_search",
                headers={"Content-Type": "application/json"},
                auth=self.auth,
                json=search_body,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Search request failed: {e}")
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

    def _build_search_query(self, query: str, field: str, size: int) -> Dict[Any, Any]:
        """Build search query based on field selection"""
        if field == "all":
            # Search across both story and story_summary fields
            search_query = {
                "multi_match": {
                    "query": query,
                    "fields": ["story^2", "story_summary^3"],  # Boost story_summary higher
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            }
        elif field == "story":
            search_query = {
                "match": {
                    "story": {
                        "query": query,
                        "fuzziness": "AUTO"
                    }
                }
            }
        elif field == "story_summary":
            search_query = {
                "match": {
                    "story_summary": {
                        "query": query,
                        "fuzziness": "AUTO"
                    }
                }
            }
        else:
            search_query = {"match_all": {}}

        return {
            "query": search_query,
            "size": size,
            "highlight": {
                "fields": {
                    "story": {},
                    "story_summary": {}
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            },
            "_source": ["id", "story", "story_summary"]
        }

    def get_suggestions(self, query: str, size: int = 5) -> Dict[Any, Any]:
        """Get search suggestions based on partial query"""
        if not query or len(query.strip()) < 2:
            return {"suggestions": []}
        
        # First try the simplified approach with just match_phrase_prefix
        suggest_body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "match_phrase_prefix": {
                                "story_summary": {
                                    "query": query,
                                    "max_expansions": size
                                }
                            }
                        },
                        {
                            "match_phrase_prefix": {
                                "story": {
                                    "query": query,
                                    "max_expansions": size
                                }
                            }
                        }
                    ]
                }
            },
            "size": size,
            "_source": ["story_summary"],
            "highlight": {
                "fields": {
                    "story_summary": {"fragment_size": 50, "number_of_fragments": 1}
                }
            }
        }
        
        try:
            response = requests.post(
                f"{self.url}/{INDEX_NAME}/_search",
                headers={"Content-Type": "application/json"},
                auth=self.auth,
                json=suggest_body,
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            suggestions = []
            
            # Extract suggestions from search hits
            if "hits" in result and "hits" in result["hits"]:
                for hit in result["hits"]["hits"][:size]:
                    if "_source" in hit and "story_summary" in hit["_source"] and hit["_source"]["story_summary"]:
                        # Extract meaningful phrases from the summary
                        summary = hit["_source"]["story_summary"].strip()
                        if len(summary) > 50:
                            summary = summary[:50] + "..."
                        if summary:  # Only add non-empty suggestions
                            suggestions.append(summary)
            
            # Remove duplicates while preserving order
            unique_suggestions = []
            seen = set()
            for suggestion in suggestions:
                if suggestion.lower() not in seen:
                    unique_suggestions.append(suggestion)
                    seen.add(suggestion.lower())
            
            # If we have suggestions from Elasticsearch, return them
            if unique_suggestions:
                return {"suggestions": unique_suggestions}
            else:
                # If no ES suggestions, use fallback
                return self._get_fallback_suggestions(query)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Suggestions request failed: {e}")
            # Return fallback suggestions based on common terms
            return self._get_fallback_suggestions(query)

    def _get_fallback_suggestions(self, query: str) -> Dict[Any, Any]:
        """Generate fallback suggestions when Elasticsearch suggestions fail"""
        fallback_terms = [
            "user manual", "technical specification", "project proposal", 
            "meeting notes", "documentation", "requirements", "analysis",
            "report", "presentation", "guidelines", "policy", "procedure",
            "training", "tutorial", "reference", "overview", "summary"
        ]
        
        query_lower = query.lower()
        suggestions = [
            term for term in fallback_terms 
            if term.startswith(query_lower) or query_lower in term
        ]
        
        return {"suggestions": suggestions[:5]}

