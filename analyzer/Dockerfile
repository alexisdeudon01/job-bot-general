FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download fr_core_news_sm

COPY . .

CMD ["python", "main.py"]