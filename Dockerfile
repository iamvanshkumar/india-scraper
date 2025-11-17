# Use slim Python image
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies + unzip
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Install REAL Chrome 129 (stable, exists, works perfectly)
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/129.0.6668.89/linux64/chrome-linux64.zip \
    && unzip chrome-linux64.zip -d /opt/chrome \
    && rm chrome-linux64.zip \
    && ln -sf /opt/chrome/chrome-linux64/chrome /usr/bin/google-chrome \
    && google-chrome --version

# Install matching ChromeDriver 129
RUN wget -q https://storage.googleapis.com/chrome-for-testing-public/129.0.6668.89/linux64/chromedriver-linux64.zip \
    && unzip chromedriver-linux64.zip -d /opt/chromedriver \
    && rm chromedriver-linux64.zip \
    && chmod +x /opt/chromedriver/chromedriver-linux64/chromedriver \
    && ln -sf /opt/chromedriver/chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chromedriver --version

# Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your app
COPY app.py .

# Create dirs with proper permissions
RUN mkdir -p /app/filings /tmp && chmod -R 777 /app/filings /tmp

# Create a non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]