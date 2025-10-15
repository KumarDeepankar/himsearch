#!/usr/bin/env python3
"""
OpenSearch Events Index Creator using HTTP calls
Creates index with hybrid search capabilities and selective field indexing
"""

import json
import sys
from pathlib import Path
import requests


class EventsIndexer:
    def __init__(self, host="localhost", port=9200):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.index_name = "events"

    def test_connection(self):
        """Test connection to OpenSearch."""
        try:
            response = self.session.get(f"{self.base_url}/")
            response.raise_for_status()
            info = response.json()
            print(f"✅ Connected to OpenSearch")
            print(f"   Version: {info.get('version', {}).get('number', 'unknown')}")
            print(f"   Cluster: {info.get('cluster_name', 'unknown')}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to OpenSearch: {e}")
            return False

    def create_index(self, mapping_file):
        """Create index with mapping from JSON file."""
        try:
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)

            # Check if index exists
            response = self.session.head(f"{self.base_url}/{self.index_name}")
            if response.status_code == 200:
                print(f"🗑️  Deleting existing index: {self.index_name}")
                delete_response = self.session.delete(f"{self.base_url}/{self.index_name}")
                if delete_response.status_code >= 400:
                    print(f"❌ Error deleting index: {delete_response.status_code}")
                    print(f"Response: {delete_response.text}")
                    return False
                print(f"✅ Deleted existing index: {self.index_name}")

            # Create new index
            print(f"\n📝 Creating index: {self.index_name}")
            response = self.session.put(f"{self.base_url}/{self.index_name}", json=mapping)

            if response.status_code >= 400:
                print(f"❌ Error creating index: {response.status_code}")
                print(f"Response: {response.text}")
                return False

            response.raise_for_status()
            print(f"✅ Created index: {self.index_name}")
            return True

        except FileNotFoundError:
            print(f"❌ Mapping file not found: {mapping_file}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in mapping file: {e}")
            return False
        except Exception as e:
            print(f"❌ Error creating index: {e}")
            return False

    def index_documents(self, docs_dir):
        """Index all JSON files from directory."""
        docs_path = Path(docs_dir)

        if not docs_path.exists():
            print(f"❌ Directory not found: {docs_dir}")
            return 0, 0

        json_files = sorted(list(docs_path.glob("*.json")))
        if not json_files:
            print(f"❌ No JSON files found in {docs_dir}")
            return 0, 0

        print(f"\n📁 Indexing {len(json_files)} files from {docs_dir}/...")

        successful = 0
        failed = 0

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    doc = json.load(f)

                # Use docid as the document ID
                doc_id = doc.get("docid")
                if not doc_id:
                    print(f"⚠️  Skipping {json_file.name}: missing docid")
                    failed += 1
                    continue

                # Index document
                response = self.session.put(
                    f"{self.base_url}/{self.index_name}/_doc/{doc_id}",
                    json=doc
                )

                if response.status_code >= 400:
                    print(f"❌ Error indexing {json_file.name}: {response.status_code}")
                    print(f"Response: {response.text}")
                    failed += 1
                    continue

                response.raise_for_status()

                # Print progress every 10 documents
                if (successful + 1) % 10 == 0:
                    print(f"   ✅ Indexed {successful + 1} documents...")

                successful += 1

            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON in {json_file.name}: {e}")
                failed += 1
            except Exception as e:
                print(f"❌ Error indexing {json_file.name}: {e}")
                failed += 1

        print(f"\n📊 Indexing Results:")
        print(f"   ✅ Successful: {successful}")
        print(f"   ❌ Failed: {failed}")
        print(f"   📈 Total: {successful + failed}")

        # Refresh index to make documents immediately searchable
        print(f"\n🔄 Refreshing index...")
        refresh_response = self.session.post(f"{self.base_url}/{self.index_name}/_refresh")
        if refresh_response.status_code == 200:
            print(f"✅ Index refreshed")

        return successful, failed

    def verify_index(self):
        """Verify the index was created and get statistics."""
        try:
            # Get index stats
            stats_response = self.session.get(f"{self.base_url}/{self.index_name}/_stats")
            if stats_response.status_code != 200:
                print(f"❌ Error getting stats: {stats_response.status_code}")
                return False

            stats = stats_response.json()
            doc_count = stats['_all']['primaries']['docs']['count']

            # Get index settings
            settings_response = self.session.get(f"{self.base_url}/{self.index_name}/_settings")
            settings = settings_response.json()

            # Get index mapping
            mapping_response = self.session.get(f"{self.base_url}/{self.index_name}/_mapping")
            mappings = mapping_response.json()

            print(f"\n{'='*60}")
            print(f"INDEX VERIFICATION")
            print(f"{'='*60}")
            print(f"Index Name: {self.index_name}")
            print(f"Total Documents: {doc_count}")

            index_settings = settings[self.index_name]['settings']['index']
            print(f"Number of Shards: {index_settings.get('number_of_shards', 'N/A')}")
            print(f"Number of Replicas: {index_settings.get('number_of_replicas', 'N/A')}")

            # Count field types
            properties = mappings[self.index_name]['mappings']['properties']
            searchable = sum(1 for field, config in properties.items()
                            if config.get('type') == 'text' and config.get('index', True) != False)
            non_searchable = sum(1 for field, config in properties.items()
                                if config.get('index') == False)
            filterable = sum(1 for field, config in properties.items()
                            if config.get('type') in ['keyword', 'integer'] and config.get('index', True) != False)

            print(f"\nField Configuration:")
            print(f"  ✅ Searchable text fields: {searchable}")
            print(f"  🔍 Filterable fields: {filterable}")
            print(f"  💾 Stored-only fields: {non_searchable}")
            print(f"{'='*60}")

            return True

        except Exception as e:
            print(f"❌ Error verifying index: {e}")
            return False

    def demonstrate_searches(self):
        """Demonstrate various search capabilities."""
        print(f"\n{'='*60}")
        print(f"SEARCH CAPABILITY DEMONSTRATIONS")
        print(f"{'='*60}")

        # Example 1: Basic search with fuzzy matching for spelling mistakes
        print("\n1. 🔍 Fuzzy Search (handles spelling mistakes):")
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
            response = self.session.post(
                f"{self.base_url}/{self.index_name}/_search",
                json=query1
            )
            if response.status_code == 200:
                result = response.json()
                total = result['hits']['total']['value']
                print(f"   ✅ Found {total} matches")
                for hit in result['hits']['hits'][:3]:
                    print(f"      - {hit['_source']['event_title']} (score: {hit['_score']:.2f})")
            else:
                print(f"   ❌ Error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Example 2: Year-wise aggregation
        print("\n2. 📊 Year-wise Event Distribution:")
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
            response = self.session.post(
                f"{self.base_url}/{self.index_name}/_search",
                json=query2
            )
            if response.status_code == 200:
                result = response.json()
                for bucket in result['aggregations']['events_by_year']['buckets']:
                    year = bucket['key']
                    count = bucket['doc_count']
                    avg = bucket['avg_attendance']['value']
                    print(f"   📅 Year {year}: {count} events, avg attendance: {avg:.0f}")
            else:
                print(f"   ❌ Error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Example 3: Country filter with search
        print("\n3. 🌍 Search with Country Filter:")
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
            response = self.session.post(
                f"{self.base_url}/{self.index_name}/_search",
                json=query3
            )
            if response.status_code == 200:
                result = response.json()
                total = result['hits']['total']['value']
                print(f"   ✅ Found {total} matches in Denmark")
                for hit in result['hits']['hits'][:3]:
                    print(f"      - {hit['_source']['event_title']}")
            else:
                print(f"   ❌ Error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Example 4: Hybrid search with ngram for partial matches
        print("\n4. 🔬 Hybrid Search (standard + ngram):")
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
            response = self.session.post(
                f"{self.base_url}/{self.index_name}/_search",
                json=query4
            )
            if response.status_code == 200:
                result = response.json()
                total = result['hits']['total']['value']
                print(f"   ✅ Found {total} matches")
                for hit in result['hits']['hits'][:3]:
                    print(f"      - {hit['_source']['event_title']}")
            else:
                print(f"   ❌ Error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        # Example 5: Year range analysis
        print("\n5. 📆 Year Range Analysis:")
        print("   Query: Events in 2022-2023")
        query5 = {
            "query": {
                "range": {
                    "year": {
                        "gte": 2022,
                        "lte": 2023
                    }
                }
            },
            "size": 0,
            "aggs": {
                "by_country": {
                    "terms": {
                        "field": "country",
                        "size": 10
                    }
                }
            }
        }

        try:
            response = self.session.post(
                f"{self.base_url}/{self.index_name}/_search",
                json=query5
            )
            if response.status_code == 200:
                result = response.json()
                total = result['hits']['total']['value']
                print(f"   ✅ Found {total} events in 2022-2023")
                print(f"   📍 Distribution by country:")
                for bucket in result['aggregations']['by_country']['buckets']:
                    print(f"      - {bucket['key']}: {bucket['doc_count']} events")
            else:
                print(f"   ❌ Error: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

        print(f"\n{'='*60}")


def main():
    """Main execution function."""
    index_name = "events"
    mapping_file = "events_mapping.json"
    docs_dir = "docs2"

    print(f"{'='*60}")
    print(f"OPENSEARCH EVENTS INDEX CREATOR")
    print(f"{'='*60}")
    print(f"🎯 Index name: {index_name}")
    print(f"📋 Mapping file: {mapping_file}")
    print(f"📁 Documents directory: {docs_dir}")
    print(f"{'='*60}")

    # Initialize indexer
    indexer = EventsIndexer()

    # Step 1: Test connection
    if not indexer.test_connection():
        print("\n❌ Setup failed: Cannot connect to OpenSearch")
        print("   Please ensure OpenSearch is running on localhost:9200")
        sys.exit(1)

    # Step 2: Create index
    if not indexer.create_index(mapping_file):
        print("\n❌ Setup failed: Cannot create index")
        sys.exit(1)

    # Step 3: Index documents
    successful, failed = indexer.index_documents(docs_dir)
    if successful == 0:
        print("\n❌ Setup failed: No documents indexed")
        sys.exit(1)

    # Step 4: Verify index
    if not indexer.verify_index():
        print("\n⚠️  Warning: Could not verify index")

    # Step 5: Demonstrate search capabilities
    indexer.demonstrate_searches()

    print(f"\n{'='*60}")
    print(f"🎉 INDEX SETUP COMPLETED SUCCESSFULLY!")
    print(f"{'='*60}")
    print(f"\n✅ Index '{index_name}' is ready for use!")
    print(f"   - Hybrid search with fuzzy matching enabled")
    print(f"   - Spelling mistake tolerance configured")
    print(f"   - Year-wise aggregation support enabled")
    print(f"   - {successful} documents indexed and searchable")
    print(f"\n💡 You can now perform searches and year-wise analysis!")


if __name__ == "__main__":
    main()
