FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /app

COPY requirements.txt /tmp/requirements-root.txt
COPY agent/requirements.txt /tmp/requirements-agent.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements-root.txt \
    && pip install --no-cache-dir -r /tmp/requirements-agent.txt

COPY . /app

CMD ["python", "agent/main.py"]
