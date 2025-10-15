# Doc Values in OpenSearch/Elasticsearch - Complete Guide

This document provides a comprehensive explanation of `doc_values` - a critical data structure in OpenSearch and Elasticsearch that enables aggregations, sorting, and scripting.

## Table of Contents
1. [What are Doc Values?](#what-are-doc-values)
2. [How Doc Values Work](#how-doc-values-work)
3. [Storage Architecture](#storage-architecture)
4. [Field Types Support](#field-types-support)
5. [Doc Values vs Inverted Index](#doc-values-vs-inverted-index)
6. [Memory and Performance](#memory-and-performance)
7. [When to Disable Doc Values](#when-to-disable-doc-values)
8. [Real-World Examples](#real-world-examples)
9. [Best Practices](#best-practices)

---

## What are Doc Values?

**Doc values** are an on-disk columnar data structure that stores field values in a document-oriented way, optimized for operations that need to access the value of a field for a specific document.

### Simple Explanation

Think of doc values as a lookup table:
```
Document ID → Field Value

DOC001 → 2021
DOC002 → 2021
DOC003 → 2022
...
```

This structure makes it extremely fast to:
- Get all values for a field (for aggregation)
- Get value for specific document (for sorting)
- Iterate through values sequentially

---

## How Doc Values Work

### Indexing Phase

When you index a document, OpenSearch creates **two data structures** for most fields:

**1. Inverted Index (for searching)**
```
Term → Document IDs
2021 → [DOC001, DOC002, DOC004, ...]
2022 → [DOC050, DOC051, DOC052, ...]
2023 → [DOC080, DOC081, DOC082, ...]
```

**2. Doc Values (for aggregations/sorting)**
```
Document ID → Term
DOC001 → 2021
DOC002 → 2021
DOC003 → 2021
DOC004 → 2021
...
DOC050 → 2022
DOC051 → 2022
...
```

### Query Phase

**Without doc values (using inverted index):**
```
Task: "Get year value for DOC050"
Process:
1. Scan through all terms: 2021, 2022, 2023...
2. Check each term's document list
3. Find which term contains DOC050
4. Return that term value
Performance: SLOW ❌
```

**With doc values:**
```
Task: "Get year value for DOC050"
Process:
1. Direct lookup: DOC050 → 2022
Performance: FAST ✅
```

---

## Storage Architecture

### On-Disk Columnar Format

Doc values are stored in a columnar format on disk, optimized for sequential access:

```
Physical Storage (simplified):

/indices/events/_doc_values/year.dv:
╔════════════╦═══════╗
║ DOC_ID     ║ VALUE ║
╠════════════╬═══════╣
║ DOC001     ║ 2021  ║  ← 4 bytes
║ DOC002     ║ 2021  ║  ← 4 bytes
║ DOC003     ║ 2021  ║  ← 4 bytes
║ ...        ║ ...   ║
╚════════════╩═══════╝

/indices/events/_doc_values/country.dv:
╔════════════╦══════════╗
║ DOC_ID     ║ VALUE    ║
╠════════════╬══════════╣
║ DOC001     ║ Denmark  ║  ← ~8 bytes (ordinal + dictionary)
║ DOC002     ║ Dominica ║
║ DOC003     ║ Denmark  ║
║ ...        ║ ...      ║
╚════════════╩══════════╝
```

### Memory-Mapped Files

Doc values use **memory-mapped files**:
- Stored on disk, not in JVM heap
- OS manages caching automatically
- Hot data stays in OS page cache
- No OutOfMemory errors
- Automatically evicted when memory is needed

```
┌─────────────────────────────────────┐
│         JVM Heap Memory             │
│  (Inverted Index, Query Cache)      │
│         ~30% of RAM                 │
└─────────────────────────────────────┘
                 │
┌─────────────────────────────────────┐
│      OS Page Cache (RAM)            │
│  (Memory-Mapped Doc Values)         │
│         ~60% of RAM                 │
└─────────────────────────────────────┘
                 │
┌─────────────────────────────────────┐
│            Disk Storage             │
│  (Doc Values, Inverted Index,       │
│   Source Documents)                 │
└─────────────────────────────────────┘
```

---

## Field Types Support

### Automatic Doc Values (Enabled by Default)

These field types **automatically** have doc_values enabled:

| Field Type | Doc Values Default | Storage Per Value | Use Case |
|------------|-------------------|------------------|----------|
| `keyword` | ✅ Enabled | ~8-16 bytes | IDs, categories, tags |
| `integer` | ✅ Enabled | 4 bytes | Numbers, counts, years |
| `long` | ✅ Enabled | 8 bytes | Large numbers, timestamps |
| `short` | ✅ Enabled | 2 bytes | Small numbers |
| `byte` | ✅ Enabled | 1 byte | Very small numbers |
| `float` | ✅ Enabled | 4 bytes | Decimal numbers |
| `double` | ✅ Enabled | 8 bytes | High-precision decimals |
| `date` | ✅ Enabled | 8 bytes | Timestamps, dates |
| `boolean` | ✅ Enabled | 1 bit | True/false values |
| `ip` | ✅ Enabled | 16 bytes | IP addresses |
| `geo_point` | ✅ Enabled | 16 bytes | Latitude/longitude |

### No Doc Values (Cannot Be Enabled)

| Field Type | Doc Values | Reason |
|------------|-----------|---------|
| `text` | ❌ Disabled | Analyzed into multiple tokens, no single value per doc |
| `text.keyword` | ✅ Enabled | Multi-field with keyword type has doc_values |

---

## Doc Values vs Inverted Index

### Side-by-Side Comparison

| Aspect | Inverted Index | Doc Values |
|--------|---------------|------------|
| **Structure** | Term → Doc IDs | Doc ID → Value |
| **Storage** | Heap + Disk | Disk (memory-mapped) |
| **Best For** | Searching | Aggregations, Sorting |
| **Access Pattern** | "Which docs have value X?" | "What value does doc X have?" |
| **Memory Usage** | Moderate (heap) | Low (OS cache) |
| **Query Type** | `match`, `term`, `range` | `aggs`, `sort`, `scripts` |

### Example: Year Field

**Input Document:**
```json
{
  "docid": "DOC001",
  "year": 2021,
  "event_title": "TechVision Summit"
}
```

**What Gets Created:**

**Inverted Index for `year`:**
```
2021 → [DOC001, DOC002, DOC003, ...]
2022 → [DOC050, DOC051, DOC052, ...]
2023 → [DOC080, DOC081, DOC082, ...]
```
**Used for:** `{"query": {"term": {"year": 2021}}}`

**Doc Values for `year`:**
```
DOC001 → 2021
DOC002 → 2021
DOC003 → 2021
DOC004 → 2021
...
```
**Used for:** `{"aggs": {"by_year": {"terms": {"field": "year"}}}}`

---

## Memory and Performance

### Memory Usage Comparison

**Old Approach: Fielddata (Pre-Elasticsearch 2.0)**
```
Memory: JVM Heap (DANGEROUS)
Process: Build in-memory structures from inverted index
Risk: OutOfMemory errors with large datasets
Performance: Slow first query, then cached

Example with 1M documents, integer field:
- Fielddata size: ~4-8 MB in heap
- Risk: Can cause GC pauses
```

**Modern Approach: Doc Values (Current)**
```
Memory: OS Page Cache (SAFE)
Process: Direct memory-mapped file access
Risk: None - OS manages memory automatically
Performance: Consistently fast

Example with 1M documents, integer field:
- Doc values size: ~4 MB on disk
- Heap usage: 0 MB (uses OS cache)
- Risk: None
```

### Performance Benchmarks

**Aggregation Query Performance:**

```
Query: Aggregate 10M documents by year (3 unique values)

WITHOUT doc_values (using fielddata):
├─ First query: 15,000 ms (build fielddata)
├─ Heap usage: +80 MB
├─ Subsequent queries: 150 ms (cached)
└─ Risk: OutOfMemory on large datasets ⚠️

WITH doc_values:
├─ First query: 200 ms (sequential disk read)
├─ Heap usage: 0 MB
├─ Subsequent queries: 50 ms (OS cached)
└─ Risk: None ✅
```

**Sorting Performance:**

```
Query: Sort 1M documents by year

WITHOUT doc_values:
├─ Must build fielddata: 8,000 ms
└─ Heap usage: +50 MB

WITH doc_values:
├─ Direct access: 300 ms
└─ Heap usage: 0 MB
```

---

## When to Disable Doc Values

### Valid Reasons to Disable

**1. Save Disk Space**
```json
{
  "internal_code": {
    "type": "keyword",
    "index": true,
    "doc_values": false  // Only used for exact searches, never aggregated
  }
}
```
**Disk space saved:** ~30-40% for that field

**2. Write-Only Fields**
```json
{
  "audit_log": {
    "type": "keyword",
    "index": true,
    "doc_values": false  // Never aggregated or sorted, only searched
  }
}
```

**3. High Cardinality ID Fields**
```json
{
  "transaction_id": {
    "type": "keyword",
    "index": true,
    "doc_values": false  // UUID-like values, never useful for aggregation
  }
}
```

### Important Considerations

**❌ Do NOT disable if you:**
- Need aggregations on this field
- Need sorting on this field
- Use the field in scripts
- Might need these features in the future

**✅ Safe to disable if:**
- Field is ONLY used for exact match searching
- Field has very high cardinality with no aggregation value
- Disk space is critical and you've verified the field is never aggregated

### Enabling Fielddata (Not Recommended)

If you disabled doc_values but later need aggregations:

```json
{
  "year": {
    "type": "integer",
    "doc_values": false,
    "fielddata": true  // ⚠️ NOT RECOMMENDED - uses heap memory
  }
}
```

**Problems with fielddata:**
- Uses JVM heap (can cause OutOfMemory)
- Slow to build
- Can trigger circuit breakers
- Can cause GC pauses

---

## Real-World Examples

### Example 1: Events Index Analysis

**Mapping:**
```json
{
  "year": {
    "type": "integer"
    // doc_values: true (default)
  },
  "country": {
    "type": "keyword"
    // doc_values: true (default)
  },
  "event_count": {
    "type": "integer"
    // doc_values: true (default)
  }
}
```

**Query: Year-wise aggregation with country breakdown**
```python
query = {
    "size": 0,
    "aggs": {
        "by_year": {
            "terms": {"field": "year"},
            "aggs": {
                "by_country": {
                    "terms": {"field": "country"}
                },
                "avg_attendance": {
                    "avg": {"field": "event_count"}
                }
            }
        }
    }
}
```

**What Happens:**
1. OpenSearch scans doc_values for `year` field
2. Groups documents into buckets (2021, 2022, 2023)
3. For each bucket, scans doc_values for `country`
4. For each bucket, scans doc_values for `event_count` and calculates average
5. All operations use memory-mapped files, no heap usage

**Performance:**
- 101 documents: <10 ms
- 10,000 documents: ~50 ms
- 1,000,000 documents: ~500 ms
- Heap usage: 0 MB (all in OS cache)

---

### Example 2: Comparing Field Configurations

**Scenario: User ID field with 1M unique values**

**Option 1: Default (doc_values enabled)**
```json
{
  "user_id": {
    "type": "keyword"
    // doc_values: true (default)
  }
}
```
- Disk usage: ~12 MB
- Can aggregate: ✅ Yes
- Can sort: ✅ Yes
- Search speed: ⚡ Fast

**Option 2: Doc values disabled**
```json
{
  "user_id": {
    "type": "keyword",
    "doc_values": false
  }
}
```
- Disk usage: ~8 MB (33% savings)
- Can aggregate: ❌ No
- Can sort: ❌ No
- Search speed: ⚡ Fast

**Recommendation:** Keep doc_values enabled unless disk space is critical and you're 100% sure you'll never aggregate or sort by this field.

---

### Example 3: Index with index: false but doc_values

**Configuration:**
```json
{
  "rid": {
    "type": "keyword",
    "index": false,
    "doc_values": true  // This is the default even with index: false
  }
}
```

**What this means:**
- ✅ Can aggregate: `{"aggs": {"by_rid": {"terms": {"field": "rid"}}}}`
- ✅ Can sort: `{"sort": [{"rid": "asc"}]}`
- ❌ Cannot search: `{"query": {"term": {"rid": "REC001"}}}` ← FAILS
- ❌ Cannot filter: `{"query": {"bool": {"filter": [{"term": {"rid": "REC001"}}]}}}` ← FAILS

**Use case:** Internal IDs that you want to group by but never search on.

---

## Best Practices

### 1. Keep Doc Values Enabled by Default

```json
// ✅ GOOD - Default configuration
{
  "year": {
    "type": "integer"
  }
}

// ❌ BAD - Disabling without reason
{
  "year": {
    "type": "integer",
    "doc_values": false  // Why? You'll regret this later
  }
}
```

### 2. Use Appropriate Field Types

```json
// ✅ GOOD - Integer for numeric aggregations
{
  "year": {
    "type": "integer"  // Can do stats, histogram, etc.
  }
}

// ❌ BAD - Keyword for numbers
{
  "year": {
    "type": "keyword"  // Can only do terms agg, no stats
  }
}
```

### 3. Multi-field for Best of Both Worlds

```json
// ✅ EXCELLENT - Text for search, keyword for aggregation
{
  "event_title": {
    "type": "text",
    "fields": {
      "keyword": {
        "type": "keyword"
      }
    }
  }
}

// Usage:
// Search: {"match": {"event_title": "summit"}}
// Aggregate: {"terms": {"field": "event_title.keyword"}}
```

### 4. Monitor Disk Usage

```bash
# Check doc_values size
GET /events/_stats/store

# Response shows:
{
  "indices": {
    "events": {
      "total": {
        "store": {
          "size_in_bytes": 524288,
          "doc_values_size_in_bytes": 102400  # Doc values portion
        }
      }
    }
  }
}
```

### 5. Disable Only When Necessary

```json
// ✅ GOOD - Valid reason to disable
{
  "uuid": {
    "type": "keyword",
    "doc_values": false,  // High cardinality, never aggregated
    "index": true  // Only used for exact searches
  }
}

// ❌ BAD - Disabling useful field
{
  "country": {
    "type": "keyword",
    "doc_values": false  // Will regret when you want to aggregate!
  }
}
```

---

## Summary

### Key Takeaways

| Aspect | Value |
|--------|-------|
| **What is it?** | Columnar storage for field values, optimized for aggregations/sorting |
| **Where stored?** | Disk (memory-mapped files) |
| **Memory impact?** | Minimal (uses OS page cache, not JVM heap) |
| **Default for?** | keyword, integer, date, and all numeric types |
| **NOT available for?** | text fields (use .keyword subfield) |
| **When to disable?** | Only if field is NEVER aggregated/sorted AND disk space is critical |
| **Overhead?** | ~30-40% more disk per field |
| **Performance?** | Extremely fast for aggregations, no heap pressure |

### Decision Matrix

**Should I keep doc_values enabled?**

```
┌─────────────────────────────────────┬─────────┐
│ Question                            │ Answer  │
├─────────────────────────────────────┼─────────┤
│ Will I ever aggregate on this field?│ Yes     │ → KEEP ENABLED
│ Will I ever sort by this field?     │ Yes     │ → KEEP ENABLED
│ Will I use this field in scripts?   │ Yes     │ → KEEP ENABLED
│ Is disk space very limited?         │ Yes     │ → Consider disabling
│ Is field only for exact searches?   │ Yes     │ → Can disable
│ Might need aggregations later?      │ Maybe   │ → KEEP ENABLED (safe)
└─────────────────────────────────────┴─────────┘

Default answer: KEEP ENABLED ✅
```

---

## Additional Resources

- **Official Docs:** https://opensearch.org/docs/latest/field-types/supported-field-types/
- **Performance Tuning:** Monitor `_stats/fielddata` vs `_stats/doc_values`
- **Memory Configuration:** Allocate 50% RAM to OS cache for doc_values

---

**Bottom Line:** Doc values are a fundamental feature that enables aggregations, sorting, and scripting without heap memory pressure. Keep them enabled unless you have a specific, documented reason to disable them.
