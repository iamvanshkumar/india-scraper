# Deployment Guide

## Local Testing

```bash
# Build and run with docker-compose
docker-compose up --build

# Access at http://localhost:8501
# PDFs will be saved to ./filings/ on your host machine
```

## Server Deployment

### Option 1: Using docker-compose (Recommended)

```bash
# On your server
git clone <your-repo>
cd <your-repo>

# Create filings directory with proper permissions
mkdir -p filings
chmod 777 filings

# Build and run
docker-compose up -d --build

# Check logs
docker-compose logs -f

# Stop
docker-compose down
```

### Option 2: Using docker run

```bash
# Build
docker build -t companies-scraper .

# Run with volume mount
docker run -d \
  -p 8501:8501 \
  -v $(pwd)/filings:/app/filings \
  --name scraper \
  companies-scraper

# Check logs
docker logs -f scraper

# Stop
docker stop scraper
docker rm scraper
```

## Troubleshooting

### PDFs not saving?

1. Check if directory exists and is writable:
```bash
ls -la filings/
```

2. Check container logs:
```bash
docker-compose logs -f
```

3. Verify volume mount:
```bash
docker inspect <container-id> | grep Mounts -A 10
```

4. Check permissions inside container:
```bash
docker exec -it <container-id> ls -la /app/filings
```

### Permission denied errors?

```bash
# On host machine
chmod -R 777 filings/

# Or use specific user ID
chown -R 1000:1000 filings/
```
