FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git build-essential ca-certificates && \
    curl -s https://go.dev/dl/ | grep linux-amd64.tar.gz | head -n 1 | \
    grep -oP 'https://go.dev/dl/go[\d.]+.linux-amd64.tar.gz' | \
    xargs curl -LO && \
    tar -C /usr/local -xzf go*.linux-amd64.tar.gz && \
    rm go*.linux-amd64.tar.gz && \
    export PATH=$PATH:/usr/local/go/bin && \
    /usr/local/go/bin/go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    cp /root/go/bin/subfinder /usr/local/bin/ && \
    apt-get remove --purge -y curl git build-essential && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /root/go /usr/local/go/pkg

# Set work directory
WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Environment defaults (overridden in production)
ENV API_ID=0
ENV API_HASH=""
ENV BOT_TOKEN=""
ENV LOGS_CHANNEL=0

CMD ["python", "main.py"]