#!/usr/bin/env python3
"""
Example script demonstrating how to search the events index
Uses HTTP calls with requests library
"""

import json
import requests


class EventsSearcher:
    def __init__(self, host="localhost", port=9200):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.index_name = "events"

    def search(self, query_body):
        """Execute a search query."""
        try:
            response = self.session.post(
                f"{self.base_url}/{self.index_name}/_search",
                json=query_body
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error executing search: {e}")
            return None

    def fuzzy_search(self, search_text, size=5):
        """
        Perform fuzzy search with spelling mistake tolerance.
        Searches across event_title, event_theme, event_summary fields.
        """
        query = {
            "query": {
                "multi_match": {
                    "query": search_text,
                    "fields": [
                        "event_title^3",
                        "event_theme^2.5",
                        "event_summary^1.5",
                        "event_object^1.2"
                    ],
                    "fuzziness": "AUTO",
                    "operator": "or"
                }
            },
            "size": size
        }
        return self.search(query)

    def hybrid_search(self, search_text, size=5):
        """
        Perform hybrid search combining standard and ngram analyzers.
        Better for partial word matches and fuzzy matching.
        """
        query = {
            "query": {
                "bool": {
                    "should": [
                        # Standard search
                        {
                            "multi_match": {
                                "query": search_text,
                                "fields": [
                                    "event_title^3",
                                    "event_theme^2.5",
                                    "event_summary^1.5"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        },
                        # Ngram search for fuzzy matching
                        {
                            "multi_match": {
                                "query": search_text,
                                "fields": [
                                    "event_title.ngram",
                                    "event_theme.ngram",
                                    "event_summary.ngram"
                                ],
                                "type": "best_fields"
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "size": size
        }
        return self.search(query)

    def search_by_country(self, search_text, country, size=5):
        """Search events in a specific country."""
        query = {
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": search_text,
                            "fields": [
                                "event_title^3",
                                "event_theme^2.5",
                                "event_summary^1.5"
                            ],
                            "fuzziness": "AUTO"
                        }
                    },
                    "filter": {
                        "term": {"country": country}
                    }
                }
            },
            "size": size
        }
        return self.search(query)

    def search_by_year_range(self, search_text, start_year, end_year, size=5):
        """Search events within a year range."""
        query = {
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": search_text,
                            "fields": [
                                "event_title^3",
                                "event_theme^2.5",
                                "event_summary^1.5"
                            ],
                            "fuzziness": "AUTO"
                        }
                    },
                    "filter": {
                        "range": {
                            "year": {
                                "gte": start_year,
                                "lte": end_year
                            }
                        }
                    }
                }
            },
            "size": size
        }
        return self.search(query)

    def year_wise_analysis(self):
        """Get year-wise event distribution with average attendance."""
        query = {
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
                        },
                        "total_attendance": {
                            "sum": {"field": "event_count"}
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
        return self.search(query)

    def country_wise_analysis(self, year=None):
        """Get country-wise event distribution, optionally filtered by year."""
        query = {
            "size": 0,
            "aggs": {
                "events_by_country": {
                    "terms": {
                        "field": "country",
                        "size": 10
                    },
                    "aggs": {
                        "avg_attendance": {
                            "avg": {"field": "event_count"}
                        }
                    }
                }
            }
        }

        if year:
            query["query"] = {
                "term": {"year": year}
            }

        return self.search(query)

    def theme_analysis(self):
        """Get top event themes."""
        query = {
            "size": 0,
            "aggs": {
                "top_themes": {
                    "terms": {
                        "field": "event_theme.keyword",
                        "size": 20
                    }
                }
            }
        }
        return self.search(query)

    def print_search_results(self, results, show_full=False):
        """Pretty print search results."""
        if not results or 'hits' not in results:
            print("No results found")
            return

        total = results['hits']['total']['value']
        hits = results['hits']['hits']

        print(f"\n📊 Total matches: {total}")
        print(f"📄 Showing top {len(hits)} results:\n")

        for i, hit in enumerate(hits, 1):
            source = hit['_source']
            score = hit['_score']

            print(f"{i}. {source.get('event_title', 'N/A')}")
            print(f"   🏆 Score: {score:.2f}")
            print(f"   🌍 Country: {source.get('country', 'N/A')}")
            print(f"   📅 Year: {source.get('year', 'N/A')}")
            print(f"   🎯 Theme: {source.get('event_theme', 'N/A')}")
            print(f"   👥 Attendance: {source.get('event_count', 'N/A')}")

            if show_full:
                print(f"   📝 Summary: {source.get('event_summary', 'N/A')[:200]}...")
                print(f"   ✨ Highlight: {source.get('event_highlight', 'N/A')[:200]}...")

            print()


def main():
    """Demonstrate various search capabilities."""
    print("="*70)
    print("OPENSEARCH EVENTS INDEX - SEARCH EXAMPLES")
    print("="*70)

    searcher = EventsSearcher()

    # Example 1: Fuzzy search with spelling mistakes
    print("\n1. 🔍 FUZZY SEARCH (with spelling mistakes)")
    print("-" * 70)
    print("Query: 'renewabel enrgy' (misspelled)")
    results = searcher.fuzzy_search("renewabel enrgy", size=3)
    if results:
        searcher.print_search_results(results)

    # Example 2: Hybrid search
    print("\n2. 🔬 HYBRID SEARCH")
    print("-" * 70)
    print("Query: 'technology summit'")
    results = searcher.hybrid_search("technology summit", size=3)
    if results:
        searcher.print_search_results(results)

    # Example 3: Search by country
    print("\n3. 🌍 SEARCH BY COUNTRY")
    print("-" * 70)
    print("Query: 'conference' in Denmark")
    results = searcher.search_by_country("conference", "Denmark", size=3)
    if results:
        searcher.print_search_results(results)

    # Example 4: Search by year range
    print("\n4. 📆 SEARCH BY YEAR RANGE")
    print("-" * 70)
    print("Query: 'summit' between 2022-2023")
    results = searcher.search_by_year_range("summit", 2022, 2023, size=3)
    if results:
        searcher.print_search_results(results)

    # Example 5: Year-wise analysis
    print("\n5. 📊 YEAR-WISE ANALYSIS")
    print("-" * 70)
    results = searcher.year_wise_analysis()
    if results and 'aggregations' in results:
        buckets = results['aggregations']['events_by_year']['buckets']
        print("\nYear | Events | Avg Attendance | Total Attendance | Min | Max")
        print("-" * 70)
        for bucket in buckets:
            year = bucket['key']
            count = bucket['doc_count']
            avg = bucket['avg_attendance']['value']
            total = bucket['total_attendance']['value']
            min_att = bucket['min_attendance']['value']
            max_att = bucket['max_attendance']['value']
            print(f"{year} | {count:6d} | {avg:14.0f} | {total:16.0f} | {min_att:3.0f} | {max_att:5.0f}")

    # Example 6: Country-wise analysis
    print("\n6. 🗺️  COUNTRY-WISE ANALYSIS")
    print("-" * 70)
    results = searcher.country_wise_analysis()
    if results and 'aggregations' in results:
        buckets = results['aggregations']['events_by_country']['buckets']
        print("\nCountry  | Events | Avg Attendance")
        print("-" * 40)
        for bucket in buckets:
            country = bucket['key']
            count = bucket['doc_count']
            avg = bucket['avg_attendance']['value']
            print(f"{country:8s} | {count:6d} | {avg:14.0f}")

    # Example 7: Theme analysis
    print("\n7. 🎯 TOP EVENT THEMES")
    print("-" * 70)
    results = searcher.theme_analysis()
    if results and 'aggregations' in results:
        buckets = results['aggregations']['top_themes']['buckets']
        print("\nTop 10 Event Themes:")
        for i, bucket in enumerate(buckets[:10], 1):
            theme = bucket['key']
            count = bucket['doc_count']
            print(f"  {i:2d}. {theme:50s} ({count} events)")

    print("\n" + "="*70)
    print("✅ Search examples completed!")
    print("="*70)


if __name__ == "__main__":
    main()
