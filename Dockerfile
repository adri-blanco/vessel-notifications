FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN pip install --no-cache-dir .

CMD ["ais-notify"]
