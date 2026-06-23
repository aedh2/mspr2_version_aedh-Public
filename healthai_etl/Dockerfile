FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/healthai_etl

COPY healthai_etl/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY healthai_etl .

CMD ["python", "run_all_etl.py"]
