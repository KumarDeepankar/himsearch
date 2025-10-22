#!/usr/bin/env python3
"""
FastMCP OpenSearch Server
Implements 4 sophisticated OpenSearch tools using FastMCP framework
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
INDEX_NAME = "events"

# Initialize FastMCP server
mcp = FastMCP("OpenSearch Events Server")


# Helper function for making OpenSearch requests
async def opensearch_request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """Make HTTP request to OpenSearch."""
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
async def search_events_hybrid(query: str, size: int = 10) -> str:
    """
    Advanced hybrid search combining standard and ngram analyzers for best fuzzy matching results.

    Use this when you need the most robust fuzzy search that can handle misspellings,
    partial words, and variations better than standard search. Best for dealing with
    uncertain or incomplete search terms. Returns highest quality fuzzy matches.

    Args:
        query: Search query text. Can include misspellings, partial words, or variations.
               Examples: 'clima sumit' (misspelled), 'tech innov' (partial), 'envronment' (misspelled)
        size: Number of results to return. Default: 10, minimum: 1, maximum: 100

    Returns:
        JSON formatted search results with event details
    """
    size = min(max(size, 1), 100)  # Clamp between 1 and 100

    if not query:
        return "Error: No query provided"

    search_body = {
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["event_title^3", "event_theme^2.5"],
                            "fuzziness": "AUTO",
                            "boost": 2
                        }
                    },
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["event_title.ngram", "event_theme.ngram"],
                            "boost": 1
                        }
                    }
                ],
                "minimum_should_match": 1
            }
        },
        "size": size
    }

    try:
        result = await opensearch_request("POST", f"{INDEX_NAME}/_search", search_body)

        hits = result.get("hits", {}).get("hits", [])
        total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

        if not hits:
            return f"No events found matching query: '{query}'"

        events = []
        for hit in hits:
            source = hit.get("_source", {})
            events.append({
                "id": hit.get("_id"),
                "score": hit.get("_score"),
                "year": source.get("year"),
                "country": source.get("country"),
                "title": source.get("event_title"),
                "theme": source.get("event_theme"),
                "attendance": source.get("event_count")
            })

        response = f"Found {total_hits} events matching hybrid search for '{query}'. Showing top {len(hits)} results:\n\n"
        response += json.dumps(events, indent=2)

        return response

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        return f"Error in hybrid search: {str(e)}"


@mcp.tool()
async def search_and_filter_events(
    query: str = "",
    country: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    min_attendance: Optional[int] = None,
    max_attendance: Optional[int] = None,
    size: int = 10,
    sort_by: str = "relevance",
    sort_order: str = "desc"
) -> str:
    """
    Search events with multiple filters combined (country, year range, attendance) and custom sorting.

    Best for complex queries requiring multiple criteria. Use this when you need to combine
    several filters together (e.g., technology events in Denmark from 2020-2023 with 100+ attendees).
    Returns precisely filtered and sorted results.

    Args:
        query: Search query text (optional). Searches across all event fields. Leave empty to filter only
        country: Country filter (optional). Must be 'Denmark' or 'Dominica'
        start_year: Start year for range filter (optional). 4-digit year
        end_year: End year for range filter (optional). 4-digit year
        min_attendance: Minimum attendance (optional)
        max_attendance: Maximum attendance (optional)
        size: Number of results to return. Default: 10, minimum: 1, maximum: 100
        sort_by: Sort field. Options: 'year', 'event_count', 'relevance'. Default: 'relevance'
        sort_order: Sort order. Options: 'asc' (ascending), 'desc' (descending). Default: 'desc'

    Returns:
        JSON formatted filtered search results
    """
    size = min(max(size, 1), 100)

    # Build complex bool query
    bool_query = {"filter": []}

    # Add search query if provided
    if query:
        bool_query["must"] = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"],
                    "fuzziness": "AUTO"
                }
            }
        ]

    # Add filters
    if country:
        bool_query["filter"].append({"term": {"country": country}})

    if start_year and end_year:
        bool_query["filter"].append({
            "range": {"year": {"gte": start_year, "lte": end_year}}
        })
    elif start_year:
        bool_query["filter"].append({"range": {"year": {"gte": start_year}}})
    elif end_year:
        bool_query["filter"].append({"range": {"year": {"lte": end_year}}})

    if min_attendance or max_attendance:
        range_query = {}
        if min_attendance:
            range_query["gte"] = min_attendance
        if max_attendance:
            range_query["lte"] = max_attendance
        bool_query["filter"].append({"range": {"event_count": range_query}})

    search_body = {
        "query": {"bool": bool_query} if bool_query["filter"] or query else {"match_all": {}},
        "size": size
    }

    # Add sorting
    if sort_by != "relevance":
        search_body["sort"] = [{
            sort_by: {
                "order": sort_order,
                "unmapped_type": "long"
            }
        }]

    try:
        result = await opensearch_request("POST", f"{INDEX_NAME}/_search", search_body)

        hits = result.get("hits", {}).get("hits", [])
        total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

        # Build filter description
        filters = []
        if query:
            filters.append(f"query='{query}'")
        if country:
            filters.append(f"country={country}")
        if start_year or end_year:
            filters.append(f"year=[{start_year or 'any'}-{end_year or 'any'}]")
        if min_attendance or max_attendance:
            filters.append(f"attendance=[{min_attendance or 'any'}-{max_attendance or 'any'}]")

        filter_desc = " AND ".join(filters) if filters else "all events"

        if not hits:
            return f"No events found matching {filter_desc}"

        events = []
        for hit in hits:
            source = hit.get("_source", {})
            events.append({
                "id": hit.get("_id"),
                "score": hit.get("_score"),
                "year": source.get("year"),
                "country": source.get("country"),
                "title": source.get("event_title"),
                "theme": source.get("event_theme"),
                "attendance": source.get("event_count")
            })

        response = f"Found {total_hits} events matching {filter_desc}. Showing top {len(hits)} results:\n\n"
        response += json.dumps(events, indent=2)

        return response

    except Exception as e:
        logger.error(f"Search and filter failed: {e}")
        return f"Error in search and filter: {str(e)}"


@mcp.tool()
async def get_event_attendance_stats(
    year: Optional[int] = None,
    country: Optional[str] = None
) -> str:
    """
    Get statistical analysis of event attendance including min, max, average, sum, and count.

    Use this for attendance analysis, capacity planning, or understanding event size distribution.
    Returns comprehensive attendance metrics: minimum, maximum, average, total sum, and event count.

    Args:
        year: Optional year filter. Use a 4-digit year to get stats for a specific year
        country: Optional country filter. Use 'Denmark' or 'Dominica' for specific country stats

    Returns:
        JSON formatted attendance statistics
    """
    # Build query with optional filters
    bool_query = {"filter": []}
    if year:
        bool_query["filter"].append({"term": {"year": year}})
    if country:
        bool_query["filter"].append({"term": {"country": country}})

    query = {"bool": bool_query} if bool_query["filter"] else {"match_all": {}}

    search_body = {
        "size": 0,
        "query": query,
        "aggs": {
            "attendance_stats": {
                "stats": {"field": "event_count"}
            }
        }
    }

    try:
        result = await opensearch_request("POST", f"{INDEX_NAME}/_search", search_body)

        stats_data = result.get("aggregations", {}).get("attendance_stats", {})

        if not stats_data:
            return "No attendance statistics available"

        # Handle None values from OpenSearch
        count = stats_data.get("count")
        min_val = stats_data.get("min")
        max_val = stats_data.get("max")
        avg_val = stats_data.get("avg")
        sum_val = stats_data.get("sum")

        stats = {
            "count": int(count) if count is not None else 0,
            "min": int(min_val) if min_val is not None else 0,
            "max": int(max_val) if max_val is not None else 0,
            "avg": round(avg_val, 2) if avg_val is not None else 0.0,
            "sum": int(sum_val) if sum_val is not None else 0
        }

        filters = []
        if year:
            filters.append(f"year={year}")
        if country:
            filters.append(f"country={country}")
        filter_str = f" ({', '.join(filters)})" if filters else ""

        response = f"Attendance statistics{filter_str}:\n\n"
        response += json.dumps(stats, indent=2)

        return response

    except Exception as e:
        logger.error(f"Get attendance stats failed: {e}")
        return f"Error getting attendance stats: {str(e)}"


@mcp.tool()
async def list_all_events(
    size: int = 10,
    from_offset: int = 0,
    sort_by: str = "year",
    sort_order: str = "desc"
) -> str:
    """
    List all events with pagination and sorting support.

    Use this to browse through all events in the index, get a sample of events, or retrieve
    events in a specific order. Perfect for data exploration or getting an overview.
    Returns paginated list of events with basic information.

    Args:
        size: Number of events to return per page. Default: 10, minimum: 1, maximum: 100
        from_offset: Offset for pagination (starting position). Default: 0.
                    Use for pagination - e.g., from=0 for page 1, from=10 for page 2
        sort_by: Sort field. Options: 'year', 'event_count'. Default: 'year'
        sort_order: Sort order. Options: 'asc' (ascending), 'desc' (descending). Default: 'desc'

    Returns:
        JSON formatted paginated list of events
    """
    size = min(max(size, 1), 100)
    from_offset = max(from_offset, 0)

    search_body = {
        "query": {"match_all": {}},
        "size": size,
        "from": from_offset,
        "sort": [{
            sort_by: {
                "order": sort_order,
                "unmapped_type": "long"
            }
        }]
    }

    try:
        result = await opensearch_request("POST", f"{INDEX_NAME}/_search", search_body)

        hits = result.get("hits", {}).get("hits", [])
        total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

        if not hits:
            return "No events found in the index"

        events = []
        for hit in hits:
            source = hit.get("_source", {})
            events.append({
                "id": hit.get("_id"),
                "year": source.get("year"),
                "country": source.get("country"),
                "title": source.get("event_title"),
                "theme": source.get("event_theme"),
                "attendance": source.get("event_count")
            })

        response = f"Total events: {total_hits}. Showing {len(hits)} events (offset: {from_offset}, sorted by {sort_by} {sort_order}):\n\n"
        response += json.dumps(events, indent=2)

        return response

    except Exception as e:
        logger.error(f"List events failed: {e}")
        return f"Error listing events: {str(e)}"


if __name__ == "__main__":
    # Get server configuration from environment
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8001"))

    # Run the FastMCP server in SSE mode by default
    logger.info(f"Starting FastMCP OpenSearch Server in SSE mode")
    logger.info(f"Server: http://{host}:{port}")
    logger.info(f"OpenSearch URL: {OPENSEARCH_URL}")
    logger.info(f"Target Index: {INDEX_NAME}")

    # Run with SSE transport (HTTP mode)
    mcp.run(transport="sse", host=host, port=port)
