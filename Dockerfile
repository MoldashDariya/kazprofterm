# Reproducible environment for the KazProfTerm experiment.
#   docker build -t kazprofterm .
#   docker run --rm kazprofterm                       # validate + tests + simulated run + analysis
#   docker run --rm -e ANTHROPIC_API_KEY -v "$PWD/skillbridge/runs:/app/skillbridge/runs" kazprofterm \
#       make judge PROVIDER=anthropic MODEL=claude-haiku-4-5-20251001 RUN=main PY=python
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*
COPY skillbridge/requirements.txt skillbridge/requirements.txt
RUN pip install --no-cache-dir -r skillbridge/requirements.txt
COPY . .
CMD ["make", "all", "PY=python"]
