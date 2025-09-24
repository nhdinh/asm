#!/bin/bash

# Deploy script for Asset Management API

set -e

echo "🚀 Deploying Asset Management API..."

# Check if docker and docker-compose are installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data logs nginx/ssl

# Copy environment file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOF
JWT_SECRET_KEY=$(openssl rand -hex 32)
DATABASE_URL=sqlite:///data/asset_management.db
FLASK_ENV=production
PORT=5000
EOF
    echo "✅ .env file created with random JWT secret key"
fi

# Build and start services
echo "🔨 Building and starting services..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Check if API is healthy
echo "🏥 Checking API health..."
max_retries=30
retry_count=0

while [ $retry_count -lt $max_retries ]; do
    if curl -f http://localhost:5000/api/health > /dev/null 2>&1; then
        echo "✅ API is healthy!"
        break
    fi
    retry_count=$((retry_count + 1))
    echo "⏳ Waiting for API... (${retry_count}/${max_retries})"
    sleep 2
done

if [ $retry_count -eq $max_retries ]; then
    echo "❌ API health check failed!"
    echo "📋 Checking logs..."
    docker-compose logs asset-management-api
    exit 1
fi

# Show status
echo "📊 Service status:"
docker-compose ps

echo ""
echo "🎉 Deployment completed successfully!"
echo "🌐 API is available at: http://localhost:5000"
echo "🏥 Health check: http://localhost:5000/api/health"
echo "📋 View logs: docker-compose logs -f"
echo ""
echo "📋 Default credentials:"
echo "   Username: admin"
echo "   Password: admin123"