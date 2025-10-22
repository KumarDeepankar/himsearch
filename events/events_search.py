#!/usr/bin/env python3
"""
OpenSearch Events Index Search Methods
Provides three search methods with optimized cascading strategy (70% accuracy, excellent precision):

1. fetch_information_by_rid - Search by RID with cascading strategy (exact → prefix → fuzzy)
2. fetch_information_by_docid - Search by DOCID with cascading strategy (exact → prefix → fuzzy)
3. search_events - Multi-field search with year/country filters + automatic spell tolerance

Cascading Strategy (Optimized for Top 3 Precision):
- Try exact match first → If found, return immediately
- Try prefix match → If found with good score (>= MIN_PREFIX_SCORE), return
- Fall back to fuzzy match → Return best results with score filtering
- Optimized score thresholds for high precision on top 3 results
- Average 1-3 results per query (excellent precision)

Spell Tolerance (search_events only):
- Automatic fuzzy matching handles typos and misspellings
- Tolerates 1-2 character edits (e.g., "climete" → "climate")
- First character must match exactly to prevent false matches
"""

import requests
import json
from typing import Dict, List, Optional, Any


class EventsSearch:
    def __init__(self, opensearch_url: str = "http://localhost:9200", index_name: str = "events"):
        """
        Initialize EventsSearch client

        Args:
            opensearch_url: OpenSearch server URL
            index_name: Index name to search
        """
        self.opensearch_url = opensearch_url
        self.index_name = index_name
        self.search_url = f"{opensearch_url}/{index_name}/_search"

        # Thresholds for high precision filtering (optimized for top 3 results)
        self.MIN_SCORE_RID = 2.5          # Increased from 1.0 for better precision
        self.MIN_SCORE_DOCID = 3.5        # Increased from 1.5 for better precision
        self.MIN_PREFIX_SCORE = 1.0       # Minimum score for prefix matches (balanced)
        self.MAX_PREFIX_RESULTS = 8       # Reduced from 20 for tighter matching

    def _execute_search(self, query: Dict) -> Dict:
        """Execute search query against OpenSearch"""
        try:
            response = requests.post(
                self.search_url,
                json=query,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code != 200:
                return {"error": f"Search failed: {response.text}"}

            return response.json()
        except Exception as e:
            return {"error": f"Request error: {str(e)}"}

    # ========================================================================
    # EXPERIMENTAL: HYBRID SEARCH STRATEGY (Not Currently Used)
    # Query-Length Routing + Parallel Search with Boosting
    #
    # NOTE: Testing showed this approach achieves same accuracy as cascading
    # (70%) but with WORSE precision (10x more results for 10-char queries).
    # Keeping code for reference. Current implementation uses cascading.
    # See hybrid_strategy_results.md for detailed analysis.
    # ========================================================================

    def _determine_search_strategies(self, query: str, field_type: str) -> List[str]:
        """
        Determine which search strategies to use based on query length

        Args:
            query: Search query string
            field_type: Either "rid" or "docid"

        Returns:
            List of strategies to use in parallel: ["exact", "prefix", "fuzzy"]

        Strategy:
            RID (typically 8 chars):
            - 1-4 chars → fuzzy only
            - 5-7 chars → prefix + fuzzy (skip exact)
            - 8+ chars → exact + prefix + fuzzy (all three)

            DOCID (typically 20-25 chars):
            - 1-7 chars → fuzzy only
            - 8-14 chars → prefix + fuzzy (skip exact)
            - 15+ chars → exact + fuzzy (skip prefix - not useful for long strings)
        """
        query_len = len(query)

        if field_type == "rid":
            if query_len <= 4:
                return ["fuzzy"]
            elif 5 <= query_len <= 7:
                return ["prefix", "fuzzy"]
            else:  # 8+
                return ["exact", "prefix", "fuzzy"]

        else:  # docid
            if query_len <= 7:
                return ["fuzzy"]
            elif 8 <= query_len <= 14:
                return ["prefix", "fuzzy"]
            else:  # 15+
                return ["exact", "fuzzy"]  # Skip prefix for very long queries

    def _parallel_search(self, query: str, field: str, strategies: List[str], aggregation_field: str) -> Optional[Dict]:
        """
        Execute multiple search strategies in parallel with boosting

        Args:
            query: Search query string
            field: Field to search (rid or docid)
            strategies: List of strategies to execute ["exact", "prefix", "fuzzy"]
            aggregation_field: Field to aggregate by (docid or rid)

        Returns:
            Search results with match type determined by highest scoring strategy
        """
        should_clauses = []

        # Add exact match with highest boost
        if "exact" in strategies:
            should_clauses.append({
                "term": {
                    f"{field}.keyword": {
                        "value": query,
                        "boost": 3.0  # Highest boost for exact matches
                    }
                }
            })

        # Add prefix match with medium boost
        if "prefix" in strategies:
            should_clauses.append({
                "match": {
                    f"{field}.prefix": {
                        "query": query,
                        "boost": 2.0  # Medium boost for prefix matches
                    }
                }
            })

        # Add fuzzy match with lowest boost
        if "fuzzy" in strategies:
            should_clauses.append({
                "match": {
                    field: {
                        "query": query,
                        "boost": 1.0  # Lowest boost for fuzzy matches
                    }
                }
            })

        # Build parallel query
        query_body = {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            },
            "size": 100,
            "_source": True,
            "sort": [{"_score": {"order": "desc"}}],
            "aggs": {
                f"{aggregation_field}_aggregation": {
                    "terms": {
                        "field": f"{aggregation_field}.keyword",
                        "size": 100
                    }
                }
            }
        }

        # Execute search
        data = self._execute_search(query_body)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        if not hits:
            return None

        # Analyze results to determine which strategy won
        return self._analyze_parallel_results(data, query, field, aggregation_field, strategies)

    def _analyze_parallel_results(self, data: Dict, query: str, field: str, aggregation_field: str, strategies: List[str]) -> Dict:
        """
        Analyze parallel search results to determine match type and confidence

        Args:
            data: OpenSearch response
            query: Original search query
            field: Field that was searched (rid or docid)
            aggregation_field: Field used for aggregation (docid or rid)
            strategies: List of strategies that were used in the search

        Returns:
            Formatted result with detected match type and confidence
        """
        hits = data['hits']['hits']

        # Apply score thresholds based on field type
        min_score = self.MIN_SCORE_RID if field == "rid" else self.MIN_SCORE_DOCID

        # Filter hits by score and prefix score thresholds
        filtered_hits = []
        for hit in hits:
            score = hit['_score']
            field_value = hit['_source'][field]

            # Determine match type for this hit
            if field_value == query:
                # Exact match - always include if score is decent
                if score >= 1.0:
                    filtered_hits.append(hit)
            elif field_value.startswith(query):
                # Prefix match - apply prefix score threshold
                if score >= self.MIN_PREFIX_SCORE:
                    filtered_hits.append(hit)
            else:
                # Fuzzy match - apply field-specific threshold
                if score >= min_score:
                    filtered_hits.append(hit)

        # If no hits pass thresholds, return top 3 anyway
        if not filtered_hits:
            filtered_hits = hits[:3]

        top_3 = filtered_hits[:3]

        # Detect overall match type based on top result AND which strategies were used
        if top_3:
            top_hit = top_3[0]
            top_field_value = top_hit['_source'][field]

            # Match type detection considers both the result and which strategies were available
            if top_field_value == query and "exact" in strategies:
                match_type = "exact"
                confidence = "very_high"
            elif top_field_value.startswith(query) and "prefix" in strategies:
                match_type = "prefix"
                confidence = "high" if len(filtered_hits) <= self.MAX_PREFIX_RESULTS else "medium"
            else:
                # Either fuzzy match, or prefix-like match when prefix wasn't used (counts as fuzzy)
                match_type = "fuzzy"
                confidence = "low" if len(filtered_hits) > 5 else "medium"
        else:
            match_type = "fuzzy"
            confidence = "low"

        # Extract aggregation data
        agg_counts = []
        agg_key = f"{aggregation_field}_aggregation"
        if "aggregations" in data and agg_key in data["aggregations"]:
            agg_counts = [
                {
                    aggregation_field: bucket["key"],
                    "count": bucket["doc_count"]
                }
                for bucket in data["aggregations"][agg_key]["buckets"]
            ]

        return {
            "query": query,
            "field": field,
            "match_type": match_type,
            "confidence": confidence,
            "total_count": len(filtered_hits),
            f"{aggregation_field}_aggregation": agg_counts,
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in top_3
            ]
        }

    # ========================================================================
    # CASCADING SEARCH METHODS (Active - Used by fetch_information_by_rid/docid)
    # These implement the individual search strategies that are called in sequence
    # ========================================================================

    def _search_rid_exact(self, rid_query: str) -> Optional[Dict]:
        """Search for exact RID match using keyword field"""
        query = {
            "query": {
                "term": {
                    "rid.keyword": rid_query
                }
            },
            "size": 100,
            "_source": True,
            "aggs": {
                "docid_aggregation": {
                    "terms": {
                        "field": "docid.keyword",
                        "size": 100
                    }
                }
            }
        }

        data = self._execute_search(query)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        if not hits:
            return None

        top_3 = hits[:3]

        # Extract aggregation data
        docid_counts = []
        if "aggregations" in data and "docid_aggregation" in data["aggregations"]:
            docid_counts = [
                {
                    "docid": bucket["key"],
                    "count": bucket["doc_count"]
                }
                for bucket in data["aggregations"]["docid_aggregation"]["buckets"]
            ]

        return {
            "query": rid_query,
            "field": "rid",
            "match_type": "exact",
            "confidence": "very_high",
            "total_count": len(hits),
            "docid_aggregation": docid_counts,
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in top_3
            ]
        }

    def _search_rid_prefix(self, rid_query: str) -> Optional[Dict]:
        """Search for RID prefix match using edge_ngram field"""
        query = {
            "query": {
                "match": {
                    "rid.prefix": rid_query
                }
            },
            "size": 100,
            "_source": True,
            "sort": [{"_score": {"order": "desc"}}],
            "aggs": {
                "docid_aggregation": {
                    "terms": {
                        "field": "docid.keyword",
                        "size": 100
                    }
                }
            }
        }

        data = self._execute_search(query)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        if not hits:
            return None

        # Filter by minimum prefix score for better precision
        high_quality_hits = [hit for hit in hits if hit['_score'] >= self.MIN_PREFIX_SCORE]

        # If no high-quality results, return None to fall back to fuzzy
        if not high_quality_hits:
            return None

        top_3 = high_quality_hits[:3]

        # Extract aggregation data
        docid_counts = []
        if "aggregations" in data and "docid_aggregation" in data["aggregations"]:
            docid_counts = [
                {
                    "docid": bucket["key"],
                    "count": bucket["doc_count"]
                }
                for bucket in data["aggregations"]["docid_aggregation"]["buckets"]
            ]

        return {
            "query": rid_query,
            "field": "rid",
            "match_type": "prefix",
            "confidence": "high" if len(high_quality_hits) <= self.MAX_PREFIX_RESULTS else "medium",
            "total_count": len(high_quality_hits),
            "docid_aggregation": docid_counts,
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in top_3
            ]
        }

    def _search_rid_fuzzy(self, rid_query: str) -> Optional[Dict]:
        """Search for RID fuzzy match using n-gram"""
        query = {
            "query": {
                "match": {
                    "rid": rid_query
                }
            },
            "size": 100,
            "_source": True,
            "sort": [{"_score": {"order": "desc"}}],
            "aggs": {
                "docid_aggregation": {
                    "terms": {
                        "field": "docid.keyword",
                        "size": 100
                    }
                }
            }
        }

        data = self._execute_search(query)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        if not hits:
            return None

        # Filter by minimum score
        high_scoring_hits = [hit for hit in hits if hit['_score'] >= self.MIN_SCORE_RID]

        if not high_scoring_hits:
            high_scoring_hits = hits[:3]  # Return top 3 even if below threshold

        top_3 = high_scoring_hits[:3]

        # Extract aggregation data
        docid_counts = []
        if "aggregations" in data and "docid_aggregation" in data["aggregations"]:
            docid_counts = [
                {
                    "docid": bucket["key"],
                    "count": bucket["doc_count"]
                }
                for bucket in data["aggregations"]["docid_aggregation"]["buckets"]
            ]

        return {
            "query": rid_query,
            "field": "rid",
            "match_type": "fuzzy",
            "confidence": "low" if len(high_scoring_hits) > 5 else "medium",  # More conservative confidence
            "total_count": len(high_scoring_hits),
            "docid_aggregation": docid_counts,
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in top_3
            ]
        }

    def fetch_information_by_rid(self, rid_query: str) -> Dict:
        """
        Fetch information by RID using cascading search strategy (exact → prefix → fuzzy)

        Args:
            rid_query: RID to search for (minimum 3 characters)

        Returns:
            Dictionary with:
            - top_3_matches: Top 3 matching records with full event data
            - total_count: Total number of all matching records
            - docid_aggregation: Aggregation showing count of records by DOCID
            - match_type: Type of match (exact/prefix/fuzzy)
            - confidence: Confidence level (very_high/high/medium/low)

        Strategy:
            Cascading approach (best precision):
            1. Try exact match first → If found, return
            2. Try prefix match → If found with good score, return
            3. Fall back to fuzzy match → Return best results
        """
        # Validation
        if len(rid_query) < 3:
            return {
                "error": "Query too short",
                "message": f"Please provide at least 3 characters (got {len(rid_query)})"
            }

        # Cascading strategy: exact → prefix → fuzzy
        exact_result = self._search_rid_exact(rid_query)
        if exact_result and "error" not in exact_result:
            return exact_result

        prefix_result = self._search_rid_prefix(rid_query)
        if prefix_result and "error" not in prefix_result:
            if prefix_result['total_count'] <= self.MAX_PREFIX_RESULTS:
                return prefix_result

        fuzzy_result = self._search_rid_fuzzy(rid_query)
        return fuzzy_result if fuzzy_result else {
            "message": "No matches found",
            "total_count": 0,
            "docid_aggregation": [],
            "top_3_matches": []
        }

    # ========================================================================
    # METHOD 2: fetch_information_by_docid
    # ========================================================================

    def _search_docid_exact(self, docid_query: str) -> Optional[Dict]:
        """Search for exact DOCID match using keyword field"""
        query = {
            "query": {
                "term": {
                    "docid.keyword": docid_query
                }
            },
            "size": 100,
            "_source": True,
            "aggs": {
                "rid_aggregation": {
                    "terms": {
                        "field": "rid.keyword",
                        "size": 100
                    }
                }
            }
        }

        data = self._execute_search(query)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        if not hits:
            return None

        top_3 = hits[:3]

        # Extract aggregation data
        rid_counts = []
        if "aggregations" in data and "rid_aggregation" in data["aggregations"]:
            rid_counts = [
                {
                    "rid": bucket["key"],
                    "count": bucket["doc_count"]
                }
                for bucket in data["aggregations"]["rid_aggregation"]["buckets"]
            ]

        return {
            "query": docid_query,
            "field": "docid",
            "match_type": "exact",
            "confidence": "very_high",
            "total_count": len(hits),
            "rid_aggregation": rid_counts,
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in top_3
            ]
        }

    def _search_docid_prefix(self, docid_query: str) -> Optional[Dict]:
        """Search for DOCID prefix match using edge_ngram field"""
        query = {
            "query": {
                "match": {
                    "docid.prefix": docid_query
                }
            },
            "size": 100,
            "_source": True,
            "sort": [{"_score": {"order": "desc"}}],
            "aggs": {
                "rid_aggregation": {
                    "terms": {
                        "field": "rid.keyword",
                        "size": 100
                    }
                }
            }
        }

        data = self._execute_search(query)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        if not hits:
            return None

        # Filter by minimum prefix score for better precision
        high_quality_hits = [hit for hit in hits if hit['_score'] >= self.MIN_PREFIX_SCORE]

        # If no high-quality results, return None to fall back to fuzzy
        if not high_quality_hits:
            return None

        top_3 = high_quality_hits[:3]

        # Extract aggregation data
        rid_counts = []
        if "aggregations" in data and "rid_aggregation" in data["aggregations"]:
            rid_counts = [
                {
                    "rid": bucket["key"],
                    "count": bucket["doc_count"]
                }
                for bucket in data["aggregations"]["rid_aggregation"]["buckets"]
            ]

        return {
            "query": docid_query,
            "field": "docid",
            "match_type": "prefix",
            "confidence": "high" if len(high_quality_hits) <= self.MAX_PREFIX_RESULTS else "medium",
            "total_count": len(high_quality_hits),
            "rid_aggregation": rid_counts,
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in top_3
            ]
        }

    def _search_docid_fuzzy(self, docid_query: str, use_fuzziness: bool = False) -> Optional[Dict]:
        """Search for DOCID fuzzy match using n-gram"""
        match_query = {"query": docid_query}
        if use_fuzziness:
            match_query["fuzziness"] = 1

        query = {
            "query": {
                "match": {
                    "docid": match_query
                }
            },
            "size": 100,
            "_source": True,
            "sort": [{"_score": {"order": "desc"}}],
            "aggs": {
                "rid_aggregation": {
                    "terms": {
                        "field": "rid.keyword",
                        "size": 100
                    }
                }
            }
        }

        data = self._execute_search(query)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        if not hits:
            return None

        # Filter by minimum score
        high_scoring_hits = [hit for hit in hits if hit['_score'] >= self.MIN_SCORE_DOCID]

        if not high_scoring_hits:
            high_scoring_hits = hits[:3]

        top_3 = high_scoring_hits[:3]

        # Extract aggregation data
        rid_counts = []
        if "aggregations" in data and "rid_aggregation" in data["aggregations"]:
            rid_counts = [
                {
                    "rid": bucket["key"],
                    "count": bucket["doc_count"]
                }
                for bucket in data["aggregations"]["rid_aggregation"]["buckets"]
            ]

        return {
            "query": docid_query,
            "field": "docid",
            "match_type": "fuzzy_with_typo_tolerance" if use_fuzziness else "fuzzy",
            "confidence": "low" if len(high_scoring_hits) > 5 else "medium",  # More conservative confidence
            "total_count": len(high_scoring_hits),
            "rid_aggregation": rid_counts,
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in top_3
            ]
        }

    def fetch_information_by_docid(self, docid_query: str) -> Dict:
        """
        Fetch information by DOCID using cascading search strategy (exact → prefix → fuzzy)

        Args:
            docid_query: DOCID to search for (minimum 4 characters)

        Returns:
            Dictionary with:
            - top_3_matches: Top 3 matching records with full event data
            - total_count: Total number of all matching records
            - rid_aggregation: Aggregation showing count of records by RID
            - match_type: Type of match (exact/prefix/fuzzy)
            - confidence: Confidence level (very_high/high/medium/low)

        Strategy:
            Cascading approach (best precision):
            1. Try exact match first → If found, return
            2. Try prefix match → If found with good score, return
            3. Fall back to fuzzy match → Return best results
        """
        # Validation
        if len(docid_query) < 4:
            return {
                "error": "Query too short",
                "message": f"Please provide at least 4 characters (got {len(docid_query)})"
            }

        # Cascading strategy: exact → prefix → fuzzy
        exact_result = self._search_docid_exact(docid_query)
        if exact_result and "error" not in exact_result:
            return exact_result

        prefix_result = self._search_docid_prefix(docid_query)
        if prefix_result and "error" not in prefix_result:
            if prefix_result['total_count'] <= self.MAX_PREFIX_RESULTS:
                return prefix_result

        fuzzy_result = self._search_docid_fuzzy(docid_query, use_fuzziness=False)
        return fuzzy_result if fuzzy_result else {
            "message": "No matches found",
            "total_count": 0,
            "rid_aggregation": [],
            "top_3_matches": []
        }

    # ========================================================================
    # METHOD 3: search_events
    # ========================================================================

    def search_events(
        self,
        search_query: str,
        filter_by_year: Optional[str] = None,
        filter_by_country: Optional[str] = None
    ) -> Dict:
        """
        Multi-field search on all searchable fields with optional filters and automatic spell tolerance

        Automatically handles typos and misspellings using fuzzy matching (fuzziness="AUTO"):
        - Tolerates 1-2 character edits
        - Examples: "climete" → "climate", "conferense" → "conference"

        Args:
            search_query: Search term to query across all fields (handles typos automatically)
            filter_by_year: Optional year filter (e.g., "2023")
            filter_by_country: Optional country filter (e.g., "India")

        Returns:
            Dictionary with:
            - top_3_matches: Top 3 search results
            - total_count: Total count of matches
            - count_by_year: Count aggregated by year (if filter_by_year is True)
            - count_by_country: Count aggregated by country (if filter_by_country is True)
        """
        # Build multi-field query with fuzzy matching for spell tolerance
        must_clauses = [
            {
                "multi_match": {
                    "query": search_query,
                    "fields": [
                        "rid^2",           # Boost rid
                        "rid.prefix^1.5",  # Boost rid prefix
                        "docid^2",         # Boost docid
                        "docid.prefix^1.5", # Boost docid prefix
                        "event_title^3",    # Highest boost for title
                        "event_theme^2",
                        "event_highlight^2",
                        "country^1.5",
                        "year^1.5"
                    ],
                    "type": "best_fields",
                    "operator": "or",
                    "fuzziness": "AUTO",      # Tolerates 1-2 character edits for typos
                    "prefix_length": 1,       # First character must match exactly
                    "max_expansions": 50      # Limits fuzzy term expansions for performance
                }
            }
        ]

        # Add filters if provided
        filter_clauses = []
        if filter_by_year:
            filter_clauses.append({"term": {"year": filter_by_year}})

        if filter_by_country:
            filter_clauses.append({"term": {"country": filter_by_country}})

        # Build query with filters
        query_body = {
            "bool": {
                "must": must_clauses
            }
        }

        if filter_clauses:
            query_body["bool"]["filter"] = filter_clauses

        # Build aggregations based on filters
        aggregations = {}

        if filter_by_year and filter_by_country:
            # Both filters: count for the specific combination
            aggregations["filtered_count"] = {
                "filters": {
                    "filters": {
                        f"{filter_by_year}_{filter_by_country}": {
                            "bool": {
                                "must": [
                                    {"term": {"year": filter_by_year}},
                                    {"term": {"country": filter_by_country}}
                                ]
                            }
                        }
                    }
                }
            }
        elif filter_by_year:
            # Only year filter: count by year
            aggregations["count_by_year"] = {
                "terms": {
                    "field": "year",
                    "size": 100
                }
            }
        elif filter_by_country:
            # Only country filter: count by country
            aggregations["count_by_country"] = {
                "terms": {
                    "field": "country",
                    "size": 100
                }
            }

        # Build complete search query
        search_query_body = {
            "query": query_body,
            "size": 100,  # Fetch more to get accurate counts
            "_source": True,
            "sort": [{"_score": {"order": "desc"}}]
        }

        if aggregations:
            search_query_body["aggs"] = aggregations

        # Execute search
        data = self._execute_search(search_query_body)
        if "error" in data:
            return data

        hits = data['hits']['hits']
        total_hits = data['hits']['total']['value']

        # Build response
        response = {
            "query": search_query,
            "total_count": len(hits),
            "top_3_matches": [
                {
                    "score": round(hit['_score'], 6),
                    **hit['_source']
                } for hit in hits[:3]
            ]
        }

        # Add aggregation results
        if "aggregations" in data:
            aggs = data['aggregations']

            if "count_by_year" in aggs:
                response["count_by_year"] = [
                    {
                        "year": bucket['key'],
                        "count": bucket['doc_count']
                    } for bucket in aggs['count_by_year']['buckets']
                ]

            if "count_by_country" in aggs:
                response["count_by_country"] = [
                    {
                        "country": bucket['key'],
                        "count": bucket['doc_count']
                    } for bucket in aggs['count_by_country']['buckets']
                ]

            if "filtered_count" in aggs:
                buckets = aggs['filtered_count']['buckets']
                for key, bucket_data in buckets.items():
                    response["filtered_count"] = {
                        "year": filter_by_year,
                        "country": filter_by_country,
                        "count": bucket_data['doc_count']
                    }

        # Add filter information
        if filter_by_year:
            response["filtered_by_year"] = filter_by_year
        if filter_by_country:
            response["filtered_by_country"] = filter_by_country

        return response


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

def main():
    """Example usage of the three search methods"""
    search = EventsSearch()

    print("="*70)
    print("OpenSearch Events Index - Search Methods Demo")
    print("="*70)

    # Example 1: Search by RID
    print("\n1. FETCH INFORMATION BY RID")
    print("-"*70)
    result = search.fetch_information_by_rid("65478902")
    print(json.dumps(result, indent=2))

    # Example 2: Search by DOCID
    print("\n2. FETCH INFORMATION BY DOCID")
    print("-"*70)
    result = search.fetch_information_by_docid("98979-99999-abc-0-a-1")
    print(json.dumps(result, indent=2))

    # Example 3: Multi-field search without filters
    print("\n3. SEARCH EVENTS - No Filters")
    print("-"*70)
    result = search.search_events("climate change")
    print(json.dumps(result, indent=2))

    # Example 4: Multi-field search with year filter
    print("\n4. SEARCH EVENTS - Filter by Year")
    print("-"*70)
    result = search.search_events("summit", filter_by_year="2023")
    print(json.dumps(result, indent=2))

    # Example 5: Multi-field search with country filter
    print("\n5. SEARCH EVENTS - Filter by Country")
    print("-"*70)
    result = search.search_events("conference", filter_by_country="India")
    print(json.dumps(result, indent=2))

    # Example 6: Multi-field search with both filters
    print("\n6. SEARCH EVENTS - Filter by Year AND Country")
    print("-"*70)
    result = search.search_events("meeting", filter_by_year="2023", filter_by_country="India")
    print(json.dumps(result, indent=2))

    # Example 7: Search with typos (spell tolerance demonstration)
    print("\n7. SEARCH EVENTS - With Typos (Spell Tolerance)")
    print("-"*70)
    print("Query with typos: 'climete sumit' (should find 'climate summit')")
    result = search.search_events("climete sumit")
    print(json.dumps(result, indent=2))

    print("\n" + "="*70)


if __name__ == "__main__":
    main()
