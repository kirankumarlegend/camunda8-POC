# Camunda 8 POC - Local Development Setup

This repository contains a local development environment for Camunda 8 using Docker Compose via Rancher Desktop.

## Overview

This setup includes the following Camunda 8 components:

- **Zeebe** - The workflow engine that executes BPMN processes
- **Operate** - Web UI for monitoring and managing workflow instances
- **Tasklist** - Web UI for working with user tasks
- **Connectors** - Pre-built integrations for common services
- **Elasticsearch** - Data storage for Operate and Tasklist

## Prerequisites

- ✅ Rancher Desktop installed and running in dockerd (moby) mode
- ✅ Docker Compose available (comes with Rancher Desktop)

## Quick Start

### 1. Start Camunda 8

```bash
docker-compose up -d
```

This will start all services in the background. Initial startup may take 2-3 minutes.

### 2. Check Service Status

```bash
docker-compose ps
```

All services should show as "healthy" or "running" after a few minutes.

### 3. View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f zeebe
docker-compose logs -f operate
```

## Access URLs

Once all services are running, you can access:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Operate** (Workflow Monitoring) | http://localhost:8081 | demo / demo |
| **Tasklist** (User Tasks) | http://localhost:8082 | demo / demo |
| **Connectors** | http://localhost:8085 | - |
| **Zeebe Gateway** | localhost:26500 | - |
| **Elasticsearch** | http://localhost:9200 | - |

## Common Operations

### Stop All Services

```bash
docker-compose down
```

### Stop and Remove All Data (Clean Restart)

```bash
docker-compose down -v
```

⚠️ This will delete all workflow instances and data!

### Restart a Specific Service

```bash
docker-compose restart zeebe
docker-compose restart operate
```

### View Resource Usage

```bash
docker stats
```

## Creating Your First Workflow

### Option 1: Using Camunda Modeler (Recommended)

1. Download [Camunda Modeler](https://camunda.com/download/modeler/)
2. Create a BPMN diagram
3. Deploy to `localhost:26500`

### Option 2: Using Operate Web UI

1. Go to http://localhost:8081
2. Login with demo/demo
3. Use the built-in examples or upload a BPMN file

### Option 3: Using zbctl CLI

Install zbctl:
```bash
brew install zbctl
```

Deploy a workflow:
```bash
zbctl deploy my-workflow.bpmn --address localhost:26500 --insecure
```

Start a workflow instance:
```bash
zbctl create instance my-process --address localhost:26500 --insecure
```

## Development Tips

### Resource Requirements

- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores

Adjust in Rancher Desktop preferences if needed.

### Elasticsearch Memory

If Elasticsearch fails to start, you may need to increase memory:
- Edit `docker-compose.yml`
- Modify `ES_JAVA_OPTS=-Xms512m -Xmx512m` to higher values (e.g., `-Xms1g -Xmx1g`)

### Network Issues (VPN)

If you're on Walmart VPN and downloads fail:
1. Disconnect from VPN
2. Run `docker-compose pull` to download images
3. Reconnect to VPN
4. Run `docker-compose up -d`

## Troubleshooting

### Services Not Starting

Check logs for the specific service:
```bash
docker-compose logs elasticsearch
docker-compose logs zeebe
```

### Port Conflicts

If ports are already in use, modify the port mappings in `docker-compose.yml`:
```yaml
ports:
  - "8081:8080"  # Change 8081 to another port
```

### Health Check Failures

Wait a bit longer - services can take 2-3 minutes to become healthy. Check status:
```bash
docker-compose ps
```

### Reset Everything

Complete reset (removes all data):
```bash
docker-compose down -v
docker-compose up -d
```

## Architecture

```
┌─────────────────────────────────────────────┐
│           Camunda 8 Platform                │
├─────────────────────────────────────────────┤
│                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Operate  │  │Tasklist  │  │Connectors│ │
│  │  :8081   │  │  :8082   │  │  :8085   │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │             │             │        │
│       └─────────────┼─────────────┘        │
│                     │                      │
│              ┌──────▼──────┐              │
│              │    Zeebe    │              │
│              │   Gateway   │              │
│              │   :26500    │              │
│              └──────┬──────┘              │
│                     │                      │
│              ┌──────▼──────┐              │
│              │Elasticsearch│              │
│              │    :9200    │              │
│              └─────────────┘              │
└─────────────────────────────────────────────┘
```

## Next Steps

1. **Learn BPMN**: Familiarize yourself with BPMN 2.0 notation
2. **Explore Operate**: Navigate through the web UI to understand workflow monitoring
3. **Create Workflows**: Build your first process using Camunda Modeler
4. **Test Connectors**: Try integrating with external systems
5. **Read Documentation**: Visit [Camunda 8 Docs](https://docs.camunda.io/)

## Useful Resources

- [Camunda 8 Documentation](https://docs.camunda.io/)
- [BPMN Tutorial](https://camunda.com/bpmn/)
- [Camunda Community](https://forum.camunda.io/)
- [Example Workflows](https://github.com/camunda-community-hub/camunda-8-examples)

## Version Information

- Camunda Platform: 8.5.0
- Elasticsearch: 8.9.0
- Docker Compose: v2.33.0

## Support

For issues with this setup, check:
1. Docker logs: `docker-compose logs`
2. Service health: `docker-compose ps`
3. Rancher Desktop is running and has enough resources

---

**Ready to build workflows!** 🚀
