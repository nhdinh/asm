FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create application directories
# RUN mkdir -p /app/src
# RUN mkdir -p /app/templates
# RUN mkdir -p /app/shared

# Create logs directory
# RUN mkdir -p /app/logs

# Expose port
EXPOSE 3000
# EXPOSE 5679

# Set environment variables
ENV FLASK_APP=src/frontend.py
ENV FLASK_ENV=production
ENV API_BASE_URL=http://backend:5000

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--reload", "--workers", "2", "--timeout", "120", "src.frontend:app"]