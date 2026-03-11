#!/bin/bash

echo "🔍 Verifying Camunda 8 Setup..."
echo ""

# Check Elasticsearch
echo -n "Elasticsearch (http://localhost:9200): "
if curl -s -f http://localhost:9200/_cluster/health > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not accessible"
fi

# Check Zeebe Gateway
echo -n "Zeebe Gateway (localhost:26500): "
if nc -z localhost 26500 2>/dev/null; then
    echo "✅ Running"
else
    echo "❌ Not accessible"
fi

# Check Operate
echo -n "Operate (http://localhost:8081): "
if curl -s -f http://localhost:8081 > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not accessible"
fi

# Check Tasklist
echo -n "Tasklist (http://localhost:8082): "
if curl -s -f http://localhost:8082 > /dev/null 2>&1; then
    echo "✅ Running"
else
    echo "❌ Not accessible"
fi

echo ""
echo "📊 Docker Container Status:"
docker-compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🎉 Setup verification complete!"
echo ""
echo "Access the services:"
echo "  • Operate:  http://localhost:8081 (demo/demo)"
echo "  • Tasklist: http://localhost:8082 (demo/demo)"
echo ""
