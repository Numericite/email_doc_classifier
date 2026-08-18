FROM python:3.13

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .
 
ENV PYTHONPATH=/app/src/document_assisstant

CMD ["python", "-m", "orchestration.pipeline_v2"]
