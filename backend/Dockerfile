FROM python:3.12-slim

WORKDIR /app
ENV FASTEMBED_CACHE_PATH=/app/.fastembed

COPY pyproject.toml ./
COPY app ./app
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .
# Download the local embedding model at build time, not on the first request.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

COPY data ./data
COPY scripts ./scripts

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
