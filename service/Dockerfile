FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Outcomes are recorded here. Mount a volume so the ledger survives a restart,
# or point AUDITOR_LEDGER_PATH at a database-backed store in production.
RUN mkdir -p /data
VOLUME /data

EXPOSE 8080
# One worker: the file ledger is locked per process, and a signing service does
# not need concurrency before it needs a database.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
