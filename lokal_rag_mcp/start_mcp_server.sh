#!/bin/bash
# MCP Server Launcher for Claude Desktop
# This script activates venv and starts the MCP server

# Путь к проекту (измените на свой)
PROJECT_DIR="/Users/yourname/Lokal-RAG"

# Активируем venv
cd "$PROJECT_DIR"
source venv/bin/activate

# Запускаем сервер
exec python -m lokal_rag_mcp.server "$@"
