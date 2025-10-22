#!/usr/bin/env python3
"""
OpenSearch Indexer for Events
Creates and populates the 'events' index with documents from docs2 folder
Uses HTTP requests (GET/POST) instead of OpenSearch library
"""

import json
import requests
from pathlib import Path


def load_mapping(mapping_file='events_mapping.json'):
    """Load index mapping from JSON file"""
    with open(mapping_file, 'r') as f:
        return json.load(f)


def check_index_exists(base_url, index_name):
    """Check if index exists using HEAD request"""
    url = f"{base_url}/{index_name}"
    response = requests.head(url)
    return response.status_code == 200


def delete_index(base_url, index_name):
    """Delete index if it exists"""
    url = f"{base_url}/{index_name}"
    response = requests.delete(url)
    if response.status_code == 200:
        print(f"Index '{index_name}' deleted successfully.")
        return True
    else:
        print(f"Error deleting index: {response.text}")
        return False


def create_index(base_url, index_name='events', mapping_file='events_mapping.json'):
    """Create the OpenSearch index with mapping using PUT request"""
    # Check if index exists
    if check_index_exists(base_url, index_name):
        print(f"Index '{index_name}' already exists. Deleting...")
        delete_index(base_url, index_name)

    # Load mapping
    mapping = load_mapping(mapping_file)

    # Create index
    print(f"Creating index '{index_name}'...")
    url = f"{base_url}/{index_name}"

    try:
        response = requests.put(
            url,
            json=mapping,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code in [200, 201]:
            print(f"Index '{index_name}' created successfully!")
            return True
        else:
            print(f"Error creating index: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"Error creating index: {e}")
        return False


def load_documents(docs_folder='../docs2'):
    """Load all JSON documents from the docs folder"""
    docs_path = Path(docs_folder)
    documents = []

    if not docs_path.exists():
        print(f"Error: Folder '{docs_folder}' does not exist!")
        return documents

    json_files = sorted(docs_path.glob('*.json'))

    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                doc = json.load(f)
                documents.append(doc)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")

    print(f"Loaded {len(documents)} documents from '{docs_folder}'")
    return documents


def index_documents(base_url, documents, index_name='events'):
    """Index documents using POST/PUT requests"""
    print(f"Indexing {len(documents)} documents...")

    indexed_count = 0
    failed_count = 0

    for i, doc in enumerate(documents, 1):
        try:
            # Use rid as document ID
            doc_id = doc.get('rid', i)

            # PUT request to index document with specific ID
            url = f"{base_url}/{index_name}/_doc/{doc_id}"

            response = requests.put(
                url,
                json=doc,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code in [200, 201]:
                indexed_count += 1

                if i % 10 == 0:
                    print(f"Indexed {i}/{len(documents)} documents...")
            else:
                print(f"Error indexing document {i}: {response.status_code} - {response.text}")
                failed_count += 1

        except Exception as e:
            print(f"Error indexing document {i} (rid: {doc.get('rid', 'N/A')}): {e}")
            failed_count += 1

    # Refresh index to make documents searchable
    refresh_url = f"{base_url}/{index_name}/_refresh"
    requests.post(refresh_url)

    print(f"\nIndexing complete!")
    print(f"Successfully indexed: {indexed_count}")
    print(f"Failed: {failed_count}")

    return indexed_count, failed_count


def verify_index(base_url, index_name='events'):
    """Verify index creation and document count"""
    try:
        # Get index stats
        stats_url = f"{base_url}/{index_name}/_stats"
        stats_response = requests.get(stats_url)

        if stats_response.status_code == 200:
            stats = stats_response.json()
            doc_count = stats['_all']['primaries']['docs']['count']

            # Get index settings
            settings_url = f"{base_url}/{index_name}/_settings"
            settings_response = requests.get(settings_url)
            settings = settings_response.json()

            # Get index mapping
            mapping_url = f"{base_url}/{index_name}/_mapping"
            mapping_response = requests.get(mapping_url)
            mappings = mapping_response.json()

            print(f"\n{'='*50}")
            print(f"Index Verification")
            print(f"{'='*50}")
            print(f"Index name: {index_name}")
            print(f"Document count: {doc_count}")
            print(f"Shards: {settings[index_name]['settings']['index']['number_of_shards']}")
            print(f"Replicas: {settings[index_name]['settings']['index']['number_of_replicas']}")
            print(f"Fields mapped: {len(mappings[index_name]['mappings']['properties'])}")
            print(f"{'='*50}\n")

            return True
        else:
            print(f"Error verifying index: {stats_response.text}")
            return False
    except Exception as e:
        print(f"Error verifying index: {e}")
        return False


def main():
    """Main execution function"""
    print("OpenSearch Events Indexer (HTTP Requests)")
    print("="*50)

    # Configuration
    INDEX_NAME = 'events'
    MAPPING_FILE = 'events_mapping.json'
    DOCS_FOLDER = '../docs2'
    HOST = 'localhost'
    PORT = 9200
    BASE_URL = f"http://{HOST}:{PORT}"

    # Test connection
    print(f"Connecting to OpenSearch at {HOST}:{PORT}...")
    try:
        response = requests.get(BASE_URL)
        if response.status_code == 200:
            info = response.json()
            print(f"Connected to OpenSearch {info['version']['number']}")
            print()
        else:
            print(f"Error connecting to OpenSearch: {response.status_code}")
            return
    except Exception as e:
        print(f"Error connecting to OpenSearch: {e}")
        print("Make sure OpenSearch is running at localhost:9200")
        return

    # Create index
    if not create_index(BASE_URL, INDEX_NAME, MAPPING_FILE):
        return

    print()

    # Load documents
    documents = load_documents(DOCS_FOLDER)
    if not documents:
        print("No documents to index!")
        return

    print()

    # Index documents
    index_documents(BASE_URL, documents, INDEX_NAME)

    # Verify index
    verify_index(BASE_URL, INDEX_NAME)

    print("Indexing process completed successfully!")


if __name__ == '__main__':
    main()
