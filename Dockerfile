FROM python:3.11-slim
WORKDIR /app
COPY app/requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y build-essential libpoppler-cpp-dev pkg-config python3-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r app/requirements.txt
COPY app ./app
ENV RAG_DB_PATH=/app/data/rag.db
ENV UPLOAD_DIR=/app/data/uploads
RUN mkdir -p /app/data/uploads
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
