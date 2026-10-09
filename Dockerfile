FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir fastapi uvicorn 'pydantic>=2.10,<3' httpx \
    'PyJWT[crypto]>=2.10,<3' 'psycopg[binary]>=3.3,<4' 'psycopg_pool>=3.3,<4'

COPY . .
EXPOSE 8002
CMD ["python", "-m", "uvicorn", "apps.api:production_app", "--factory", "--host", "0.0.0.0", "--port", "8002"]
