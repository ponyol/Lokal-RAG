# Lokal-RAG MCP Server - Пошаговая настройка

## 🎯 Для macOS (M1/M2/M3/M4)

### Шаг 1: Установка зависимостей

```bash
# Перейти в проект
cd /Users/yourname/Lokal-RAG

# Активировать venv (если уже создан)
source venv/bin/activate

# Или создать новый venv
python3.14 -m venv venv
source venv/bin/activate

# Установить MCP сервер с re-ranking
cd lokal_rag_mcp
pip install -e ".[rerank]"

# Проверить установку
pip list | grep -E "(fastmcp|sentence-transformers|chromadb)"
```

**Ожидаемый вывод:**
```
chromadb                    0.5.x
fastmcp                     2.12.x
sentence-transformers       3.3.x
```

---

### Шаг 2: Настройка конфигурации

#### 2.1 Создайте настройки сервера

```bash
# Создать директорию для настроек
mkdir -p ~/.lokal-rag

# Создать настройки (вариант 1 - вручную)
nano ~/.lokal-rag/settings.json
```

**Содержимое `~/.lokal-rag/settings.json`:**

```json
{
  "_comment": "Lokal-RAG MCP Server Settings",

  "llm_provider": "gemini",
  "gemini_api_key": "ВАШ_API_КЛЮЧ_ЗДЕСЬ",
  "gemini_model": "gemini-2.5-pro-preview-03-25",

  "vector_db_path": "/Users/yourname/Lokal-RAG/lokal_rag_db",
  "markdown_output_path": "/Users/yourname/Lokal-RAG/output_markdown",
  "notes_dir": "/Users/yourname/Lokal-RAG/notes",
  "database_language": "en",

  "rerank": {
    "enabled": true,
    "model": "jinaai/jina-reranker-v2-base-multilingual",
    "device": "auto",
    "default_top_k": 25,
    "default_top_n": 5,
    "batch_size": 16,
    "cache_model": true
  },

  "mcp": {
    "log_level": "INFO",
    "log_format": "json"
  }
}
```

**Или скопировать пример:**

```bash
cp /Users/yourname/Lokal-RAG/lokal_rag_mcp/examples/settings.example.json ~/.lokal-rag/settings.json

# Отредактировать
nano ~/.lokal-rag/settings.json
# Замените:
# - "your-gemini-api-key-here" → ваш API ключ
# - "/Users/yourname" → ваш реальный путь
```

**ВАЖНО:** Замените пути на **абсолютные**, например:
```json
"vector_db_path": "/Users/ponyol/Lokal-RAG/lokal_rag_db"
```

---

### Шаг 3: Тестирование сервера

```bash
# Активировать venv
cd /Users/yourname/Lokal-RAG
source venv/bin/activate

# Запустить тест
python -m lokal_rag_mcp.server --test
```

**Ожидаемый вывод (успех):**

```json
{
  "status": "healthy",
  "components": {
    "storage": {
      "status": "ok",
      "document_count": 42
    },
    "llm_provider": {
      "status": "ok",
      "provider": "gemini"
    },
    "reranker": {
      "status": "ok",
      "model": "jinaai/jina-reranker-v2-base-multilingual",
      "device": "mps",
      "memory_mb": "~600",
      "test_latency_ms": 156
    }
  },
  "platform": {
    "system": "Darwin",
    "processor": "arm64",
    "apple_silicon": true,
    "mps_available": true
  }
}

✅ Server is healthy
```

**Если ошибка:**

1. **"Storage service not initialized"** → Проверьте пути в settings.json
2. **"Custom code warning"** → Это нормально, код обновлен (см. ниже)
3. **"No such file or directory"** → Убедитесь, что база данных существует

---

### Шаг 4: Настройка Claude Desktop

#### 4.1 Найдите конфигурацию Claude Desktop

```bash
# macOS
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Linux
nano ~/.config/Claude/claude_desktop_config.json

# Windows
notepad %APPDATA%\Claude\claude_desktop_config.json
```

#### 4.2 Вариант A: Через прямой путь к Python (рекомендуется)

```json
{
  "mcpServers": {
    "lokal-rag": {
      "command": "/Users/yourname/Lokal-RAG/venv/bin/python",
      "args": [
        "-m",
        "lokal_rag_mcp.server"
      ],
      "env": {
        "PYTHONPATH": "/Users/yourname/Lokal-RAG"
      }
    }
  }
}
```

**Найти путь к Python из venv:**

```bash
cd /Users/yourname/Lokal-RAG
source venv/bin/activate
which python
# Вывод: /Users/yourname/Lokal-RAG/venv/bin/python
```

#### 4.3 Вариант B: Через shell script (для сложных настроек)

**1. Создайте скрипт:**

```bash
cd /Users/yourname/Lokal-RAG/lokal_rag_mcp

# Создать скрипт
cat > start_mcp_server.sh <<'EOF'
#!/bin/bash
cd /Users/yourname/Lokal-RAG
source venv/bin/activate
exec python -m lokal_rag_mcp.server "$@"
EOF

# Сделать executable
chmod +x start_mcp_server.sh
```

**ВАЖНО:** Замените `/Users/yourname` на ваш реальный путь!

**2. Тест скрипта:**

```bash
./start_mcp_server.sh --test
```

**3. Claude Desktop config:**

```json
{
  "mcpServers": {
    "lokal-rag": {
      "command": "/Users/yourname/Lokal-RAG/lokal_rag_mcp/start_mcp_server.sh"
    }
  }
}
```

---

### Шаг 5: Перезапуск Claude Desktop

```bash
# Закрыть Claude Desktop полностью (Cmd+Q)
# Открыть заново
```

**Проверка в Claude Desktop:**

Откройте новый чат и наберите:
```
Use lokal_rag_health_check to check the server status
```

Claude должен ответить результатами health check.

---

## 🔍 Откуда сервер берет путь к базе?

### Порядок загрузки конфигурации:

1. **Флаг `--settings` (если указан):**
   ```bash
   python -m lokal_rag_mcp.server --settings /custom/path/settings.json
   ```

2. **Иначе домашняя директория (по умолчанию):**
   ```
   ~/.lokal-rag/settings.json
   ```

### Что читается из settings.json:

```json
{
  "vector_db_path": "/Users/yourname/Lokal-RAG/lokal_rag_db",
  "markdown_output_path": "/Users/yourname/Lokal-RAG/output_markdown",
  "notes_dir": "/Users/yourname/Lokal-RAG/notes"
}
```

**ВАЖНО:** Используйте **абсолютные пути**, не относительные!

❌ Неправильно:
```json
"vector_db_path": "./lokal_rag_db"
```

✅ Правильно:
```json
"vector_db_path": "/Users/ponyol/Lokal-RAG/lokal_rag_db"
```

---

## 📊 Диагностика проблем

### Проблема 1: venv не активируется в Claude Desktop

**Симптом:** Ошибка "No module named 'fastmcp'"

**Решение:** Используйте **абсолютный путь** к Python из venv:

```json
{
  "command": "/Users/yourname/Lokal-RAG/venv/bin/python"
}
```

**Не используйте:**
```json
{
  "command": "python"  // ❌ Это будет системный Python!
}
```

---

### Проблема 2: База данных не найдена

**Симптом:** "Storage service not initialized" или "document_count: 0"

**Решение:**

1. **Проверьте путь к базе:**
   ```bash
   ls -la /Users/yourname/Lokal-RAG/lokal_rag_db
   # Должна быть директория с файлами ChromaDB
   ```

2. **Убедитесь, что база создана:**
   ```bash
   # Запустите основное приложение Lokal-RAG
   cd /Users/yourname/Lokal-RAG
   source venv/bin/activate
   python main.py

   # Обработайте хотя бы один PDF, чтобы создать базу
   ```

3. **Проверьте настройки:**
   ```bash
   cat ~/.lokal-rag/settings.json | grep vector_db_path
   ```

---

### Проблема 3: Custom code warning

**Симптом:**
```
ValueError: The repository contains custom code which must be executed...
```

**Решение:**

Это уже **исправлено** в коде (commit 0d1f44a). Обновитесь:

```bash
cd /Users/yourname/Lokal-RAG
git pull
source venv/bin/activate
pip install -e ".[rerank]" --upgrade
```

Проверьте:
```bash
python -m lokal_rag_mcp.server --test
```

---

### Проблема 4: Медленная работа

**Симптом:** Re-ranking занимает >500ms на M1/M2

**Решение:**

1. **Проверьте device:**
   ```bash
   python -m lokal_rag_mcp.server --test | grep device
   # Должно быть: "device": "mps"
   ```

2. **Если используется CPU:**
   ```bash
   # Проверьте torch
   python -c "import torch; print(torch.backends.mps.is_available())"
   # Должно быть: True

   # Если False, переустановите torch
   pip install torch>=2.5.0 --upgrade
   ```

3. **Уменьшите batch_size для экономии памяти:**
   ```json
   {
     "rerank": {
       "batch_size": 8  // Вместо 16
     }
   }
   ```

---

## 🚀 Быстрая настройка (все в одном)

```bash
# 1. Перейти в проект
cd /Users/yourname/Lokal-RAG

# 2. Создать/активировать venv
python3.14 -m venv venv
source venv/bin/activate

# 3. Установить MCP сервер
cd lokal_rag_mcp
pip install -e ".[rerank]"

# 4. Создать настройки
mkdir -p ~/.lokal-rag
cp examples/settings.example.json ~/.lokal-rag/settings.json

# 5. Отредактировать настройки (ВАЖНО!)
nano ~/.lokal-rag/settings.json
# Замените:
# - API ключи
# - Пути на абсолютные (/Users/yourname/...)

# 6. Протестировать
python -m lokal_rag_mcp.server --test

# 7. Настроить Claude Desktop
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
# Вставить конфиг (см. выше, Вариант A)

# 8. Перезапустить Claude Desktop
# Cmd+Q → Открыть заново
```

---

## 📞 Нужна помощь?

Если что-то не работает:

1. **Покажите вывод теста:**
   ```bash
   python -m lokal_rag_mcp.server --test
   ```

2. **Покажите настройки:**
   ```bash
   cat ~/.lokal-rag/settings.json
   ```

3. **Покажите Claude Desktop config:**
   ```bash
   cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

Готов помочь! 🎯
