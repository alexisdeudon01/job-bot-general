FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y gcc libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

COPY requirements.txt /tmp/requirements-root.txt
COPY dashboard/requirements.txt /tmp/requirements-dashboard.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-root.txt \
    && pip install --no-cache-dir -r /tmp/requirements-dashboard.txt \
    && python -m spacy download fr_core_news_sm

COPY . /app

CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
