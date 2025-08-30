from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class SearchRequest(BaseModel):
    query: str
    field: Optional[str] = "all"  # "all", "story", "story_summary"
    size: Optional[int] = 10


class SearchResponse(BaseModel):
    hits: List[Dict[Any, Any]]
    total: int
    took: int
    engine_type: str