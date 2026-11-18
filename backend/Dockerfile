FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /repo/backend

# CPU-only torch first, so pip doesn't pull the multi-GB CUDA build

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu 

COPY backend/requirements.txt backend/requirements-vision.txt ./
RUN pip install -r requirements.txt -r requirements-vision.txt

COPY shared /repo/shared
COPY backend /repo/backend

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]