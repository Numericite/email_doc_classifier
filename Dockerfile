FROM python:3.13

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .
 
ENV PYTHONPATH=/app/src/document_assisstant

CMD ["python", "-m", "orchestration.pipeline_v2"]
