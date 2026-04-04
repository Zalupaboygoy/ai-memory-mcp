FROM python:3.12-slim
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r -s /bin/false mcpuser && chown -R mcpuser:mcpuser /app
USER mcpuser
EXPOSE 8000
CMD ["python", "main.py"]
