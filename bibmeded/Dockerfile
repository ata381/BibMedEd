FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
RUN pip install --no-cache-dir ".[server]"

COPY . .

RUN chmod +x scripts/entrypoint.sh

ENTRYPOINT ["scripts/entrypoint.sh"]
CMD ["uvicorn", "bibmeded.main:app", "--host", "0.0.0.0", "--port", "8000"]
