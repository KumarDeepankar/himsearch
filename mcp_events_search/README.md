# Events Search MCP Server

FastMCP server exposing three optimized search methods for OpenSearch events index using cascading strategy (70% accuracy, excellent precision).

## Overview

This MCP server provides AI agents with access to three high-precision search tools:

1. **search_by_rid** - Search by RID (Resource ID) using cascading strategy
2. **search_by_docid** - Search by DOCID (Document ID) using cascading strategy
3. **search_events** - Multi-field search with filters and automatic spell tolerance

All tools use optimized cascading search (exact → prefix → fuzzy) for maximum precision on top 3 results.

---

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

---

## Quick Start

### Run the Server

```bash
# Using default configuration (localhost:8002)
python server.py

# With custom configuration
OPENSEARCH_URL=http://localhost:9200 \
INDEX_NAME=events \
HOST=0.0.0.0 \
PORT=8002 \
python server.py
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENSEARCH_URL` | `http://localhost:9200` | OpenSearch server URL |
| `INDEX_NAME` | `events` | Target index name |
| `HOST` | `127.0.0.1` | Server bind address |
| `PORT` | `8002` | Server port |
| `MIN_SCORE_RID` | `2.5` | Minimum score for RID fuzzy matches |
| `MIN_SCORE_DOCID` | `3.5` | Minimum score for DOCID fuzzy matches |
| `MIN_PREFIX_SCORE` | `1.0` | Minimum score for prefix matches |
| `MAX_PREFIX_RESULTS` | `8` | Maximum prefix results before fallback |

---

## Tools

### 1. search_by_rid

Search for events by RID using cascading strategy.

**When to use**: RID-based lookups, finding events by resource identifier.

**Cascading strategy**:
- Exact match (first): Complete RID match → ~1 result, very_high confidence
- Prefix match (second): RIDs starting with query → ~1-3 results, high confidence
- Fuzzy match (fallback): Partial character matches → ~3 results, medium/low confidence

**Parameters**:
- `rid_query` (string, required): RID to search for (minimum 3 characters)

**Example**:
```json
{
  "rid_query": "65478902"
}
```

**Returns**:
```json
{
  "query": "65478902",
  "field": "rid",
  "match_type": "exact",
  "confidence": "very_high",
  "total_count": 1,
  "docid_aggregation": [
    {"docid": "98979-99999-abc-0-a-1", "count": 1}
  ],
  "top_3_matches": [...]
}
```

---

### 2. search_by_docid

Search for events by DOCID using cascading strategy.

**When to use**: DOCID-based lookups, document tracking.

**Cascading strategy**:
- Exact match (first): Complete DOCID match → ~1 result, very_high confidence
- Prefix match (second): DOCIDs starting with query → ~1-3 results, high confidence
- Fuzzy match (fallback): Partial character matches → ~3 results, medium/low confidence

**Parameters**:
- `docid_query` (string, required): DOCID to search for (minimum 4 characters)

**Example**:
```json
{
  "docid_query": "98979-99999-abc-0-a-1"
}
```

**Returns**:
```json
{
  "query": "98979-99999-abc-0-a-1",
  "field": "docid",
  "match_type": "exact",
  "confidence": "very_high",
  "total_count": 1,
  "rid_aggregation": [
    {"rid": "65478902", "count": 1}
  ],
  "top_3_matches": [...]
}
```

---

### 3. search_events

Multi-field search with filters and automatic spell tolerance.

**When to use**: General event search, content discovery, natural language queries.

**Spell tolerance**: Automatically handles typos!
- ✅ "climete" → finds "climate"
- ✅ "conferense" → finds "conference"
- ✅ "tecnology" → finds "technology"

**Searchable fields** (with boost factors):
- event_title (3x) - Highest priority
- rid, docid, event_theme, event_highlight (2x) - High priority
- rid.prefix, docid.prefix, country, year (1.5x) - Medium priority

**Parameters**:
- `query` (string, required): Search query text (handles typos automatically)
- `filter_by_year` (string, optional): Year filter (e.g., "2023")
- `filter_by_country` (string, optional): Country filter (e.g., "India")

**Example**:
```json
{
  "query": "climate summit",
  "filter_by_year": "2023"
}
```

**Returns**:
```json
{
  "query": "climate summit",
  "filtered_by_year": "2023",
  "total_count": 4,
  "count_by_year": [
    {"year": "2023", "count": 4},
    {"year": "2022", "count": 2}
  ],
  "top_3_matches": [...]
}
```

---

## Performance

### Accuracy
- **Overall**: 70% test framework accuracy (80% real-world)
- **Exact match**: 100%
- **Prefix match**: 50% (but high result quality)
- **Fuzzy match**: 100%

### Precision
- **Exact queries**: ~1 result average
- **Prefix queries**: ~1-3 results average
- **Fuzzy queries**: ~3 results average
- **10-char specific queries**: ~1 result (excellent)

### Response Format
- Returns top 3 highest-scoring matches
- Includes total count of all matches
- Includes aggregations (DOCID for RID search, RID for DOCID search)
- Match type and confidence level indicators

---

## Architecture

### Cascading Search Strategy

All RID and DOCID searches use optimized cascading:

1. **Try Exact Match First**
   - Uses `.keyword` field
   - Score threshold: 1.0
   - Returns immediately if found

2. **Try Prefix Match Second**
   - Uses `.prefix` field with edge_ngram
   - Score threshold: 1.0 (MIN_PREFIX_SCORE)
   - Max results: 8 (MAX_PREFIX_RESULTS)
   - Falls back to fuzzy if too many results

3. **Fallback to Fuzzy Match**
   - Uses base field with n-gram
   - Score threshold: 2.5 (RID) or 3.5 (DOCID)
   - Returns top 3 results

### Spell Tolerance (search_events only)

Multi-field search includes fuzzy matching:
- `fuzziness: "AUTO"` - Tolerates 1-2 character edits
- `prefix_length: 1` - First character must match
- `max_expansions: 50` - Performance limit

---

## Integration with AI Agents

### MCP Protocol

This server uses FastMCP with SSE (Server-Sent Events) transport:
- **Protocol**: Model Context Protocol (MCP)
- **Transport**: SSE (HTTP)
- **Endpoint**: `http://localhost:8002` (default)

### Tool Descriptions

Each tool includes comprehensive descriptions for agents:
- **When to use**: Clear guidance on use cases
- **How it works**: Detailed explanation of search strategy
- **Parameters**: Type, requirements, and examples
- **Returns**: Format and content description

### Example Agent Usage

```python
# Agent discovers and calls tools via MCP protocol

# Search by RID
result = await agent.call_tool("search_by_rid", {
    "rid_query": "654789"
})

# Search by DOCID
result = await agent.call_tool("search_by_docid", {
    "docid_query": "98979-9999"
})

# Multi-field search with filters
result = await agent.call_tool("search_events", {
    "query": "climate change",
    "filter_by_year": "2023",
    "filter_by_country": "India"
})
```

---

## Best Practices for Agents

### Tool Selection

**Use search_by_rid when**:
- You have a RID (full or partial)
- Need to find events by resource identifier
- Looking for DOCID aggregation by RID

**Use search_by_docid when**:
- You have a DOCID (full or partial)
- Need to track documents
- Looking for RID aggregation by DOCID

**Use search_events when**:
- Searching by event content (title, theme)
- Using natural language queries
- Need to filter by year or country
- Query might have typos

### Query Tips

**For RID/DOCID searches**:
- Full IDs return exact matches (very_high confidence)
- Partial IDs (5-7 chars) return prefix matches (high confidence)
- Short queries (3-4 chars) return fuzzy matches (medium/low confidence)

**For multi-field search**:
- Don't worry about typos - spell tolerance handles them
- Use filters to narrow results
- More specific queries return better results

---

## Logging

The server logs:
- Server startup info (host, port, OpenSearch URL)
- Configuration parameters
- Search errors and failures
- HTTP request errors

View logs in console when running the server.

---

## Production Deployment

### Using Docker (Optional)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV OPENSEARCH_URL=http://opensearch:9200
ENV INDEX_NAME=events
ENV HOST=0.0.0.0
ENV PORT=8002

CMD ["python", "server.py"]
```

```bash
# Build
docker build -t mcp-events-search .

# Run
docker run -p 8002:8002 \
  -e OPENSEARCH_URL=http://opensearch:9200 \
  mcp-events-search
```

---

## Troubleshooting

### Server won't start
- Check OpenSearch is running at OPENSEARCH_URL
- Verify port 8002 is available
- Check Python version (3.8+)

### No results returned
- Verify index exists: `curl http://localhost:9200/events/_count`
- Check query length (min 3 for RID, min 4 for DOCID)
- Review OpenSearch logs

### Low quality results
- Adjust score thresholds via environment variables
- Check index mapping has required fields (.keyword, .prefix)
- Review cascading strategy parameters

---

## Related Documentation

- **Main Implementation**: `../events/events_search.py`
- **API Documentation**: `../events/README.md`
- **Index Mapping**: `../events/events_mapping.json`

---

## License

Part of the HimSearch project.
