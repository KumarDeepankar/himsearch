import requests
import logging
import os
from fastapi import HTTPException
from typing import Optional, Dict, Any, List
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

# Configure logging
logger = logging.getLogger(__name__)

# Configuration
SEARCH_ENGINE_URL = os.getenv("SEARCH_ENGINE_URL", "http://localhost:9200")
INDEX_NAME = os.getenv("INDEX_NAME", "stories")
USERNAME = os.getenv("SEARCH_USERNAME", None)
PASSWORD = os.getenv("SEARCH_PASSWORD", None)
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")


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

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding using Ollama for semantic search"""
        try:
            payload = {
                "model": EMBEDDING_MODEL,
                "prompt": text
            }
            response = requests.post(f"{OLLAMA_URL}/api/embeddings", json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            embedding = result.get("embedding")
            if embedding and len(embedding) == 768:  # Expected dimension
                return embedding
            else:
                logger.warning(f"Invalid embedding dimension: {len(embedding) if embedding else 'None'}")
                return None
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return None

    def _build_knn_search(self, query_vector: List[float], size: int) -> Dict[Any, Any]:
        """Build KNN search query for OpenSearch"""
        return {
            "size": size,
            "knn": {
                "doc_subject": {
                    "vector": query_vector,
                    "k": size
                }
            },
            "_source": ["document_id", "story", "story_summary", "indexed_at", "doc_subject"]
        }

    def _get_source_fields(self, include_fields: Optional[List[str]] = None, exclude_fields: Optional[List[str]] = None) -> List[str]:
        """Determine which fields to include in _source based on include/exclude parameters"""
        # Default fields if none specified
        default_fields = ["document_id", "story", "story_summary", "indexed_at", "doc_subject"]
        
        if include_fields is None and exclude_fields is None:
            # Return all available fields (let OpenSearch return everything)
            return None  # This tells OpenSearch to return all fields
        
        if include_fields is not None:
            # Only include specified fields
            return include_fields
        
        if exclude_fields is not None:
            # Include default fields minus excluded ones
            return [field for field in default_fields if field not in exclude_fields]
        
        return default_fields

    def search(self, query: str, field: str = "all", size: int = 10, semantic_boost: float = 0.3, 
               include_fields: Optional[List[str]] = None, exclude_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
        """Perform hybrid search combining text and semantic vector search"""
        
        # Determine source fields to return
        source_fields = self._get_source_fields(include_fields, exclude_fields)
        
        if field == "doc_subject":
            # Pure semantic search on doc_subject field
            return self._perform_vector_search(query, size, source_fields)
        elif field in ["story", "story_summary"]:
            # Pure text search on specific field
            return self._perform_text_search(query, field, size, source_fields)
        elif field == "all":
            # Hybrid search: combine text and semantic results
            return self._perform_hybrid_search(query, size, semantic_boost, source_fields)
        else:
            # Fallback to match_all
            return self._perform_text_search(query, "all", size, source_fields)

    def _perform_text_search(self, query: str, field: str, size: int, source_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
        """Perform text-only search"""
        search_body = self._build_text_search_query(query, field, size, source_fields)
        
        try:
            response = requests.post(
                f"{self.url}/{INDEX_NAME}/_search",
                headers={"Content-Type": "application/json"},
                auth=self.auth,
                json=search_body,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            result["_meta"] = {"semantic_search_used": False, "search_type": "text_only"}
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Text search failed: {e}")
            raise HTTPException(status_code=500, detail=f"Text search failed: {str(e)}")

    def _perform_vector_search(self, query: str, size: int, source_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
        """Perform vector-only search on doc_subject field"""
        query_embedding = self._generate_embedding(query)
        if query_embedding is None:
            logger.warning("Failed to generate embedding, falling back to match_all")
            return self._perform_text_search("", "all", size)
        
        search_body = {
            "size": size,
            "knn": {
                "doc_subject": {
                    "vector": query_embedding,
                    "k": size
                }
            }
        }
        
        # Add _source field control
        if source_fields is not None:
            search_body["_source"] = source_fields
        # If source_fields is None, OpenSearch will return all fields
        
        try:
            response = requests.post(
                f"{self.url}/{INDEX_NAME}/_search",
                headers={"Content-Type": "application/json"},
                auth=self.auth,
                json=search_body,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            result["_meta"] = {"semantic_search_used": True, "search_type": "vector_only"}
            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Vector search failed: {e}")
            # Fallback to text search
            logger.info("Falling back to text search")
            return self._perform_text_search(query, "all", size)

    def _perform_hybrid_search(self, query: str, size: int, semantic_boost: float, source_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
        """Perform hybrid search combining text and vector results using parallel processing"""
        # Get embedding for semantic search
        query_embedding = self._generate_embedding(query)
        
        if query_embedding is None or semantic_boost == 0:
            logger.info("No embedding available or semantic_boost=0, using text-only search")
            return self._perform_text_search(query, "all", size)
        
        try:
            start_time = time.time()
            
            # Perform both searches in parallel using multiprocessing
            with ProcessPoolExecutor(max_workers=2) as executor:
                # Submit both search tasks
                text_future = executor.submit(
                    _parallel_text_search, 
                    query, self.url, INDEX_NAME, self.auth, size * 2, source_fields
                )
                vector_future = executor.submit(
                    _parallel_vector_search, 
                    query_embedding, self.url, INDEX_NAME, self.auth, size * 2, source_fields
                )
                
                # Collect results as they complete
                text_results = None
                vector_results = None
                
                for future in as_completed([text_future, vector_future]):
                    if future == text_future:
                        text_results = future.result()
                    else:
                        vector_results = future.result()
            
            parallel_time = time.time() - start_time
            
            # Fallback if either search failed
            if text_results is None:
                logger.warning("Text search failed in parallel execution, falling back to sequential")
                text_results = self._perform_text_search(query, "all", size * 2)
            if vector_results is None:
                logger.warning("Vector search failed in parallel execution, falling back to sequential")
                vector_results = self._perform_vector_search(query, size * 2)
            
            # Combine and re-rank results
            combined_results = self._combine_search_results(
                text_results, vector_results, semantic_boost, size
            )
            
            combined_results["_meta"] = {
                "semantic_search_used": True, 
                "search_type": "hybrid_parallel",
                "semantic_boost": semantic_boost,
                "text_results_count": len(text_results.get("hits", {}).get("hits", [])),
                "vector_results_count": len(vector_results.get("hits", {}).get("hits", [])),
                "parallel_execution_time": parallel_time
            }
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Parallel hybrid search failed: {e}")
            # Fallback to sequential search
            logger.info("Falling back to sequential hybrid search")
            return self._perform_hybrid_search_sequential(query, size, semantic_boost)

    def _perform_hybrid_search_sequential(self, query: str, size: int, semantic_boost: float) -> Dict[Any, Any]:
        """Fallback sequential hybrid search when parallel processing fails"""
        try:
            # 1. Text search
            text_results = self._perform_text_search(query, "all", size * 2)
            
            # 2. Vector search  
            vector_results = self._perform_vector_search(query, size * 2)
            
            # 3. Combine and re-rank results
            combined_results = self._combine_search_results(
                text_results, vector_results, semantic_boost, size
            )
            
            combined_results["_meta"] = {
                "semantic_search_used": True, 
                "search_type": "hybrid_sequential",
                "semantic_boost": semantic_boost,
                "text_results_count": len(text_results.get("hits", {}).get("hits", [])),
                "vector_results_count": len(vector_results.get("hits", {}).get("hits", []))
            }
            
            return combined_results
            
        except Exception as e:
            logger.error(f"Sequential hybrid search failed: {e}")
            # Final fallback to text search
            return self._perform_text_search(query, "all", size)

    def _build_text_search_query(self, query: str, field: str, size: int, source_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
        """Build text search query"""
        if field == "all":
            if not query.strip():
                search_query = {"match_all": {}}
            else:
                search_query = {
                    "multi_match": {
                        "query": query,
                        "fields": ["story^2", "story_summary^3"],
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

        query_body = {
            "query": search_query,
            "size": size,
            "highlight": {
                "fields": {
                    "story": {},
                    "story_summary": {}
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            }
        }
        
        # Add _source field control
        if source_fields is not None:
            query_body["_source"] = source_fields
        # If source_fields is None, OpenSearch will return all fields
        
        return query_body

    def _combine_search_results(self, text_results: Dict[Any, Any], vector_results: Dict[Any, Any], 
                               semantic_boost: float, size: int) -> Dict[Any, Any]:
        """Combine and re-rank results from text and vector searches"""
        
        # Extract hits from both result sets
        text_hits = text_results.get("hits", {}).get("hits", [])
        vector_hits = vector_results.get("hits", {}).get("hits", [])
        
        # Normalize scores to 0-1 range for fair combination
        text_max_score = text_results.get("hits", {}).get("max_score", 1.0) or 1.0
        vector_max_score = vector_results.get("hits", {}).get("max_score", 1.0) or 1.0
        
        # Create a combined scoring dictionary
        combined_scores = {}
        doc_details = {}
        
        # Process text search results
        for hit in text_hits:
            doc_id = hit["_id"]
            normalized_text_score = (hit["_score"] / text_max_score) if text_max_score > 0 else 0
            combined_scores[doc_id] = {
                "text_score": normalized_text_score,
                "vector_score": 0.0
            }
            doc_details[doc_id] = hit
        
        # Process vector search results and merge
        for hit in vector_hits:
            doc_id = hit["_id"]
            normalized_vector_score = (hit["_score"] / vector_max_score) if vector_max_score > 0 else 0
            
            if doc_id in combined_scores:
                combined_scores[doc_id]["vector_score"] = normalized_vector_score
            else:
                combined_scores[doc_id] = {
                    "text_score": 0.0,
                    "vector_score": normalized_vector_score
                }
                doc_details[doc_id] = hit
        
        # Calculate hybrid scores and sort
        hybrid_results = []
        for doc_id, scores in combined_scores.items():
            # Hybrid score: (1 - semantic_boost) * text_score + semantic_boost * vector_score
            hybrid_score = (1 - semantic_boost) * scores["text_score"] + semantic_boost * scores["vector_score"]
            
            hit = doc_details[doc_id].copy()
            hit["_score"] = hybrid_score
            
            # Add score breakdown for debugging
            hit["_score_breakdown"] = {
                "text_score": scores["text_score"],
                "vector_score": scores["vector_score"],
                "hybrid_score": hybrid_score,
                "semantic_boost": semantic_boost
            }
            
            hybrid_results.append(hit)
        
        # Sort by hybrid score (descending)
        hybrid_results.sort(key=lambda x: x["_score"], reverse=True)
        
        # Take top results
        final_hits = hybrid_results[:size]
        
        # Construct final result structure
        return {
            "took": text_results.get("took", 0) + vector_results.get("took", 0),
            "timed_out": False,
            "_shards": text_results.get("_shards", {}),
            "hits": {
                "total": {
                    "value": len(hybrid_results),
                    "relation": "eq"
                },
                "max_score": final_hits[0]["_score"] if final_hits else 0.0,
                "hits": final_hits
            }
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


# Parallel worker functions for multiprocessing
def _parallel_text_search(query: str, url: str, index_name: str, auth: tuple, size: int, source_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
    """Worker function for parallel text search"""
    try:
        search_body = _build_text_search_query_worker(query, "all", size, source_fields)
        
        response = requests.post(
            f"{url}/{index_name}/_search",
            headers={"Content-Type": "application/json"},
            auth=auth,
            json=search_body,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        result["_meta"] = {"semantic_search_used": False, "search_type": "text_only"}
        return result
    except Exception as e:
        logger.error(f"Parallel text search failed: {e}")
        return None


def _parallel_vector_search(query_embedding: List[float], url: str, index_name: str, auth: tuple, size: int, source_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
    """Worker function for parallel vector search"""
    try:
        search_body = {
            "size": size,
            "knn": {
                "doc_subject": {
                    "vector": query_embedding,
                    "k": size
                }
            }
        }
        
        # Add _source field control
        if source_fields is not None:
            search_body["_source"] = source_fields
        # If source_fields is None, OpenSearch will return all fields
        
        response = requests.post(
            f"{url}/{index_name}/_search",
            headers={"Content-Type": "application/json"},
            auth=auth,
            json=search_body,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        result["_meta"] = {"semantic_search_used": True, "search_type": "vector_only"}
        return result
    except Exception as e:
        logger.error(f"Parallel vector search failed: {e}")
        return None


def _build_text_search_query_worker(query: str, field: str, size: int, source_fields: Optional[List[str]] = None) -> Dict[Any, Any]:
    """Worker function to build text search query for parallel execution"""
    if field == "all":
        if not query.strip():
            search_query = {"match_all": {}}
        else:
            search_query = {
                "multi_match": {
                    "query": query,
                    "fields": ["story^2", "story_summary^3"],
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

    query_body = {
        "query": search_query,
        "size": size,
        "highlight": {
            "fields": {
                "story": {},
                "story_summary": {}
            },
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"]
        }
    }
    
    # Add _source field control
    if source_fields is not None:
        query_body["_source"] = source_fields
    # If source_fields is None, OpenSearch will return all fields
    
    return query_body

