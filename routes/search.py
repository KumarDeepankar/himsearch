from fastapi import APIRouter, HTTPException, Query
from models import SearchRequest, SearchResponse
from search.engine import SearchEngine, SEARCH_ENGINE_URL, USERNAME, PASSWORD
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize search engine
search_engine = SearchEngine(SEARCH_ENGINE_URL, USERNAME, PASSWORD)


@router.post("/search", response_model=SearchResponse)
async def search_stories(request: SearchRequest):
    """Search stories endpoint"""
    try:
        result = search_engine.search(request.query, request.field, request.size)

        return SearchResponse(
            hits=result.get("hits", {}).get("hits", []),
            total=result.get("hits", {}).get("total", {}).get("value", 0) if isinstance(
                result.get("hits", {}).get("total"), dict) else result.get("hits", {}).get("total", 0),
            took=result.get("took", 0),
            engine_type=search_engine.engine_type
        )
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_engine_info():
    """Get search engine information"""
    return {
        "engine_type": search_engine.engine_type,
        "url": SEARCH_ENGINE_URL,
        "index_name": "stories"
    }


@router.get("/suggestions")
async def get_suggestions(q: str = Query(..., min_length=1, description="Search query for suggestions")):
    """Get search suggestions based on partial query"""
    try:
        result = search_engine.get_suggestions(q, size=5)
        return result
    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))