FROM python:3.12-slim

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml .
COPY src/app src/app

RUN pip install --no-cache-dir .

COPY src/app src/app

USER app

ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
