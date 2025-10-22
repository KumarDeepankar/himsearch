FROM python:3.11-slim

LABEL maintainer="HimSearch Team"
LABEL description="FastMCP Events Search Server - Optimized search for OpenSearch events index"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .

# Set default environment variables
ENV OPENSEARCH_URL=http://localhost:9200
ENV INDEX_NAME=events
ENV HOST=0.0.0.0
ENV PORT=8002
ENV MIN_SCORE_RID=2.5
ENV MIN_SCORE_DOCID=3.5
ENV MIN_PREFIX_SCORE=1.0
ENV MAX_PREFIX_RESULTS=8

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:8002/health', timeout=5)" || exit 1

# Run server
CMD ["python", "server.py"]
