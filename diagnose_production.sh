#!/bin/bash

echo "🔍 Diagnosing Production Deployment Issues"
echo "========================================="

echo "1. Checking Docker services status..."
docker-compose ps

echo ""
echo "2. Checking application logs..."
echo "--- FastAPI App Logs ---"
docker-compose logs --tail=20 app

echo ""
echo "--- Nginx Logs ---"
docker-compose logs --tail=20 nginx

echo ""
echo "--- Redis Logs ---"
docker-compose logs --tail=10 redis

echo ""
echo "--- PostgreSQL Logs ---"
docker-compose logs --tail=10 postgres

echo ""
echo "3. Testing direct application access..."
echo "Testing FastAPI health endpoint directly..."
curl -v http://localhost:8000/health 2>&1 || echo "❌ FastAPI not responding on port 8000"

echo ""
echo "4. Checking port bindings..."
netstat -tuln | grep -E "(8000|80|6379|5432)"

echo ""
echo "5. Testing database connections..."
echo "Testing Redis..."
docker-compose exec -T redis redis-cli ping 2>&1 || echo "❌ Redis connection failed"

echo ""
echo "Testing PostgreSQL..."
docker-compose exec -T postgres pg_isready -U campaign_user 2>&1 || echo "❌ PostgreSQL connection failed"

echo ""
echo "6. Checking container resource usage..."
docker stats --no-stream

echo ""
echo "7. Checking system resources..."
echo "Memory usage:"
free -h

echo ""
echo "Disk space:"
df -h

echo ""
echo "System load:"
uptime

echo ""
echo "8. Testing internal network connectivity..."
docker-compose exec app ping -c 2 redis || echo "❌ App cannot reach Redis"
docker-compose exec app ping -c 2 postgres || echo "❌ App cannot reach PostgreSQL"

echo ""
echo "🔧 Quick fixes to try:"
echo "1. Restart services: docker-compose restart"
echo "2. Rebuild containers: docker-compose up -d --build"
echo "3. Check logs: docker-compose logs -f app"
echo "4. Reset everything: docker-compose down && docker-compose up -d --build"