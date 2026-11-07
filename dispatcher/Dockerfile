FROM python:3.12-slim

WORKDIR /dispatcher

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# No root needed: it only makes outbound HTTP calls
RUN useradd --system --uid 10001 --no-create-home dispatcher
USER dispatcher

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
