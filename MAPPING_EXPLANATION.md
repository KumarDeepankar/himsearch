# Events Index Mapping - Detailed Explanation

This document provides a comprehensive explanation of the `events` OpenSearch index mapping and the search features it enables.

## Table of Contents
1. [Index Settings](#index-settings)
2. [Analyzers Configuration](#analyzers-configuration)
3. [Field Mappings](#field-mappings)
4. [Enabled Search Features](#enabled-search-features)
5. [Query Examples](#query-examples)

---

## Index Settings

```json
{
  "settings": {
    "index": {
      "number_of_shards": 1,
      "number_of_replicas": 1,
      "max_ngram_diff": 10
    }
  }
}
```

### Explanation

| Setting | Value | Purpose |
|---------|-------|---------|
| `number_of_shards` | 1 | Single shard for small dataset (101 documents). More shards would be unnecessary overhead. |
| `number_of_replicas` | 1 | One replica for high availability. Data is duplicated on another node. |
| `max_ngram_diff` | 10 | Maximum difference between `min_gram` and `max_gram`. Allows edge_ngram (2-10) to work. |

---

## Analyzers Configuration

The index uses **3 custom analyzers** to enable different search capabilities:

### 1. Standard Search Analyzer

```json
"standard_search": {
  "type": "standard",
  "stopwords": "_english_"
}
```

**What it does:**
- Uses OpenSearch's built-in standard tokenizer
- Removes English stopwords (the, is, at, which, etc.)
- Lowercases all text
- Splits on whitespace and punctuation

**Example:**
```
Input:  "The Renewable Energy Summit 2023"
Output: ["renewable", "energy", "summit", "2023"]
        (note: "the" is removed as stopword)
```

**Used for:** Primary text search on main content fields

---

### 2. Ngram Analyzer

```json
"ngram_analyzer": {
  "type": "custom",
  "tokenizer": "standard",
  "filter": [
    "lowercase",
    "asciifolding",
    "ngram_filter"
  ]
}
```

**Filter definitions:**
```json
"ngram_filter": {
  "type": "ngram",
  "min_gram": 3,
  "max_gram": 4
}
```

**What it does:**
1. Standard tokenizer splits text into words
2. Lowercase filter converts to lowercase
3. ASCII folding removes accents (café → cafe)
4. Ngram filter creates overlapping 3-4 character chunks

**Example:**
```
Input:  "renewable"
After tokenization: ["renewable"]
After lowercase: ["renewable"]
After ngram (3-4 chars):
  3-grams: ["ren", "ene", "new", "ewa", "wab", "abl", "ble"]
  4-grams: ["rene", "enew", "newa", "ewab", "wabl", "able"]
```

**Why this enables fuzzy search:**
```
Query:    "renewabel" (misspelled)
Ngrams:   ["ren", "ene", "new", "ewa", "wab", "abe", "bel"]

Indexed:  "renewable"
Ngrams:   ["ren", "ene", "new", "ewa", "wab", "abl", "ble"]

Overlap:  5 out of 7 ngrams match!
Result:   Document is returned with decent relevance score
```

**Used for:** Spelling mistake tolerance and fuzzy matching

---

### 3. Edge Ngram Analyzer

```json
"edge_ngram_analyzer": {
  "type": "custom",
  "tokenizer": "standard",
  "filter": [
    "lowercase",
    "asciifolding",
    "edge_ngram_filter"
  ]
}
```

**Filter definition:**
```json
"edge_ngram_filter": {
  "type": "edge_ngram",
  "min_gram": 2,
  "max_gram": 10
}
```

**What it does:**
- Like ngram, but only from the **beginning** of each word
- Creates progressively longer prefixes
- Perfect for autocomplete/search-as-you-type

**Example:**
```
Input:  "technology"
After tokenization: ["technology"]
After edge_ngram:
  ["te", "tec", "tech", "techn", "techno", "technol", "technolo", "technolog", "technology"]
```

**Why this enables autocomplete:**
```
User types: "tech"
Matches:    All words starting with "tech"
            - "technology"
            - "technical"
            - "techniques"
```

**Used for:** Autocomplete and prefix matching

---

## Field Mappings

### Overview Table

| Field | Type | Indexed? | Searchable? | Filterable? | Aggregatable? | Purpose |
|-------|------|----------|-------------|-------------|---------------|---------|
| `rid` | keyword | ❌ No | ❌ No | ❌ No | ❌ No | Storage only (record ID) |
| `docid` | keyword | ❌ No | ❌ No | ❌ No | ❌ No | Storage only (document ID) |
| `url` | keyword | ❌ No | ❌ No | ❌ No | ❌ No | Storage only (URL) |
| `country` | keyword | ✅ Yes | ✅ Yes (exact) | ✅ Yes | ✅ Yes | Filtering and aggregation |
| `year` | integer | ✅ Yes | ✅ Yes (exact) | ✅ Yes | ✅ Yes | Filtering and aggregation |
| `event_count` | integer | ✅ Yes | ✅ Yes (exact) | ✅ Yes | ✅ Yes | Numerical analysis |
| `event_title` | text | ✅ Yes | ✅ Yes (fuzzy) | ❌ No | ⚠️ .keyword only | Primary search field |
| `event_theme` | text | ✅ Yes | ✅ Yes (fuzzy) | ❌ No | ⚠️ .keyword only | Theme-based search |
| `event_highlight` | text | ✅ Yes | ✅ Yes (fuzzy) | ❌ No | ❌ No | Event highlights search |
| `event_summary` | text | ✅ Yes | ✅ Yes (fuzzy) | ❌ No | ❌ No | Summary search |
| `event_object` | text | ✅ Yes | ✅ Yes (fuzzy) | ❌ No | ❌ No | Objective search |
| `commentary_summary` | text | ❌ No | ❌ No | ❌ No | ❌ No | Storage only |
| `next_event_plan` | text | ❌ No | ❌ No | ❌ No | ❌ No | Storage only |
| `event_conclusion` | text | ❌ No | ❌ No | ❌ No | ❌ No | Storage only |
| `event_conclusion_overall` | text | ❌ No | ❌ No | ❌ No | ❌ No | Storage only |
| `next_event_suggestion` | text | ❌ No | ❌ No | ❌ No | ❌ No | Storage only |

---

### Detailed Field Configurations

#### 1. Storage-Only Fields (Not Indexed)

```json
"rid": {
  "type": "keyword",
  "index": false
}
```

**Fields:** `rid`, `docid`, `url`, `commentary_summary`, `next_event_plan`, `event_conclusion`, `event_conclusion_overall`, `next_event_suggestion`

**Configuration:**
- `"index": false` - Field is stored but not indexed
- Cannot be searched, filtered, or aggregated
- Only returned in search results
- Saves index space and memory

**Why these fields are not indexed:**
- **IDs and URLs**: Not meant for searching
- **Summary fields**: Contain overlapping information with indexed fields
- **Avoids duplicate matches**: Prevents same content matching multiple times

---

#### 2. Filterable/Aggregatable Fields

##### Country Field

```json
"country": {
  "type": "keyword"
}
```

**Type:** `keyword` (exact value, not analyzed)

**Capabilities:**
- ✅ Exact match filtering
- ✅ Aggregations (group by country)
- ✅ Sorting
- ✅ Doc values enabled by default

**Use cases:**
```python
# Filter by country
{"query": {"term": {"country": "Denmark"}}}

# Aggregate by country
{"aggs": {"by_country": {"terms": {"field": "country"}}}}
```

##### Year Field

```json
"year": {
  "type": "integer"
}
```

**Type:** `integer` (numeric value)

**Capabilities:**
- ✅ Exact match filtering
- ✅ Range queries (gte, lte, gt, lt)
- ✅ Aggregations (histogram, stats)
- ✅ Numerical sorting
- ✅ Doc values enabled by default

**Use cases:**
```python
# Range filter
{"query": {"range": {"year": {"gte": 2021, "lte": 2023}}}}

# Aggregate by year
{"aggs": {"by_year": {"terms": {"field": "year"}}}}

# Statistics
{"aggs": {"year_stats": {"stats": {"field": "year"}}}}
```

##### Event Count Field

```json
"event_count": {
  "type": "integer"
}
```

**Same as year field** - supports all numeric operations

**Use cases:**
```python
# Find large events
{"query": {"range": {"event_count": {"gte": 10000}}}}

# Average attendance
{"aggs": {"avg_attendance": {"avg": {"field": "event_count"}}}}
```

---

#### 3. Searchable Text Fields

##### Event Title (Primary Search Field)

```json
"event_title": {
  "type": "text",
  "analyzer": "standard_search",
  "fields": {
    "keyword": {
      "type": "keyword"
    },
    "ngram": {
      "type": "text",
      "analyzer": "ngram_analyzer"
    },
    "edge_ngram": {
      "type": "text",
      "analyzer": "edge_ngram_analyzer"
    }
  }
}
```

**Multi-field configuration enables:**

1. **`event_title` (main field)**
   - Analyzer: `standard_search`
   - Use: Primary text search
   - Stopwords removed
   - Example query: `{"match": {"event_title": "renewable energy"}}`

2. **`event_title.keyword`**
   - Type: `keyword` (exact value)
   - Use: Aggregations, exact matching, sorting
   - Example: `{"terms": {"field": "event_title.keyword"}}`

3. **`event_title.ngram`**
   - Analyzer: `ngram_analyzer` (3-4 character chunks)
   - Use: Fuzzy search, spelling mistakes
   - Example: `{"match": {"event_title.ngram": "technolgy"}}`

4. **`event_title.edge_ngram`**
   - Analyzer: `edge_ngram_analyzer` (prefix matching)
   - Use: Autocomplete, search-as-you-type
   - Example: `{"match": {"event_title.edge_ngram": "tech"}}`

**Boosting:**
- `event_title` has highest boost (3.0) in multi_match queries
- Matches in title score higher than matches in other fields

##### Event Theme

```json
"event_theme": {
  "type": "text",
  "analyzer": "standard_search",
  "fields": {
    "keyword": {
      "type": "keyword"
    },
    "ngram": {
      "type": "text",
      "analyzer": "ngram_analyzer"
    }
  }
}
```

**Multi-field configuration:**
1. **`event_theme`** - Standard text search
2. **`event_theme.keyword`** - Aggregations (group by theme)
3. **`event_theme.ngram`** - Fuzzy theme search

**Note:** No edge_ngram (autocomplete not needed for themes)

##### Event Highlight, Summary, Object

```json
"event_highlight": {
  "type": "text",
  "analyzer": "standard_search",
  "fields": {
    "ngram": {
      "type": "text",
      "analyzer": "ngram_analyzer"
    }
  }
}
```

**Configuration:**
- Standard text search
- Ngram for fuzzy matching
- No keyword subfield (not used for aggregations)
- Lower boost in multi_match queries

---

## Enabled Search Features

### 1. ✅ Full-Text Search

**Enabled by:** Text fields with `standard_search` analyzer

**How it works:**
```python
{
  "query": {
    "match": {
      "event_title": "renewable energy"
    }
  }
}
```

**Features:**
- Tokenization (splits into words)
- Stopword removal
- Lowercase normalization
- Relevance scoring (TF-IDF/BM25)

---

### 2. ✅ Multi-Field Search

**Enabled by:** Multiple text fields with different boost values

**How it works:**
```python
{
  "query": {
    "multi_match": {
      "query": "climate summit",
      "fields": [
        "event_title^3",      # Boost 3x
        "event_theme^2.5",    # Boost 2.5x
        "event_summary^1.5"   # Boost 1.5x
      ]
    }
  }
}
```

**Features:**
- Searches across multiple fields simultaneously
- Weighted scoring (matches in title score higher)
- Returns best overall matches

---

### 3. ✅ Fuzzy Search (Spelling Mistakes)

**Enabled by:** Fuzziness parameter + ngram analyzer

**Method 1: Fuzziness Parameter**
```python
{
  "query": {
    "match": {
      "event_title": {
        "query": "renewabel enrgy",  # Misspelled
        "fuzziness": "AUTO"
      }
    }
  }
}
```

**AUTO fuzziness rules:**
- 1-2 chars: 0 edits allowed
- 3-5 chars: 1 edit allowed (renewabel → renewable)
- 6+ chars: 2 edits allowed

**Method 2: Ngram Matching**
```python
{
  "query": {
    "match": {
      "event_title.ngram": "technolgy"  # Misspelled
    }
  }
}
```

**Ngram overlap:**
```
"technolgy": ["tec", "ech", "chn", "hno", "nol", "olg", "lgy"]
"technology": ["tec", "ech", "chn", "hno", "nol", "olo", "log", "ogy"]
Overlap: 5/7 = 71% match
```

---

### 4. ✅ Hybrid Search

**Enabled by:** Combining standard and ngram analyzers

**How it works:**
```python
{
  "query": {
    "bool": {
      "should": [
        {
          "multi_match": {
            "query": "tech summit",
            "fields": ["event_title^3", "event_theme^2.5"],
            "fuzziness": "AUTO"
          }
        },
        {
          "multi_match": {
            "query": "tech summit",
            "fields": ["event_title.ngram", "event_theme.ngram"]
          }
        }
      ]
    }
  }
}
```

**Benefits:**
- Standard analyzer: Good for exact word matches
- Ngram analyzer: Good for fuzzy/partial matches
- Combined: Best of both worlds
- Higher scores for documents matching both ways

---

### 5. ✅ Autocomplete / Search-as-You-Type

**Enabled by:** Edge ngram analyzer on `.edge_ngram` subfields

**How it works:**
```python
{
  "query": {
    "match": {
      "event_title.edge_ngram": "tech"
    }
  }
}
```

**What gets matched:**
- "tech" matches "technology", "technical", "techniques"
- "renew" matches "renewable", "renewal"
- Works for any prefix length (2+ characters)

---

### 6. ✅ Exact Match Filtering

**Enabled by:** Keyword type fields (`country`) and integer fields (`year`, `event_count`)

**How it works:**
```python
# Exact country match
{
  "query": {
    "term": {
      "country": "Denmark"
    }
  }
}

# Exact year match
{
  "query": {
    "term": {
      "year": 2023
    }
  }
}
```

**Features:**
- Fast exact matching
- No scoring (filter context)
- Can be cached for performance

---

### 7. ✅ Range Queries

**Enabled by:** Integer type fields (`year`, `event_count`)

**How it works:**
```python
# Year range
{
  "query": {
    "range": {
      "year": {
        "gte": 2021,  # Greater than or equal
        "lte": 2023   # Less than or equal
      }
    }
  }
}

# Attendance range
{
  "query": {
    "range": {
      "event_count": {
        "gt": 5000,   # Greater than
        "lt": 15000   # Less than
      }
    }
  }
}
```

---

### 8. ✅ Boolean Queries (Combining Multiple Conditions)

**Enabled by:** All indexed fields

**How it works:**
```python
{
  "query": {
    "bool": {
      "must": [
        # Must match (contributes to score)
        {"match": {"event_title": "summit"}}
      ],
      "filter": [
        # Must match (doesn't affect score)
        {"term": {"country": "Denmark"}},
        {"range": {"year": {"gte": 2022}}}
      ],
      "should": [
        # Optional (boosts score if matched)
        {"match": {"event_theme": "technology"}}
      ],
      "must_not": [
        # Must not match
        {"match": {"event_summary": "cancelled"}}
      ]
    }
  }
}
```

**Clauses:**
- `must`: AND condition, affects relevance score
- `filter`: AND condition, no scoring (faster)
- `should`: OR condition, boosts score
- `must_not`: NOT condition, excludes documents

---

### 9. ✅ Aggregations (Year-wise, Country-wise Analysis)

**Enabled by:** `year` (integer), `country` (keyword), `.keyword` subfields

**Terms Aggregation (Group By):**
```python
{
  "size": 0,  # Don't return documents
  "aggs": {
    "events_by_year": {
      "terms": {
        "field": "year",
        "size": 10
      }
    }
  }
}

# Result: Count of events per year
{
  "aggregations": {
    "events_by_year": {
      "buckets": [
        {"key": 2021, "doc_count": 34},
        {"key": 2022, "doc_count": 34},
        {"key": 2023, "doc_count": 33}
      ]
    }
  }
}
```

**Stats Aggregation (Numerical Analysis):**
```python
{
  "aggs": {
    "attendance_stats": {
      "stats": {
        "field": "event_count"
      }
    }
  }
}

# Result: min, max, avg, sum, count
```

**Nested Aggregations (Sub-aggregations):**
```python
{
  "aggs": {
    "by_year": {
      "terms": {"field": "year"},
      "aggs": {
        "avg_attendance": {
          "avg": {"field": "event_count"}
        }
      }
    }
  }
}

# Result: Average attendance per year
```

---

### 10. ✅ Sorting

**Enabled by:** All indexed fields (except text without .keyword)

**How it works:**
```python
{
  "query": {...},
  "sort": [
    {"year": "desc"},              # Sort by year (newest first)
    {"event_count": "desc"},       # Then by attendance
    {"event_title.keyword": "asc"} # Then alphabetically
  ]
}
```

---

### 11. ✅ Highlighting

**Enabled by:** All text fields

**How it works:**
```python
{
  "query": {"match": {"event_summary": "renewable energy"}},
  "highlight": {
    "fields": {
      "event_summary": {}
    }
  }
}

# Result includes:
{
  "highlight": {
    "event_summary": [
      "The summit focused on <em>renewable</em> <em>energy</em> solutions..."
    ]
  }
}
```

---

### 12. ✅ Phrase Matching

**Enabled by:** Text fields with position information

**How it works:**
```python
# Match exact phrase
{
  "query": {
    "match_phrase": {
      "event_title": "climate change summit"
    }
  }
}

# Match phrase with slop (words can be up to 2 positions apart)
{
  "query": {
    "match_phrase": {
      "event_title": {
        "query": "climate summit",
        "slop": 2
      }
    }
  }
}
```

---

## Query Examples

### Example 1: Basic Search with Spelling Mistakes

```python
{
  "query": {
    "multi_match": {
      "query": "renewabel enrgy conferance",  # Multiple typos
      "fields": [
        "event_title^3",
        "event_theme^2.5",
        "event_summary^1.5"
      ],
      "fuzziness": "AUTO",
      "operator": "or"
    }
  },
  "size": 5
}
```

**What happens:**
1. "renewabel" → matched to "renewable" (1 edit distance)
2. "enrgy" → matched to "energy" (1 edit distance)
3. "conferance" → matched to "conference" (1 edit distance)
4. Searches across title, theme, and summary
5. Title matches score highest (boost 3x)

---

### Example 2: Filtered Search with Aggregation

```python
{
  "query": {
    "bool": {
      "must": {
        "multi_match": {
          "query": "technology innovation",
          "fields": ["event_title^3", "event_theme^2.5"]
        }
      },
      "filter": [
        {"term": {"country": "Denmark"}},
        {"range": {"year": {"gte": 2022}}}
      ]
    }
  },
  "aggs": {
    "by_year": {
      "terms": {"field": "year"},
      "aggs": {
        "avg_attendance": {
          "avg": {"field": "event_count"}
        }
      }
    }
  },
  "size": 10
}
```

**What happens:**
1. Searches for "technology innovation" in title and theme
2. Filters to only Denmark events
3. Filters to years 2022 and later
4. Returns top 10 matching documents
5. Also returns aggregation: event count and average attendance per year

---

### Example 3: Hybrid Search (Standard + Ngram)

```python
{
  "query": {
    "bool": {
      "should": [
        {
          "multi_match": {
            "query": "climat chang",  # Misspelled
            "fields": ["event_title^3", "event_theme^2.5"],
            "type": "best_fields",
            "fuzziness": "AUTO"
          }
        },
        {
          "multi_match": {
            "query": "climat chang",
            "fields": ["event_title.ngram", "event_theme.ngram"],
            "type": "best_fields"
          }
        }
      ],
      "minimum_should_match": 1
    }
  },
  "size": 5
}
```

**What happens:**
1. First query: Standard analyzer with fuzziness
2. Second query: Ngram analyzer (more fuzzy-tolerant)
3. Documents matching both score highest
4. Even severe misspellings get matched via ngram overlap

---

### Example 4: Autocomplete Query

```python
{
  "query": {
    "bool": {
      "should": [
        {
          "match": {
            "event_title.edge_ngram": {
              "query": "tech",
              "boost": 2
            }
          }
        },
        {
          "match": {
            "event_theme.edge_ngram": "tech"
          }
        }
      ]
    }
  },
  "size": 10
}
```

**What happens:**
1. Matches any title starting with "tech"
2. Matches any theme starting with "tech"
3. Title matches score 2x higher
4. Returns: "TechVision AI Summit", "Agricultural Technology Forum", etc.

---

### Example 5: Complex Year-wise Analysis

```python
{
  "size": 0,
  "aggs": {
    "by_year": {
      "terms": {
        "field": "year",
        "order": {"_key": "asc"}
      },
      "aggs": {
        "by_country": {
          "terms": {"field": "country"}
        },
        "total_attendance": {
          "sum": {"field": "event_count"}
        },
        "avg_attendance": {
          "avg": {"field": "event_count"}
        },
        "min_attendance": {
          "min": {"field": "event_count"}
        },
        "max_attendance": {
          "max": {"field": "event_count"}
        }
      }
    }
  }
}
```

**What happens:**
1. Groups all events by year
2. For each year, shows:
   - Country breakdown
   - Total attendance across all events
   - Average attendance per event
   - Smallest event
   - Largest event
3. Perfect for year-over-year analysis

---

## Summary: Mapping → Features Matrix

| Mapping Feature | Enabled Search Capability |
|-----------------|---------------------------|
| `type: text` | Full-text search |
| `analyzer: standard_search` | Tokenization, stopwords, normalization |
| `analyzer: ngram_analyzer` | Spelling mistake tolerance, fuzzy matching |
| `analyzer: edge_ngram_analyzer` | Autocomplete, prefix matching |
| `fields.keyword` | Exact matching, aggregations, sorting |
| `type: keyword` | Fast exact filtering, aggregations |
| `type: integer` | Range queries, numerical aggregations |
| `index: false` | Storage only (no search overhead) |
| Multi-field configuration | Multiple search strategies per field |
| Field boosting (^3, ^2.5) | Relevance tuning |

---

## Best Practices

### When to Use Each Search Type

1. **Standard Search**: General queries, when spelling is correct
2. **Fuzzy Search**: User-entered queries, likely to have typos
3. **Hybrid Search**: When you want both precision and recall
4. **Ngram Search**: Very fuzzy queries, partial word matches
5. **Edge Ngram**: Autocomplete, search-as-you-type
6. **Term Query**: Exact matches on keyword/integer fields
7. **Range Query**: Date ranges, numerical ranges
8. **Bool Query**: Complex conditions (AND/OR/NOT)

### Performance Tips

1. Use `filter` context (not `must`) for exact matches - no scoring overhead
2. Limit aggregation size to prevent memory issues
3. Use `_source: false` if you only need IDs
4. Use pagination with `from` and `size`
5. Consider using `search_after` for deep pagination

---

## Conclusion

The events index mapping is designed to provide:
- **Flexibility**: Multiple search strategies for different use cases
- **Robustness**: Handles spelling mistakes and partial matches
- **Performance**: Selective indexing reduces overhead
- **Analytics**: Year-wise and country-wise aggregations
- **Relevance**: Boost important fields for better results

The combination of standard, ngram, and edge ngram analyzers creates a hybrid search system that handles both precise and fuzzy queries effectively, while selective field indexing prevents information overlap and improves search relevance.
