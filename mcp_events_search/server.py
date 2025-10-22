#!/usr/bin/env python3
"""
FastMCP Events Search Server
Exposes 3 optimized search methods for OpenSearch events index using cascading strategy.

Tools:
1. search_by_rid - High-precision RID search (exact → prefix → fuzzy)
2. search_by_docid - High-precision DOCID search (exact → prefix → fuzzy)
3. search_events - Multi-field search with filters and spell tolerance
"""
import os
import json
import logging
from typing import Optional
import aiohttp
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get OpenSearch configuration from environment
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
INDEX_NAME = os.getenv("INDEX_NAME", "events")

# Optimized score thresholds for high precision
MIN_SCORE_RID = float(os.getenv("MIN_SCORE_RID", "2.5"))
MIN_SCORE_DOCID = float(os.getenv("MIN_SCORE_DOCID", "3.5"))
MIN_PREFIX_SCORE = float(os.getenv("MIN_PREFIX_SCORE", "1.0"))
MAX_PREFIX_RESULTS = int(os.getenv("MAX_PREFIX_RESULTS", "8"))

# Initialize FastMCP server
mcp = FastMCP("Events Search Server")


# Helper function for making OpenSearch requests
async def opensearch_request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """Make async HTTP request to OpenSearch."""
    url = f"{OPENSEARCH_URL}/{path}"

    try:
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"OpenSearch error ({response.status}): {error_text}")

            elif method == "POST":
                headers = {"Content-Type": "application/json"}
                async with session.post(url, json=body, headers=headers) as response:
                    if response.status in [200, 201]:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        raise Exception(f"OpenSearch error ({response.status}): {error_text}")

    except aiohttp.ClientError as e:
        logger.error(f"HTTP request failed: {e}")
        raise Exception(f"Failed to connect to OpenSearch at {OPENSEARCH_URL}: {str(e)}")


@mcp.tool()
async def search_by_rid(rid_query: str) -> str:
    """
    Search events by RID (Resource ID). Use when you have a full or partial RID.

    Finds events using cascading strategy (exact → prefix → fuzzy) optimized for precision.
    Returns top 3 matches with confidence levels and DOCID aggregation.

    Args:
        rid_query: RID to search (min 3 chars). Examples: "65478902", "654789", "654"

    Returns:
        JSON with match_type (exact/prefix/fuzzy), confidence (very_high/high/medium/low),
        total_count, docid_aggregation, and top_3_matches with full event details
    """
    # Validation
    if not rid_query or len(rid_query) < 3:
        return json.dumps({
            "error": "Query too short",
            "message": f"Please provide at least 3 characters (got {len(rid_query) if rid_query else 0})"
        }, indent=2)

    try:
        # Try cascading search: exact → prefix → fuzzy
        result = await _search_rid_cascading(rid_query)

        if not result:
            return json.dumps({
                "message": "No matches found",
                "query": rid_query,
                "total_count": 0,
                "top_3_matches": []
            }, indent=2)

        # Format response
        response = {
            "query": rid_query,
            "field": "rid",
            "match_type": result.get("match_type"),
            "confidence": result.get("confidence"),
            "total_count": result.get("total_count"),
            "docid_aggregation": result.get("docid_aggregation", []),
            "top_3_matches": result.get("top_3_matches", [])
        }

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"RID search failed: {e}")
        return json.dumps({"error": f"Search failed: {str(e)}"}, indent=2)


@mcp.tool()
async def search_by_docid(docid_query: str) -> str:
    """
    Search events by DOCID (Document ID). Use when you have a full or partial DOCID.

    Finds events using cascading strategy (exact → prefix → fuzzy) optimized for precision.
    Returns top 3 matches with confidence levels and RID aggregation.

    Args:
        docid_query: DOCID to search (min 4 chars). Examples: "98979-99999-abc-0-a-1", "98979-9999", "9897"

    Returns:
        JSON with match_type (exact/prefix/fuzzy), confidence (very_high/high/medium/low),
        total_count, rid_aggregation, and top_3_matches with full event details
    """
    # Validation
    if not docid_query or len(docid_query) < 4:
        return json.dumps({
            "error": "Query too short",
            "message": f"Please provide at least 4 characters (got {len(docid_query) if docid_query else 0})"
        }, indent=2)

    try:
        # Try cascading search: exact → prefix → fuzzy
        result = await _search_docid_cascading(docid_query)

        if not result:
            return json.dumps({
                "message": "No matches found",
                "query": docid_query,
                "total_count": 0,
                "top_3_matches": []
            }, indent=2)

        # Format response
        response = {
            "query": docid_query,
            "field": "docid",
            "match_type": result.get("match_type"),
            "confidence": result.get("confidence"),
            "total_count": result.get("total_count"),
            "rid_aggregation": result.get("rid_aggregation", []),
            "top_3_matches": result.get("top_3_matches", [])
        }

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"DOCID search failed: {e}")
        return json.dumps({"error": f"Search failed: {str(e)}"}, indent=2)


@mcp.tool()
async def search_events(
    query: str,
    filter_by_year: Optional[str] = None,
    filter_by_country: Optional[str] = None
) -> str:
    """
    Search events by text content (title, theme, etc). Use for natural language queries.

    Searches across event_title, event_theme, event_highlight, rid, docid, country, year.
    Handles typos automatically (e.g., "climete" finds "climate"). Optional year/country filters.
    Returns top 3 matches with aggregations based on filters applied.

    Args:
        query: Search text (handles typos). Examples: "climate summit", "technology conference"
        filter_by_year: Optional year filter. Examples: "2023", "2022"
        filter_by_country: Optional country filter. Examples: "India", "Denmark"

    Returns:
        JSON with total_count, optional aggregations (count_by_year, count_by_country, or filtered_count),
        and top_3_matches with full event details
    """
    if not query:
        return json.dumps({
            "error": "Empty query",
            "message": "Please provide a search query"
        }, indent=2)

    try:
        # Build multi-field query with fuzzy matching
        must_clauses = [{
            "multi_match": {
                "query": query,
                "fields": [
                    "rid^2",
                    "rid.prefix^1.5",
                    "docid^2",
                    "docid.prefix^1.5",
                    "event_title^3",
                    "event_theme^2",
                    "event_highlight^2",
                    "country^1.5",
                    "year^1.5"
                ],
                "type": "best_fields",
                "operator": "or",
                "fuzziness": "AUTO",      # Spell tolerance
                "prefix_length": 1,       # First char must match
                "max_expansions": 50      # Performance limit
            }
        }]

        # Add filters
        filter_clauses = []
        if filter_by_year:
            filter_clauses.append({"term": {"year": filter_by_year}})
        if filter_by_country:
            filter_clauses.append({"term": {"country": filter_by_country}})

        # Build query
        query_body = {
            "bool": {
                "must": must_clauses
            }
        }
        if filter_clauses:
            query_body["bool"]["filter"] = filter_clauses

        # Build aggregations
        aggregations = {}
        if filter_by_year and filter_by_country:
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
            aggregations["count_by_year"] = {
                "terms": {"field": "year", "size": 100}
            }
        elif filter_by_country:
            aggregations["count_by_country"] = {
                "terms": {"field": "country", "size": 100}
            }

        # Build search request
        search_body = {
            "query": query_body,
            "size": 100,
            "_source": True,
            "sort": [{"_score": {"order": "desc"}}]
        }
        if aggregations:
            search_body["aggs"] = aggregations

        # Execute search
        data = await opensearch_request("POST", f"{INDEX_NAME}/_search", search_body)

        hits = data.get("hits", {}).get("hits", [])
        total_hits = data.get("hits", {}).get("total", {}).get("value", 0)

        # Build response
        response = {
            "query": query,
            "total_count": len(hits)
        }

        # Add filter info
        if filter_by_year:
            response["filtered_by_year"] = filter_by_year
        if filter_by_country:
            response["filtered_by_country"] = filter_by_country

        # Add aggregations
        if "aggregations" in data:
            aggs = data["aggregations"]

            if "count_by_year" in aggs:
                response["count_by_year"] = [
                    {"year": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in aggs["count_by_year"]["buckets"]
                ]

            if "count_by_country" in aggs:
                response["count_by_country"] = [
                    {"country": bucket["key"], "count": bucket["doc_count"]}
                    for bucket in aggs["count_by_country"]["buckets"]
                ]

            if "filtered_count" in aggs:
                buckets = aggs["filtered_count"]["buckets"]
                for key, bucket_data in buckets.items():
                    response["filtered_count"] = {
                        "year": filter_by_year,
                        "country": filter_by_country,
                        "count": bucket_data["doc_count"]
                    }

        # Add top 3 matches
        top_3 = hits[:3]
        response["top_3_matches"] = [
            {
                "score": round(hit["_score"], 6),
                **hit["_source"]
            }
            for hit in top_3
        ]

        return json.dumps(response, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Events search failed: {e}")
        return json.dumps({"error": f"Search failed: {str(e)}"}, indent=2)


# ============================================================================
# HELPER FUNCTIONS - Cascading Search Implementation
# ============================================================================

async def _search_rid_cascading(rid_query: str) -> Optional[dict]:
    """Execute cascading RID search: exact → prefix → fuzzy"""
    # Try exact match
    exact_result = await _search_rid_exact(rid_query)
    if exact_result:
        return exact_result

    # Try prefix match
    prefix_result = await _search_rid_prefix(rid_query)
    if prefix_result and prefix_result.get("total_count", 0) <= MAX_PREFIX_RESULTS:
        return prefix_result

    # Fallback to fuzzy
    return await _search_rid_fuzzy(rid_query)


async def _search_docid_cascading(docid_query: str) -> Optional[dict]:
    """Execute cascading DOCID search: exact → prefix → fuzzy"""
    # Try exact match
    exact_result = await _search_docid_exact(docid_query)
    if exact_result:
        return exact_result

    # Try prefix match
    prefix_result = await _search_docid_prefix(docid_query)
    if prefix_result and prefix_result.get("total_count", 0) <= MAX_PREFIX_RESULTS:
        return prefix_result

    # Fallback to fuzzy
    return await _search_docid_fuzzy(docid_query)


async def _search_rid_exact(rid_query: str) -> Optional[dict]:
    """Search for exact RID match using keyword field"""
    query = {
        "query": {"term": {"rid.keyword": rid_query}},
        "size": 100,
        "_source": True,
        "aggs": {
            "docid_aggregation": {
                "terms": {"field": "docid.keyword", "size": 100}
            }
        }
    }

    data = await opensearch_request("POST", f"{INDEX_NAME}/_search", query)
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        return None

    return {
        "match_type": "exact",
        "confidence": "very_high",
        "total_count": len(hits),
        "docid_aggregation": [
            {"docid": b["key"], "count": b["doc_count"]}
            for b in data.get("aggregations", {}).get("docid_aggregation", {}).get("buckets", [])
        ],
        "top_3_matches": [{"score": round(h["_score"], 6), **h["_source"]} for h in hits[:3]]
    }


async def _search_rid_prefix(rid_query: str) -> Optional[dict]:
    """Search for RID prefix match using edge_ngram"""
    query = {
        "query": {"match": {"rid.prefix": rid_query}},
        "size": 100,
        "_source": True,
        "sort": [{"_score": {"order": "desc"}}],
        "aggs": {
            "docid_aggregation": {
                "terms": {"field": "docid.keyword", "size": 100}
            }
        }
    }

    data = await opensearch_request("POST", f"{INDEX_NAME}/_search", query)
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        return None

    # Filter by minimum prefix score
    high_quality_hits = [h for h in hits if h["_score"] >= MIN_PREFIX_SCORE]

    if not high_quality_hits:
        return None

    return {
        "match_type": "prefix",
        "confidence": "high" if len(high_quality_hits) <= MAX_PREFIX_RESULTS else "medium",
        "total_count": len(high_quality_hits),
        "docid_aggregation": [
            {"docid": b["key"], "count": b["doc_count"]}
            for b in data.get("aggregations", {}).get("docid_aggregation", {}).get("buckets", [])
        ],
        "top_3_matches": [{"score": round(h["_score"], 6), **h["_source"]} for h in high_quality_hits[:3]]
    }


async def _search_rid_fuzzy(rid_query: str) -> Optional[dict]:
    """Search for RID fuzzy match using n-gram"""
    query = {
        "query": {"match": {"rid": rid_query}},
        "size": 100,
        "_source": True,
        "sort": [{"_score": {"order": "desc"}}],
        "aggs": {
            "docid_aggregation": {
                "terms": {"field": "docid.keyword", "size": 100}
            }
        }
    }

    data = await opensearch_request("POST", f"{INDEX_NAME}/_search", query)
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        return None

    # Filter by minimum score
    high_scoring_hits = [h for h in hits if h["_score"] >= MIN_SCORE_RID]

    if not high_scoring_hits:
        high_scoring_hits = hits[:3]

    return {
        "match_type": "fuzzy",
        "confidence": "low" if len(high_scoring_hits) > 5 else "medium",
        "total_count": len(high_scoring_hits),
        "docid_aggregation": [
            {"docid": b["key"], "count": b["doc_count"]}
            for b in data.get("aggregations", {}).get("docid_aggregation", {}).get("buckets", [])
        ],
        "top_3_matches": [{"score": round(h["_score"], 6), **h["_source"]} for h in high_scoring_hits[:3]]
    }


async def _search_docid_exact(docid_query: str) -> Optional[dict]:
    """Search for exact DOCID match using keyword field"""
    query = {
        "query": {"term": {"docid.keyword": docid_query}},
        "size": 100,
        "_source": True,
        "aggs": {
            "rid_aggregation": {
                "terms": {"field": "rid.keyword", "size": 100}
            }
        }
    }

    data = await opensearch_request("POST", f"{INDEX_NAME}/_search", query)
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        return None

    return {
        "match_type": "exact",
        "confidence": "very_high",
        "total_count": len(hits),
        "rid_aggregation": [
            {"rid": b["key"], "count": b["doc_count"]}
            for b in data.get("aggregations", {}).get("rid_aggregation", {}).get("buckets", [])
        ],
        "top_3_matches": [{"score": round(h["_score"], 6), **h["_source"]} for h in hits[:3]]
    }


async def _search_docid_prefix(docid_query: str) -> Optional[dict]:
    """Search for DOCID prefix match using edge_ngram"""
    query = {
        "query": {"match": {"docid.prefix": docid_query}},
        "size": 100,
        "_source": True,
        "sort": [{"_score": {"order": "desc"}}],
        "aggs": {
            "rid_aggregation": {
                "terms": {"field": "rid.keyword", "size": 100}
            }
        }
    }

    data = await opensearch_request("POST", f"{INDEX_NAME}/_search", query)
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        return None

    # Filter by minimum prefix score
    high_quality_hits = [h for h in hits if h["_score"] >= MIN_PREFIX_SCORE]

    if not high_quality_hits:
        return None

    return {
        "match_type": "prefix",
        "confidence": "high" if len(high_quality_hits) <= MAX_PREFIX_RESULTS else "medium",
        "total_count": len(high_quality_hits),
        "rid_aggregation": [
            {"rid": b["key"], "count": b["doc_count"]}
            for b in data.get("aggregations", {}).get("rid_aggregation", {}).get("buckets", [])
        ],
        "top_3_matches": [{"score": round(h["_score"], 6), **h["_source"]} for h in high_quality_hits[:3]]
    }


async def _search_docid_fuzzy(docid_query: str) -> Optional[dict]:
    """Search for DOCID fuzzy match using n-gram"""
    query = {
        "query": {"match": {"docid": docid_query}},
        "size": 100,
        "_source": True,
        "sort": [{"_score": {"order": "desc"}}],
        "aggs": {
            "rid_aggregation": {
                "terms": {"field": "rid.keyword", "size": 100}
            }
        }
    }

    data = await opensearch_request("POST", f"{INDEX_NAME}/_search", query)
    hits = data.get("hits", {}).get("hits", [])

    if not hits:
        return None

    # Filter by minimum score
    high_scoring_hits = [h for h in hits if h["_score"] >= MIN_SCORE_DOCID]

    if not high_scoring_hits:
        high_scoring_hits = hits[:3]

    return {
        "match_type": "fuzzy",
        "confidence": "low" if len(high_scoring_hits) > 5 else "medium",
        "total_count": len(high_scoring_hits),
        "rid_aggregation": [
            {"rid": b["key"], "count": b["doc_count"]}
            for b in data.get("aggregations", {}).get("rid_aggregation", {}).get("buckets", [])
        ],
        "top_3_matches": [{"score": round(h["_score"], 6), **h["_source"]} for h in high_scoring_hits[:3]]
    }


if __name__ == "__main__":
    # Get server configuration from environment
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8002"))

    # Run the FastMCP server in SSE mode
    logger.info(f"Starting FastMCP Events Search Server in SSE mode")
    logger.info(f"Server: http://{host}:{port}")
    logger.info(f"OpenSearch URL: {OPENSEARCH_URL}")
    logger.info(f"Target Index: {INDEX_NAME}")
    logger.info(f"Optimized Parameters: MIN_SCORE_RID={MIN_SCORE_RID}, MIN_SCORE_DOCID={MIN_SCORE_DOCID}, MIN_PREFIX_SCORE={MIN_PREFIX_SCORE}, MAX_PREFIX_RESULTS={MAX_PREFIX_RESULTS}")

    # Run with SSE transport (HTTP mode)
    mcp.run(transport="sse", host=host, port=port)
