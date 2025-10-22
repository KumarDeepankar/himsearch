# OpenSearch Events Index - Search Methods

Production-ready search implementation with optimized cascading strategy for high-precision top 3 results.

---

## Overview

The `EventsSearch` class provides three specialized search methods:

1. **fetch_information_by_rid** - RID-specific search with cascading strategy
2. **fetch_information_by_docid** - DOCID-specific search with cascading strategy
3. **search_events** - Multi-field search across all fields with optional filters

**Performance**: 70% accuracy with excellent precision (1-3 results per query on average)

---

## Installation

```bash
pip install requests
```

---

## Quick Start

```python
from events_search import EventsSearch

# Initialize search client
search = EventsSearch(
    opensearch_url="http://localhost:9200",
    index_name="events"
)

# Method 1: Search by RID
result = search.fetch_information_by_rid("65478902")

# Method 2: Search by DOCID
result = search.fetch_information_by_docid("98979-99999-abc-0-a-1")

# Method 3: Multi-field search
result = search.search_events("climate summit", filter_by_year="2023")
```

---

## Cascading Search Strategy

Both RID and DOCID searches use an optimized cascading strategy for maximum precision:

### 1. Exact Match (First Priority)
- Uses `.keyword` field for exact matching
- **Confidence**: very_high
- **When**: Query matches complete RID/DOCID exactly
- Returns immediately if match found

### 2. Prefix Match (Second Priority)
- Uses `.prefix` field with edge_ngram analyzer
- **Confidence**: high/medium
- **Threshold**: Score >= 1.0 (MIN_PREFIX_SCORE)
- **Max Results**: 8 (MAX_PREFIX_RESULTS)
- Falls back to fuzzy if no high-quality matches

### 3. Fuzzy Match (Final Fallback)
- Uses base field with n-gram tokenizer
- **Confidence**: medium/low
- **Threshold**: Score >= 2.5 (RID) or >= 3.5 (DOCID)
- Returns best 3 results

### Optimized Parameters

```python
MIN_SCORE_RID = 2.5          # Filters low-quality RID matches
MIN_SCORE_DOCID = 3.5        # Filters low-quality DOCID matches
MIN_PREFIX_SCORE = 1.0       # Minimum score for prefix matches
MAX_PREFIX_RESULTS = 8       # Maximum prefix results before fallback
```

These parameters are optimized for **high precision on top 3 results**.

---

## Method 1: fetch_information_by_rid

Search for events by RID using cascading strategy.

### Signature

```python
fetch_information_by_rid(rid_query: str) -> Dict
```

### Parameters

- **rid_query** (str): RID to search for (minimum 3 characters)

### Returns

```python
{
    "query": "654789",
    "field": "rid",
    "match_type": "prefix",          # exact | prefix | fuzzy
    "confidence": "high",            # very_high | high | medium | low
    "total_count": 4,                # Total matching records found
    "docid_aggregation": [           # Aggregation grouped by DOCID
        {
            "docid": "98979-99999-abc-0-a-1",
            "count": 2
        },
        {
            "docid": "98980-100006-xyz-1-b-2",
            "count": 1
        },
        {
            "docid": "98981-100013-jkl-2-c-3",
            "count": 1
        }
    ],
    "top_3_matches": [               # Top 3 highest-scoring results
        {
            "score": 2.856,
            "rid": "65478902",
            "docid": "98979-99999-abc-0-a-1",
            "event_title": "TechVision AI Summit 2023",
            "event_theme": "Artificial Intelligence and Future Technologies",
            "event_highlight": "Unveiling of breakthrough natural language processing model",
            "event_summary": "Annual technology conference showcasing latest innovations in AI",
            "country": "Denmark",
            "year": 2021,
            "event_count": 5000,
            "url": "https://techvisionai.summit.com"
            # ... all other event fields included
        },
        {
            "score": 2.803,
            "rid": "65478903",
            "docid": "98979-99999-abc-0-a-1",
            "event_title": "Global Innovation Forum 2023",
            "event_theme": "Digital Transformation and Sustainability",
            "event_highlight": "Launch of green technology initiative",
            "event_summary": "International forum bringing together leaders in innovation",
            "country": "Sweden",
            "year": 2022,
            "event_count": 3500,
            "url": "https://globalinnovation.forum.com"
            # ... all other event fields included
        },
        {
            "score": 2.745,
            "rid": "65478904",
            "docid": "98980-100006-xyz-1-b-2",
            "event_title": "Smart Cities Conference 2023",
            "event_theme": "Urban Technology and Infrastructure",
            "event_highlight": "IoT solutions for sustainable city planning",
            "event_summary": "Conference focused on technology-driven urban development",
            "country": "Norway",
            "year": 2023,
            "event_count": 2800,
            "url": "https://smartcities.conference.com"
            # ... all other event fields included
        }
    ]
}
```

**Note**: Even though `total_count` is 4, only the **top 3 highest-scoring matches** are returned in `top_3_matches`.

### Examples

```python
# Full RID (8 chars) → Exact match
result = search.fetch_information_by_rid("65478902")
# Returns: match_type="exact", confidence="very_high", ~1 result

# Partial RID (6 chars) → Prefix match
result = search.fetch_information_by_rid("654789")
# Returns: match_type="prefix", confidence="high", ~3 results

# Short RID (3-4 chars) → Fuzzy match
result = search.fetch_information_by_rid("654")
# Returns: match_type="fuzzy", confidence="medium", ~3 results
```

---

## Method 2: fetch_information_by_docid

Search for events by DOCID using cascading strategy.

### Signature

```python
fetch_information_by_docid(docid_query: str) -> Dict
```

### Parameters

- **docid_query** (str): DOCID to search for (minimum 4 characters)

### Returns

```python
{
    "query": "98979",
    "field": "docid",
    "match_type": "prefix",          # exact | prefix | fuzzy
    "confidence": "high",            # very_high | high | medium | low
    "total_count": 4,                # Total matching records found
    "rid_aggregation": [             # Aggregation grouped by RID
        {
            "rid": "65478902",
            "count": 2
        },
        {
            "rid": "65478905",
            "count": 1
        },
        {
            "rid": "65478908",
            "count": 1
        }
    ],
    "top_3_matches": [               # Top 3 highest-scoring results
        {
            "score": 4.521,
            "rid": "65478902",
            "docid": "98979-99999-abc-0-a-1",
            "event_title": "TechVision AI Summit 2023",
            "event_theme": "Artificial Intelligence and Future Technologies",
            "event_highlight": "Unveiling of breakthrough natural language processing model",
            "event_summary": "Annual technology conference showcasing latest innovations in AI",
            "country": "Denmark",
            "year": 2021,
            "event_count": 5000,
            "url": "https://techvisionai.summit.com"
            # ... all other event fields included
        },
        {
            "score": 4.456,
            "rid": "65478902",
            "docid": "98979-99998-def-0-b-2",
            "event_title": "AI Ethics Workshop 2023",
            "event_theme": "Responsible AI Development",
            "event_highlight": "Framework for ethical AI implementation",
            "event_summary": "Workshop on ethical considerations in AI development",
            "country": "Denmark",
            "year": 2022,
            "event_count": 1200,
            "url": "https://aiethics.workshop.com"
            # ... all other event fields included
        },
        {
            "score": 4.389,
            "rid": "65478905",
            "docid": "98979-99997-ghi-0-c-3",
            "event_title": "Machine Learning Symposium 2023",
            "event_theme": "Advanced ML Algorithms",
            "event_highlight": "Deep learning breakthrough in computer vision",
            "event_summary": "Symposium showcasing latest ML research",
            "country": "Finland",
            "year": 2023,
            "event_count": 2100,
            "url": "https://mlsymposium.conference.com"
            # ... all other event fields included
        }
    ]
}
```

**Note**: Even though `total_count` is 4, only the **top 3 highest-scoring matches** are returned in `top_3_matches`.

### Examples

```python
# Full DOCID (20+ chars) → Exact match
result = search.fetch_information_by_docid("98979-99999-abc-0-a-1")
# Returns: match_type="exact", confidence="very_high", 1 result

# Partial DOCID (10 chars) → Prefix match
result = search.fetch_information_by_docid("98979-9999")
# Returns: match_type="prefix", confidence="high", ~1 result

# Short DOCID (4-5 chars) → Fuzzy match
result = search.fetch_information_by_docid("9897")
# Returns: match_type="fuzzy", confidence="medium", ~3 results
```

---

## Method 3: search_events

Multi-field search across all fields with optional year/country filters and **automatic spell tolerance**.

### Signature

```python
search_events(
    search_query: str,
    filter_by_year: Optional[str] = None,
    filter_by_country: Optional[str] = None
) -> Dict
```

### Parameters

- **search_query** (str): Search term to query across all fields
- **filter_by_year** (str, optional): Year filter (e.g., "2023")
- **filter_by_country** (str, optional): Country filter (e.g., "India")

### Spell Tolerance ✨

The search automatically handles common typos and misspellings using fuzzy matching:

- ✅ **1-2 character edits**: "climete" → finds "climate"
- ✅ **Missing letters**: "conferece" → finds "conference"
- ✅ **Extra letters**: "climmate" → finds "climate"
- ✅ **Wrong letters**: "conferense" → finds "conference"
- ✅ **Character swaps**: "sumit" → finds "summit"

**How it works**:
- `fuzziness: "AUTO"` - Automatically allows 1 edit for words 3-5 chars, 2 edits for 6+ chars
- `prefix_length: 1` - First character must match exactly (prevents false matches)
- `max_expansions: 50` - Limits performance impact

**Note**: Very long edit distances (3+ character differences) won't match.

### Searchable Fields with Boost Factors

| Field | Boost | Priority |
|-------|-------|----------|
| event_title | 3.0x | Highest |
| rid | 2.0x | High |
| docid | 2.0x | High |
| event_theme | 2.0x | High |
| event_highlight | 2.0x | High |
| rid.prefix | 1.5x | Medium |
| docid.prefix | 1.5x | Medium |
| country | 1.5x | Medium |
| year | 1.5x | Medium |

### Returns - No Filters

```python
{
    "query": "climate summit",
    "total_count": 4,
    "top_3_matches": [
        {
            "score": 15.234,
            "rid": "65478910",
            "docid": "98985-100041-abc-6-g-7",
            "event_title": "Global Climate Summit 2023",
            "event_theme": "Climate Action and Sustainability",
            "event_highlight": "Historic agreement on carbon reduction",
            "country": "Switzerland",
            "year": 2023
            # ... all other event fields
        },
        {
            "score": 14.567,
            "rid": "65478911",
            "docid": "98986-100048-vwx-7-h-8",
            "event_title": "UN Climate Conference",
            "event_theme": "Global Warming Solutions",
            "event_highlight": "New renewable energy initiatives",
            "country": "Germany",
            "year": 2022
            # ... all other event fields
        },
        {
            "score": 13.890,
            "rid": "65478912",
            "docid": "98987-100055-abc-8-i-9",
            "event_title": "Climate Leadership Summit",
            "event_theme": "Environmental Protection",
            "event_highlight": "Youth-led climate movement",
            "country": "France",
            "year": 2023
            # ... all other event fields
        }
    ]
}
```

**Note**: Total of 4 matches found, top 3 highest-scoring returned.

### Returns - With Year Filter

```python
{
    "query": "technology summit",
    "filtered_by_year": "2023",
    "total_count": 4,
    "count_by_year": [
        {"year": "2023", "count": 4},
        {"year": "2022", "count": 2},
        {"year": "2021", "count": 1}
    ],
    "top_3_matches": [
        {
            "score": 16.789,
            "rid": "65478902",
            "docid": "98985-100041-abc-6-g-7",
            "event_title": "TechVision AI Summit 2023",
            "year": 2023,
            "country": "Denmark"
            # ... all other event fields
        },
        {
            "score": 15.234,
            "rid": "65478905",
            "docid": "98986-100048-vwx-7-h-8",
            "event_title": "Global Technology Forum 2023",
            "year": 2023,
            "country": "Sweden"
            # ... all other event fields
        },
        {
            "score": 14.567,
            "rid": "65478908",
            "docid": "98987-100055-abc-8-i-9",
            "event_title": "Innovation Summit 2023",
            "year": 2023,
            "country": "Norway"
            # ... all other event fields
        }
    ]
}
```

**Note**: Total of 4 matches found for year 2023, top 3 highest-scoring returned.

### Returns - With Country Filter

```python
{
    "query": "conference",
    "filtered_by_country": "India",
    "total_count": 5,
    "count_by_country": [
        {"country": "India", "count": 5},
        {"country": "USA", "count": 3},
        {"country": "UK", "count": 2}
    ],
    "top_3_matches": [
        {
            "score": 12.456,
            "rid": "65478915",
            "docid": "98990-100075-pqr-11-l-12",
            "event_title": "International Tech Conference 2023",
            "country": "India",
            "year": 2023
            # ... all other event fields
        },
        {
            "score": 11.789,
            "rid": "65478916",
            "docid": "98991-100082-stu-12-m-13",
            "event_title": "AI Research Conference 2022",
            "country": "India",
            "year": 2022
            # ... all other event fields
        },
        {
            "score": 10.234,
            "rid": "65478917",
            "docid": "98992-100089-vwx-13-n-14",
            "event_title": "Data Science Conference 2023",
            "country": "India",
            "year": 2023
            # ... all other event fields
        }
    ]
}
```

**Note**: Total of 5 matches found for India, top 3 highest-scoring returned.

### Returns - With Both Filters

```python
{
    "query": "summit",
    "filtered_by_year": "2023",
    "filtered_by_country": "India",
    "total_count": 4,
    "filtered_count": {
        "year": "2023",
        "country": "India",
        "count": 4
    },
    "top_3_matches": [
        {
            "score": 14.123,
            "rid": "65478920",
            "docid": "98995-100110-abc-16-q-17",
            "event_title": "India Tech Summit 2023",
            "year": 2023,
            "country": "India"
            # ... all other event fields
        },
        {
            "score": 13.456,
            "rid": "65478921",
            "docid": "98996-100117-def-17-r-18",
            "event_title": "Digital India Summit 2023",
            "year": 2023,
            "country": "India"
            # ... all other event fields
        },
        {
            "score": 12.789,
            "rid": "65478922",
            "docid": "98997-100124-ghi-18-s-19",
            "event_title": "Innovation Summit India 2023",
            "year": 2023,
            "country": "India"
            # ... all other event fields
        }
    ]
}
```

**Note**: Total of 4 matches found for India in 2023, top 3 highest-scoring returned.

### Examples

```python
# Simple search
result = search.search_events("climate change")

# Search with typos (automatically corrected)
result = search.search_events("climete change")  # Finds "climate change"
result = search.search_events("conferense")      # Finds "conference"
result = search.search_events("tecnology sumit") # Finds "technology summit"

# With year filter
result = search.search_events("summit", filter_by_year="2023")

# With country filter (typos work with filters too)
result = search.search_events("conferece", filter_by_country="India")

# With both filters
result = search.search_events(
    "international meeting",
    filter_by_year="2023",
    filter_by_country="India"
)
```

---

## Configuration

### Custom OpenSearch URL

```python
search = EventsSearch(
    opensearch_url="https://my-cluster:9200",
    index_name="my_events_index"
)
```

### Adjust Score Thresholds (Advanced)

```python
search = EventsSearch()

# Adjust RID fuzzy score threshold (default: 2.5)
search.MIN_SCORE_RID = 3.0

# Adjust DOCID fuzzy score threshold (default: 3.5)
search.MIN_SCORE_DOCID = 4.0

# Adjust prefix score threshold (default: 1.0)
search.MIN_PREFIX_SCORE = 1.5

# Adjust max prefix results (default: 8)
search.MAX_PREFIX_RESULTS = 10
```

**Note**: Current parameters are optimized for high precision. Adjust carefully.

---

## Error Handling

All methods return error information if validation fails:

```python
# Query too short
result = search.fetch_information_by_rid("ab")

# Returns:
{
    "error": "Query too short",
    "message": "Please provide at least 3 characters (got 2)"
}
```

---

## Performance Characteristics

### Average Result Counts
- **Exact matches**: ~1 result
- **Prefix matches**: ~1-3 results
- **Fuzzy matches**: ~3 results
- **10-char specific queries**: ~1 result

### Response Format
- Fetches up to 100 results internally for accurate counting
- Returns only **top 3 matches** in response
- Includes **total_count** for all matches
- Includes **aggregations** by related field (docid or rid)

### Confidence Levels

| Match Type | Confidence | Typical Count |
|------------|------------|---------------|
| Exact | very_high | 1-2 results |
| Prefix (tight) | high | 1-5 results |
| Prefix (broad) | medium | 6-8 results |
| Fuzzy (focused) | medium | 3-5 results |
| Fuzzy (broad) | low | 6+ results |

---

## Testing

```bash
# Run comprehensive test suite
python precision_test.py

# Run example usage
python events_search.py
```

---

## Index Mapping Requirements

The implementation expects the following field mappings (see `events_mapping.json`):

- **rid**: text with ngram analyzer + keyword and prefix sub-fields
- **docid**: text with ngram analyzer + keyword and prefix sub-fields
- **event_title**: text with stemming and shingles
- **event_theme**: text with stemming and shingles
- **event_highlight**: text with stemming and shingles
- **year**: keyword (exact match, aggregatable)
- **country**: keyword (exact match, aggregatable)

---

## Implementation Details

### Why Cascading Strategy?

Cascading provides the best balance of:
- ✅ **High precision** on top 3 results
- ✅ **Simple logic** that's easy to debug
- ✅ **Tight result counts** (1-3 results average)
- ✅ **Clear confidence levels** based on match type

### Score Thresholds

The optimized score thresholds filter out low-quality matches:

- **MIN_SCORE_RID = 2.5**: Filters fuzzy RID matches with scores < 2.5
- **MIN_SCORE_DOCID = 3.5**: Filters fuzzy DOCID matches with scores < 3.5
- **MIN_PREFIX_SCORE = 1.0**: Balanced threshold for prefix matches

These were determined through comprehensive precision testing on 30 test cases.

### Aggregations

- **RID search** → Returns `docid_aggregation` (grouped by DOCID)
- **DOCID search** → Returns `rid_aggregation` (grouped by RID)
- Server-side aggregations for efficiency
- Size limited to 100 buckets

---

## Production Checklist

✅ Optimized parameters for high precision
✅ Comprehensive error handling
✅ Clear confidence indicators
✅ Efficient aggregations
✅ Tested with 30 test cases (70% accuracy, excellent precision)
✅ Simple, maintainable code

---

## License

This code is part of the HimSearch project.
