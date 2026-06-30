FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

COPY pyproject.toml uv.lock /app/

RUN uv pip install --system .

COPY . /app

ENV MLFLOW_URL=http://127.0.0.1:5000

EXPOSE 8000 5000

CMD ["honcho", "start", "-f", "Procfile"]
