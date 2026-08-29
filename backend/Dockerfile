FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements-dev.txt ./
# Dev deps (pytest) are tiny and let the test suite run inside the running container.
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY backend/app ./app
COPY backend/tests ./tests
COPY backend/pytest.ini .
COPY data ./data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
