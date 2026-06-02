# Docker Development Environment

This directory contains Docker Compose configurations for DeerFlow deployment.

## Quick Start

```bash
# Start services (always use --env-file to ensure .env is loaded)
docker-compose -f docker-compose-dev.yaml --env-file ../.env up -d

# Stop services
docker-compose -f docker-compose-dev.yaml --env-file ../.env down
```

## Configuration

### Environment Variables (.env)

**Critical for Windows**: The following variables must be set in `.env`:

```env
# Container internal paths (used inside containers)
DEER_FLOW_HOME=/app/backend/.deer-flow
DEER_FLOW_CONFIG_PATH=/app/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/app/extensions_config.json

# Host paths (Windows paths for Docker bind mounts)
DEER_FLOW_ROOT=/c/Users/wing/Documents/Wing/emto/2026/2026.3/DeerFlow/deer-flow
DEER_FLOW_REPO_ROOT=/c/Users/wing/Documents/Wing/emto/2026/2026.3/DeerFlow/deer-flow
HOME=/c/Users/wing

# ADS 统一认证
ADS_BASE_URL=http://ads:8080
ADS_MCP_CONFIG_PATH=/home/wing/.hermes/mcp-servers/ads-mcp/.ads-mcp/config.json
```

**Why /c/ path format?** Docker Desktop on Windows uses MSYS2 paths. Always use `/c/Users/...` instead of `C:\Users\...` or `C:/Users/...`.

## Common Issues

### 502 Bad Gateway / IsADirectoryError

**Symptom**: Gateway or LangGraph fails to start with:
```
IsADirectoryError: [Errno 21] Is a directory: '/app/backend/config.yaml'
RuntimeError: Failed to load configuration during gateway startup
```

**Cause**: Environment variables not properly loaded. Docker Compose uses default values instead of .env values.

**Solution**:
1. Always use `--env-file ../.env` when running docker-compose commands
2. Ensure `HOME` and `DEER_FLOW_ROOT` are set in .env (Windows does not set HOME by default)
3. Verify config paths in .env use `/c/...` format, not Windows `C:\...` format

**Check**:
```bash
# Verify .env is being loaded correctly
docker-compose -f docker-compose-dev.yaml --env-file ../.env config | Select-String DEER_FLOW_CONFIG
```

### Services Start But 502 on API Calls

**Cause**: Config file mounted at `/app/config.yaml` but `DEER_FLOW_CONFIG_PATH` environment variable still points to `/app/backend/config.yaml`.

**Solution**: Set `DEER_FLOW_CONFIG_PATH=/app/config.yaml` (container internal path) in .env.

## Services

- **nginx** (port 2026): Reverse proxy
- **frontend** (port 3000): Next.js dev server
- **gateway** (port 8001): FastAPI Gateway
- **langgraph** (port 2024): LangGraph server

## 零侵入扩展原则

遵循根目录 `CLAUDE.md` 的 ⚠️ 铁律：零侵入扩展原则。如对 Docker 配置（`docker-compose*.yaml`、`Dockerfile`）的修改涉及扩展对接：

1. 用 try/except 包裹扩展模块的 import
2. 在 `docs/patches/docker.md` 记录改动

详见 `@./docs/零侵入扩展方法论.md`
