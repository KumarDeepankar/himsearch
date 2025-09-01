#!/usr/bin/env python3
"""
Simple Search Engine JSON Indexer for Story Documents
Supports Elasticsearch and OpenSearch
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import requests
import os


class SimpleSearchIndexer:
    def __init__(self, host="localhost", port=9200):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def test_connection(self):
        """Test connection to search engine."""
        try:
            response = self.session.get(f"{self.base_url}/")
            response.raise_for_status()
            print("✅ Connected to search engine")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to search engine: {e}")
            return False

    def create_index(self, index_name, mapping_file):
        """Create index with mapping."""
        try:
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)

            # Delete existing index if it exists
            response = self.session.head(f"{self.base_url}/{index_name}")
            if response.status_code == 200:
                print(f"🗑️ Deleting existing index: {index_name}")
                self.session.delete(f"{self.base_url}/{index_name}")

            # Create new index
            response = self.session.put(f"{self.base_url}/{index_name}", json=mapping)
            if response.status_code >= 400:
                print(f"❌ Error creating index: {response.status_code}")
                print(f"Response: {response.text}")
                return False
            
            response.raise_for_status()
            print(f"✅ Created index: {index_name}")
            return True

        except Exception as e:
            print(f"❌ Error creating index: {e}")
            return False

    def index_documents(self, docs_dir, index_name):
        """Index all JSON files from directory."""
        docs_path = Path(docs_dir)

        if not docs_path.exists():
            print(f"❌ Directory not found: {docs_dir}")
            return

        json_files = list(docs_path.glob("*.json"))
        if not json_files:
            print(f"❌ No JSON files found in {docs_dir}")
            return

        print(f"📁 Indexing {len(json_files)} files...")

        successful = 0
        failed = 0

        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    doc = json.load(f)

                # Prepare document for indexing
                indexed_doc = {
                    "document_id": doc.get("id"),
                    "story": doc.get("story"),
                    "story_summary": doc.get("story_summary"),
                    "indexed_at": datetime.utcnow().isoformat()
                }

                # Index document using the document ID
                doc_id = doc.get("id")
                response = self.session.put(
                    f"{self.base_url}/{index_name}/_doc/{doc_id}",
                    json=indexed_doc
                )
                if response.status_code >= 400:
                    print(f"❌ Error indexing {json_file.name}: {response.status_code}")
                    print(f"Response: {response.text}")
                    failed += 1
                    continue
                
                response.raise_for_status()
                print(f"✅ Indexed {json_file.name}")
                successful += 1

            except Exception as e:
                print(f"❌ Error indexing {json_file.name}: {e}")
                failed += 1

        print(f"\n📊 Results: {successful} successful, {failed} failed")

        # Refresh index
        self.session.post(f"{self.base_url}/{index_name}/_refresh")
        print("🔄 Index refreshed")


def main():
    index_name = "stories"
    mapping_file = os.path.join(os.path.dirname(__file__), "index_mapping.json")
    docs_dir = "../docs"

    print(f"🚀 Indexing documents into '{index_name}'")
    print(f"📋 Using mapping: {mapping_file}")
    print(f"📁 From directory: {docs_dir}")
    print("=" * 40)

    indexer = SimpleSearchIndexer()

    if not indexer.test_connection():
        sys.exit(1)

    if not indexer.create_index(index_name, mapping_file):
        sys.exit(1)

    indexer.index_documents(docs_dir, index_name)
    print("\n🎉 Done!")


if __name__ == "__main__":
    main()