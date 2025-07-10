FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl git ca-certificates build-essential && \
    curl -s https://go.dev/VERSION?m=text | xargs -I {} curl -LO https://go.dev/dl/{}.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go*.linux-amd64.tar.gz && \
    rm go*.linux-amd64.tar.gz

# Set Go environment
ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"
ENV GOPATH="/root/go"

# Install subfinder
RUN go install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest && \
    cp /root/go/bin/subfinder /usr/local/bin/

# Clean up unnecessary packages
RUN apt-get remove --purge -y curl git build-essential && \
    apt-get autoremove -y && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the bot code
COPY . .

# Set environment variable defaults (overridden by Koyeb or Docker run)
ENV API_ID=0
ENV API_HASH=""
ENV BOT_TOKEN=""
ENV LOGS_CHANNEL=0

# Run the bot
CMD ["python", "main.py"]
