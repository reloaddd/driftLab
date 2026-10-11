
# DriftLab — Python 3.12 application image

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

# Install dependencies before copying application source.
# This helps Docker reuse cached installation layers.
COPY deployment/requirements-lock.txt \
     /app/deployment/requirements-lock.txt

RUN python -m pip install --no-cache-dir \
    -r /app/deployment/requirements-lock.txt

# Copy application source.
COPY api/ /app/api/
COPY src/ /app/src/
COPY frontend/ /app/frontend/

# Models and data are mounted by Docker Compose.
RUN mkdir -p /app/models /app/data

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
