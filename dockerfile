FROM python:3.9-slim

WORKDIR /app

RUN mkdir -p /app/input /app/output

RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN chmod +x main.py

CMD ["python3", "main.py", "/app/input", "--outdir", "/app/output"]
