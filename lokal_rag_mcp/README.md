# Lokal-RAG MCP Server

**Model Context Protocol (MCP) server for Lokal-RAG with intelligent re-ranking.**

Give AI assistants like Claude Desktop direct access to your local knowledge base with two-stage search (Hybrid + Re-Ranking) for maximum precision.

## Features

- 🔍 **Two-Stage Search Pipeline**
  - Stage 1: Hybrid search (BM25 + Vector) for high recall
  - Stage 2: Cross-Encoder re-ranking for high precision
- 🎯 **Intelligent Re-Ranking** with jina-reranker-v2-base-multilingual
- 📝 **Notes Management** with vector search
- 💬 **Contextual Chat** with RAG and re-ranked context
- 🌐 **Multilingual** Russian/English support
- ⚡ **Apple Silicon Optimized** (M1/M2/M3/M4 with MPS acceleration)
- 🚀 **FastMCP 2.12+** (latest MCP protocol compliance)

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/ponyol/Lokal-RAG.git
cd Lokal-RAG/lokal_rag_mcp

# Install with re-ranking support
pip install -e ".[rerank]"

# Or with all optional dependencies
pip install -e ".[all]"
```

**Requirements:**
- Python 3.10+ (Python 3.14 recommended)
- Existing Lokal-RAG knowledge base

### Configuration

Create or update `~/.lokal-rag/settings.json`:

```json
{
  "llm_provider": "gemini",
  "gemini_api_key": "your-api-key",
  "gemini_model": "gemini-2.5-pro-preview-03-25",
  "vector_db_path": "./lokal_rag_db",
  "markdown_output_path": "./output_markdown",

  "rerank": {
    "enabled": true,
    "model": "jinaai/jina-reranker-v2-base-multilingual",
    "device": "auto",
    "default_top_k": 25,
    "default_top_n": 5,
    "batch_size": 16,
    "cache_model": true,
    "threshold": 0.0
  },

  "mcp": {
    "log_level": "INFO",
    "log_format": "json",
    "enable_metrics": true
  }
}
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "lokal-rag": {
      "command": "python",
      "args": [
        "-m",
        "lokal_rag_mcp.server"
      ],
      "env": {
        "PYTHONPATH": "/path/to/Lokal-RAG"
      }
    }
  }
}
```

**With custom settings:**

```json
{
  "mcpServers": {
    "lokal-rag": {
      "command": "python",
      "args": [
        "-m",
        "lokal_rag_mcp.server",
        "--settings", "/Users/yourname/.lokal-rag/settings.json",
        "--log-level", "INFO"
      ],
      "env": {
        "PYTHONPATH": "/path/to/Lokal-RAG"
      }
    }
  }
}
```

### Test the Server

```bash
# Test mode (health check)
python -m lokal_rag_mcp.server --test

# Disable re-ranking (for testing)
python -m lokal_rag_mcp.server --no-rerank --test

# Force CPU (for testing)
python -m lokal_rag_mcp.server --rerank-device cpu --test
```

Expected output:
```json
{
  "status": "healthy",
  "components": {
    "storage": {"status": "ok", "document_count": 42},
    "llm_provider": {"status": "ok", "provider": "gemini"},
    "reranker": {
      "status": "ok",
      "model": "jinaai/jina-reranker-v2-base-multilingual",
      "device": "mps",
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

## Usage

### From Claude Desktop

Once configured, you can use these tools directly in Claude Desktop:

#### Search with Re-Ranking

```
Use lokal_rag_search to find documents about "transformer architecture".
Enable re-ranking and return top 5 results.
```

Claude will call:
```python
lokal_rag_search(
    query="transformer architecture",
    mode="hybrid",
    initial_limit=25,
    rerank_top_n=5,
    enable_rerank=True
)
```

#### Chat with Context

```
Use lokal_rag_chat to answer: "What are the main optimization techniques
for neural networks mentioned in my documents?"
```

Claude will:
1. Search your knowledge base (with re-ranking)
2. Retrieve top 5 most relevant documents
3. Generate an answer using those documents as context

#### Create Notes

```
Use lokal_rag_create_note to create a note titled "Meeting Notes" with
content about our AI strategy discussion.
```

### Available Tools

| Tool | Description |
|------|-------------|
| `lokal_rag_search` | Universal search with re-ranking |
| `lokal_rag_get_document` | Get document by ID |
| `lokal_rag_list_documents` | List all documents |
| `lokal_rag_create_note` | Create new note |
| `lokal_rag_get_note` | Get note by ID |
| `lokal_rag_list_notes` | List all notes |
| `lokal_rag_update_note` | Update note (coming soon) |
| `lokal_rag_delete_note` | Delete note (coming soon) |
| `lokal_rag_chat` | Chat with RAG |
| `lokal_rag_chat_with_history` | Multi-turn chat |
| `lokal_rag_get_stats` | Get knowledge base stats |
| `lokal_rag_health_check` | Health check |

See [LOKAL_RAG_MCP_SPECIFICATION_V2.md](../LOKAL_RAG_MCP_SPECIFICATION_V2.md) for full API reference.

## Re-Ranking Deep Dive

### Why Re-Ranking?

Re-ranking is a **second-stage refinement** that dramatically improves search precision:

```
User Query → Stage 1 (Hybrid Search) → 25 candidates → Stage 2 (Re-Ranking) → Top 5 best
```

| Aspect | Stage 1 (Hybrid) | Stage 2 (Re-Ranker) |
|--------|-----------------|---------------------|
| **Speed** | Fast (~50ms) | Slower (~150ms) |
| **Method** | Independent embeddings | Reads query + doc together |
| **Accuracy** | Good recall | Excellent precision |
| **Scope** | Millions of docs | Small candidate set |

**Result:** Top 5 results are the absolute best, not just "good enough."

### Performance Benchmarks

| Device | Re-rank 25 docs | Re-rank 50 docs | Model Load |
|--------|----------------|----------------|------------|
| **M1 (8GB)** | ~200ms | ~400ms | ~2s |
| **M2 Pro (16GB)** | ~150ms | ~300ms | ~1.5s |
| **M3 Max (32GB)** | ~100ms | ~200ms | ~1s |
| **CPU (fallback)** | ~800ms | ~1600ms | ~3s |

**Memory:** ~600MB for model + ~200MB per batch

### Configuration Options

```json
{
  "rerank": {
    "enabled": true,                              // Enable/disable globally
    "model": "jinaai/jina-reranker-v2-base-multilingual",  // Model name
    "device": "auto",                            // "auto", "cpu", "mps", "cuda"
    "default_top_k": 25,                         // Stage 1 candidates
    "default_top_n": 5,                          // Stage 2 results
    "batch_size": 16,                            // Batch size
    "cache_model": true,                         // Keep in memory
    "threshold": 0.0                             // Min score (0-1)
  }
}
```

## Apple Silicon Optimization

### Automatic Detection

The server automatically detects and uses Apple Silicon (M1/M2/M3/M4) with MPS backend:

```python
# Automatic
device = "auto"  # → "mps" on Apple Silicon

# Manual
device = "mps"   # Force Apple Silicon GPU
device = "cpu"   # Force CPU (for testing)
```

### Optimization Tips

**For M1/M2/M3 (8GB+):**
```json
{
  "rerank": {
    "device": "mps",
    "batch_size": 16,
    "cache_model": true
  }
}
```

**For Low RAM (<8GB):**
```json
{
  "rerank": {
    "device": "cpu",
    "batch_size": 8,
    "cache_model": false
  }
}
```

**For Maximum Speed (disable re-ranking):**
```json
{
  "rerank": {
    "enabled": false
  }
}
```

## Development

### Running Locally

```bash
# Development mode
python -m lokal_rag_mcp.server

# With debug logging
python -m lokal_rag_mcp.server --log-level DEBUG

# Test re-ranker performance
python -c "
from lokal_rag_mcp.reranker import ReRanker
from lokal_rag_mcp.config import ReRankConfig

config = ReRankConfig(device='auto')
reranker = ReRanker(config)
metrics = reranker.test_latency(25)
print(metrics)
"
```

### Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# With coverage
pytest --cov=lokal_rag_mcp --cov-report=html

# Run specific test
pytest tests/test_reranker.py::test_reranker_basic
```

### Code Quality

```bash
# Format with black
black lokal_rag_mcp/

# Lint with ruff
ruff check lokal_rag_mcp/

# Type check with mypy
mypy lokal_rag_mcp/
```

## Troubleshooting

### Re-ranker Not Loading

**Problem:** Re-ranker fails to load or uses CPU instead of MPS.

**Solutions:**

1. **Install torch with MPS support:**
   ```bash
   pip install torch>=2.5.0
   ```

2. **Check MPS availability:**
   ```python
   import torch
   print(torch.backends.mps.is_available())  # Should be True
   ```

3. **Force CPU for testing:**
   ```bash
   python -m lokal_rag_mcp.server --rerank-device cpu --test
   ```

### Slow Performance

**Problem:** Re-ranking is slow (>500ms for 25 docs on M1).

**Solutions:**

1. **Check device:**
   ```bash
   python -m lokal_rag_mcp.server --test
   # Look at: components.reranker.device
   ```

2. **Reduce batch size:**
   ```json
   {"rerank": {"batch_size": 8}}
   ```

3. **Disable re-ranking for simple queries:**
   ```python
   lokal_rag_search(query="...", enable_rerank=False)
   ```

### Out of Memory

**Problem:** Server crashes with OOM on 8GB Mac.

**Solutions:**

1. **Use CPU:**
   ```json
   {"rerank": {"device": "cpu", "cache_model": false}}
   ```

2. **Reduce initial_limit:**
   ```python
   lokal_rag_search(query="...", initial_limit=15)
   ```

3. **Close other apps** to free RAM.

### Claude Desktop Not Seeing Tools

**Problem:** Tools don't appear in Claude Desktop.

**Solutions:**

1. **Check config path:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Verify PYTHONPATH:**
   ```json
   {
     "env": {
       "PYTHONPATH": "/full/path/to/Lokal-RAG"
     }
   }
   ```

3. **Restart Claude Desktop** after changing config.

4. **Check logs:** Look for errors in Claude Desktop developer console.

## FAQ

**Q: Do I need to run the Lokal-RAG GUI app?**

A: No! The MCP server works standalone. It reads from the same vector database.

**Q: Can I use this without re-ranking?**

A: Yes! Set `"rerank": {"enabled": false}` or use `--no-rerank` flag.

**Q: What languages are supported?**

A: jina-reranker-v2-base-multilingual supports 100+ languages, including Russian and English.

**Q: How much memory does this use?**

A: ~100MB base + ~600MB for re-ranker model + ~200MB during re-ranking = ~900MB total.

**Q: Can I use a different re-ranker model?**

A: Yes! Set `"rerank": {"model": "your-model-name"}`. Must be a CrossEncoder-compatible model on HuggingFace.

**Q: Does this work on Linux/Windows?**

A: Yes! Apple Silicon optimization is automatic, but everything works on Linux (CUDA/CPU) and Windows (CPU).

## Contributing

Contributions welcome! See [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

Same as Lokal-RAG project (MIT).

## Links

- [Lokal-RAG GitHub](https://github.com/ponyol/Lokal-RAG)
- [MCP Specification v2.0](../LOKAL_RAG_MCP_SPECIFICATION_V2.md)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [jina-reranker-v2 Model](https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual)

## Changelog

### v2.0.0 (2025-11-18)

- ✨ Initial release with re-ranking support
- ⚡ Apple Silicon (M1/M2/M3/M4) optimization
- 🔍 Two-stage search pipeline
- 💬 RAG-powered chat with re-ranked context
- 📝 Notes management
- 🏥 Health check with re-ranker diagnostics
- 🚀 FastMCP 2.12+ integration
