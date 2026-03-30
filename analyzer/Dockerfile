FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# Create and use a virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download fr_core_news_sm

COPY . .

CMD ["python", "main.py"]