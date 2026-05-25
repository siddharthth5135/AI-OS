#!/bin/bash
echo "=== AI OS Health Check ==="
curl -s http://localhost:8000/health | python3 -m json.tool
echo ""
echo "=== Container Status ==="
docker compose ps
echo ""
echo "=== Recent Errors ==="
docker compose logs fastapi --since 10m | grep -i error | tail -20
