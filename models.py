from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SearchRequest(BaseModel):
    query: str
    field: Optional[str] = "all"  # "all", "story", "story_summary", "doc_subject"
    size: Optional[int] = 10
    semantic_boost: Optional[float] = Field(default=0.3, ge=0.0, le=1.0, description="Weight for semantic similarity search (0.0-1.0)")
    include_fields: Optional[List[str]] = Field(default=None, description="Specific fields to include in response. If None, returns all available fields")
    exclude_fields: Optional[List[str]] = Field(default=None, description="Fields to exclude from response")


class SearchResponse(BaseModel):
    hits: List[Dict[Any, Any]]
    total: int
    took: int
    engine_type: str
    semantic_search_used: Optional[bool] = False