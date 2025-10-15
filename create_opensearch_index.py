#!/usr/bin/env python3
"""
OpenSearch Index Creation Script for Events
Implements hybrid search with selective field indexing and spelling correction
"""

import json
import os
from opensearchpy import OpenSearch, helpers
from typing import List, Dict

# OpenSearch connection configuration
OPENSEARCH_HOST = 'localhost'
OPENSEARCH_PORT = 9200
INDEX_NAME = 'events'

# Initialize OpenSearch client
client = OpenSearch(
    hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
    http_auth=('admin', 'admin'),  # Update with your credentials
    use_ssl=False,
    verify_certs=False,
    ssl_show_warn=False
)


def create_index_mapping():
    """
    Create index mapping with hybrid search capabilities and selective field indexing.

    Strategy:
    1. Searchable fields (high priority, avoid overlap): event_title, event_theme, event_highlight
    2. Searchable fields (medium priority): event_summary, event_object
    3. Filterable only: country, year, event_count
    4. Stored only (not searchable): rid, docid, url, and other overlapping summary fields

    Features:
    - Custom analyzers for fuzzy matching and spelling correction
    - Hybrid search with both text and keyword fields
    - Year-wise aggregation support
    """

    mapping = {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 1,
                "max_ngram_diff": 10
            },
            "analysis": {
                "analyzer": {
                    # Standard analyzer with lowercase and stop words for general search
                    "standard_search": {
                        "type": "standard",
                        "stopwords": "_english_"
                    },
                    # Edge ngram analyzer for autocomplete and fuzzy matching
                    "edge_ngram_analyzer": {
                        "type": "custom",
                        "tokenizer": "edge_ngram_tokenizer",
                        "filter": ["lowercase", "asciifolding"]
                    },
                    # Ngram analyzer for fuzzy/spelling mistake tolerance
                    "ngram_analyzer": {
                        "type": "custom",
                        "tokenizer": "ngram_tokenizer",
                        "filter": ["lowercase", "asciifolding"]
                    },
                    # Whitespace analyzer for exact phrase matching
                    "whitespace_analyzer": {
                        "type": "whitespace",
                        "filter": ["lowercase"]
                    }
                },
                "tokenizer": {
                    "edge_ngram_tokenizer": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 10,
                        "token_chars": ["letter", "digit"]
                    },
                    "ngram_tokenizer": {
                        "type": "ngram",
                        "min_gram": 3,
                        "max_gram": 4,
                        "token_chars": ["letter", "digit"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                # ============ Identification Fields (stored only) ============
                "rid": {
                    "type": "keyword",
                    "index": False  # Not searchable, only stored
                },
                "docid": {
                    "type": "keyword",
                    "index": False
                },
                "url": {
                    "type": "keyword",
                    "index": False
                },

                # ============ Filterable Fields (exact match only) ============
                "country": {
                    "type": "keyword"  # For exact filtering (Denmark/Dominica)
                },
                "year": {
                    "type": "integer"  # For range queries and aggregations
                },
                "event_count": {
                    "type": "integer"  # For numerical analysis
                },

                # ============ High Priority Searchable Fields ============
                # These are the most distinctive fields with less overlap
                "event_title": {
                    "type": "text",
                    "analyzer": "standard_search",
                    "fields": {
                        "keyword": {"type": "keyword"},  # For exact matching
                        "ngram": {
                            "type": "text",
                            "analyzer": "ngram_analyzer"  # For fuzzy matching
                        },
                        "edge_ngram": {
                            "type": "text",
                            "analyzer": "edge_ngram_analyzer"  # For autocomplete
                        }
                    },
                    "boost": 3.0  # Highest priority in search
                },
                "event_theme": {
                    "type": "text",
                    "analyzer": "standard_search",
                    "fields": {
                        "keyword": {"type": "keyword"},
                        "ngram": {
                            "type": "text",
                            "analyzer": "ngram_analyzer"
                        }
                    },
                    "boost": 2.5
                },
                "event_highlight": {
                    "type": "text",
                    "analyzer": "standard_search",
                    "fields": {
                        "ngram": {
                            "type": "text",
                            "analyzer": "ngram_analyzer"
                        }
                    },
                    "boost": 2.0
                },

                # ============ Medium Priority Searchable Fields ============
                "event_summary": {
                    "type": "text",
                    "analyzer": "standard_search",
                    "fields": {
                        "ngram": {
                            "type": "text",
                            "analyzer": "ngram_analyzer"
                        }
                    },
                    "boost": 1.5
                },
                "event_object": {
                    "type": "text",
                    "analyzer": "standard_search",
                    "fields": {
                        "ngram": {
                            "type": "text",
                            "analyzer": "ngram_analyzer"
                        }
                    },
                    "boost": 1.2
                },

                # ============ Stored Only Fields (avoid overlap) ============
                # These fields contain overlapping information, so we store them
                # but don't index for search to avoid redundant matches
                "commentary_summary": {
                    "type": "text",
                    "index": False  # Stored but not searchable
                },
                "next_event_plan": {
                    "type": "text",
                    "index": False
                },
                "event_conclusion": {
                    "type": "text",
                    "index": False
                },
                "event_conclusion_overall": {
                    "type": "text",
                    "index": False
                },
                "next_event_suggestion": {
                    "type": "text",
                    "index": False
                }
            }
        }
    }

    return mapping


def delete_index_if_exists():
    """Delete the index if it already exists"""
    if client.indices.exists(index=INDEX_NAME):
        print(f"Deleting existing index: {INDEX_NAME}")
        client.indices.delete(index=INDEX_NAME)
        print(f"✓ Index {INDEX_NAME} deleted")


def create_index():
    """Create the OpenSearch index with the defined mapping"""
    try:
        mapping = create_index_mapping()

        # Delete existing index if present
        delete_index_if_exists()

        # Create new index
        print(f"\nCreating index: {INDEX_NAME}")
        response = client.indices.create(index=INDEX_NAME, body=mapping)
        print(f"✓ Index {INDEX_NAME} created successfully")
        print(f"Response: {response}")
        return True

    except Exception as e:
        print(f"✗ Error creating index: {e}")
        return False


def load_json_documents(docs_dir: str = 'docs2') -> List[Dict]:
    """Load all JSON documents from the docs2 directory"""
    documents = []
    json_files = sorted([f for f in os.listdir(docs_dir) if f.endswith('.json')])

    print(f"\nLoading {len(json_files)} JSON documents from {docs_dir}/")

    for filename in json_files:
        filepath = os.path.join(docs_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                doc = json.load(f)
                documents.append(doc)
        except Exception as e:
            print(f"✗ Error loading {filename}: {e}")

    print(f"✓ Loaded {len(documents)} documents")
    return documents


def index_documents(documents: List[Dict]):
    """Bulk index documents into OpenSearch"""
    try:
        print(f"\nIndexing {len(documents)} documents into {INDEX_NAME}...")

        # Prepare bulk indexing actions
        actions = [
            {
                "_index": INDEX_NAME,
                "_id": doc.get("docid"),  # Use docid as document ID
                "_source": doc
            }
            for doc in documents
        ]

        # Bulk index
        success, failed = helpers.bulk(client, actions, raise_on_error=False)

        print(f"✓ Successfully indexed: {success} documents")
        if failed:
            print(f"✗ Failed to index: {len(failed)} documents")

        # Refresh index to make documents searchable immediately
        client.indices.refresh(index=INDEX_NAME)
        print(f"✓ Index refreshed")

        return success, failed

    except Exception as e:
        print(f"✗ Error indexing documents: {e}")
        return 0, []


def verify_index():
    """Verify the index was created and documents were indexed"""
    try:
        # Get index stats
        stats = client.indices.stats(index=INDEX_NAME)
        doc_count = stats['_all']['primaries']['docs']['count']

        # Get index settings and mappings
        settings = client.indices.get_settings(index=INDEX_NAME)
        mappings = client.indices.get_mapping(index=INDEX_NAME)

        print(f"\n{'='*60}")
        print(f"INDEX VERIFICATION")
        print(f"{'='*60}")
        print(f"Index Name: {INDEX_NAME}")
        print(f"Total Documents: {doc_count}")
        print(f"Number of Shards: {settings[INDEX_NAME]['settings']['index']['number_of_shards']}")
        print(f"Number of Replicas: {settings[INDEX_NAME]['settings']['index']['number_of_replicas']}")

        # Count searchable vs non-searchable fields
        properties = mappings[INDEX_NAME]['mappings']['properties']
        searchable = sum(1 for field, config in properties.items()
                        if config.get('type') == 'text' and config.get('index', True) != False)
        non_searchable = sum(1 for field, config in properties.items()
                            if config.get('index') == False)
        filterable = sum(1 for field, config in properties.items()
                        if config.get('type') in ['keyword', 'integer'] and config.get('index', True) != False)

        print(f"\nField Configuration:")
        print(f"  Searchable text fields: {searchable}")
        print(f"  Filterable fields: {filterable}")
        print(f"  Stored-only fields: {non_searchable}")
        print(f"{'='*60}")

        return True

    except Exception as e:
        print(f"✗ Error verifying index: {e}")
        return False


def demonstrate_search_capabilities():
    """Demonstrate various search capabilities"""
    print(f"\n{'='*60}")
    print(f"SEARCH CAPABILITY DEMONSTRATIONS")
    print(f"{'='*60}")

    # Example 1: Basic search with fuzzy matching
    print("\n1. Basic Search (with fuzzy matching for spelling mistakes):")
    print("   Query: 'renewabel enrgy' (misspelled)")
    query1 = {
        "query": {
            "multi_match": {
                "query": "renewabel enrgy",
                "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"],
                "fuzziness": "AUTO",
                "operator": "or"
            }
        },
        "size": 3
    }

    try:
        response1 = client.search(index=INDEX_NAME, body=query1)
        print(f"   Found {response1['hits']['total']['value']} matches")
        for hit in response1['hits']['hits'][:3]:
            print(f"   - {hit['_source']['event_title']} (score: {hit['_score']:.2f})")
    except Exception as e:
        print(f"   Error: {e}")

    # Example 2: Year-wise aggregation
    print("\n2. Year-wise Event Distribution (for analysis):")
    query2 = {
        "size": 0,
        "aggs": {
            "events_by_year": {
                "terms": {
                    "field": "year",
                    "size": 10,
                    "order": {"_key": "asc"}
                },
                "aggs": {
                    "avg_attendance": {
                        "avg": {"field": "event_count"}
                    }
                }
            }
        }
    }

    try:
        response2 = client.search(index=INDEX_NAME, body=query2)
        for bucket in response2['aggregations']['events_by_year']['buckets']:
            print(f"   Year {bucket['key']}: {bucket['doc_count']} events, "
                  f"avg attendance: {bucket['avg_attendance']['value']:.0f}")
    except Exception as e:
        print(f"   Error: {e}")

    # Example 3: Country filter with search
    print("\n3. Search with Country Filter:")
    print("   Query: 'summit' in Denmark")
    query3 = {
        "query": {
            "bool": {
                "must": {
                    "multi_match": {
                        "query": "summit",
                        "fields": ["event_title^3", "event_theme^2.5", "event_summary^1.5"]
                    }
                },
                "filter": {
                    "term": {"country": "Denmark"}
                }
            }
        },
        "size": 3
    }

    try:
        response3 = client.search(index=INDEX_NAME, body=query3)
        print(f"   Found {response3['hits']['total']['value']} matches in Denmark")
        for hit in response3['hits']['hits'][:3]:
            print(f"   - {hit['_source']['event_title']}")
    except Exception as e:
        print(f"   Error: {e}")

    # Example 4: Hybrid search with ngram for partial matches
    print("\n4. Hybrid Search (ngram for partial word matching):")
    print("   Query: 'tech' (partial word)")
    query4 = {
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": "tech",
                            "fields": ["event_title^3", "event_theme^2.5"],
                            "type": "best_fields"
                        }
                    },
                    {
                        "multi_match": {
                            "query": "tech",
                            "fields": ["event_title.ngram", "event_theme.ngram"],
                            "type": "phrase"
                        }
                    }
                ]
            }
        },
        "size": 3
    }

    try:
        response4 = client.search(index=INDEX_NAME, body=query4)
        print(f"   Found {response4['hits']['total']['value']} matches")
        for hit in response4['hits']['hits'][:3]:
            print(f"   - {hit['_source']['event_title']}")
    except Exception as e:
        print(f"   Error: {e}")

    print(f"{'='*60}\n")


def main():
    """Main execution function"""
    print(f"{'='*60}")
    print(f"OPENSEARCH INDEX SETUP FOR EVENTS")
    print(f"{'='*60}")

    # Check OpenSearch connection
    try:
        info = client.info()
        print(f"\n✓ Connected to OpenSearch")
        print(f"  Version: {info['version']['number']}")
        print(f"  Cluster: {info['cluster_name']}")
    except Exception as e:
        print(f"\n✗ Failed to connect to OpenSearch: {e}")
        print(f"  Please ensure OpenSearch is running on {OPENSEARCH_HOST}:{OPENSEARCH_PORT}")
        return

    # Step 1: Create index
    if not create_index():
        return

    # Step 2: Load documents
    documents = load_json_documents('docs2')
    if not documents:
        print("✗ No documents to index")
        return

    # Step 3: Index documents
    success, failed = index_documents(documents)

    # Step 4: Verify index
    if verify_index():
        print("\n✓ Index setup completed successfully!")

    # Step 5: Demonstrate search capabilities
    demonstrate_search_capabilities()

    print(f"\nIndex '{INDEX_NAME}' is ready for use!")
    print(f"You can now perform searches, aggregations, and year-wise analysis.")


if __name__ == "__main__":
    main()
