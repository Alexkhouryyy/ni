FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt
RUN python -m playwright install chromium --with-deps

COPY . .

ENV PYTHONUNBUFFERED=1 \
    DASHBOARD_HOST=0.0.0.0 \
    DASHBOARD_PORT=7860

EXPOSE 7860

CMD ["python", "main.py", "--text", "--no-proactive", "--no-screenshot"]
