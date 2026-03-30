FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

COPY requirements.txt /tmp/requirements-root.txt
COPY analyzer/requirements.txt /tmp/requirements-analyzer.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-root.txt \
    && pip install --no-cache-dir -r /tmp/requirements-analyzer.txt \
    && python -m spacy download fr_core_news_sm

COPY . /app

CMD ["python", "analyzer/main.py"]
