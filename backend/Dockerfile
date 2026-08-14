FROM python:3.12-slim

WORKDIR /app

ARG INSTALL_BACKTEST=0

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/* \
  && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md* ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# hatchling 需要 package；无 README 时补空文件避免构建失败
RUN if [ ! -f README.md ]; then echo "zak2-api" > README.md; fi \
  && if [ "$INSTALL_BACKTEST" = "1" ]; then \
       uv sync --frozen --no-dev --extra backtest; \
     else \
       uv sync --frozen --no-dev; \
     fi

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
