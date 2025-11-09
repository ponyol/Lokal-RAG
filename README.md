# Lokal-RAG

A local-first desktop application for building a private RAG (Retrieval-Augmented Generation) knowledge base from PDF documents.

## Features

- 📄 **PDF Ingestion**: Convert PDF files to high-quality Markdown using marker-pdf
- 🌐 **Web Article Ingestion**: Fetch and extract content from web articles (Medium, blogs, news sites)
- 🔐 **Authenticated Access**: Use your browser cookies to access paywalled content (Medium, etc.)
- 🌍 **Translation**: Optional translation to Russian using local LLM
- 🏷️ **Auto-tagging**: Automatic content categorization based on subject matter
- 💾 **Local Storage**: All data stays on your machine - no cloud required
- 💬 **Chat Interface**: Query your knowledge base using natural language
- 🔒 **Privacy-First**: Uses local Ollama instance for all AI operations

## Architecture

The application follows a clean 4-layer architecture:
- **View**: CustomTkinter GUI
- **Controller**: State management and event coordination
- **Services**: Pure functional business logic
- **Storage**: Vector database and file operations

## Prerequisites

- Python 3.11 or 3.12
- [Ollama](https://ollama.ai/) installed and running locally
- At least 8GB RAM recommended (for running Qwen2.5-7B model)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd Lokal-RAG
```

### 2. Create virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
# Install core dependencies
pip install -r requirements.txt

# Install marker-pdf (separate due to heavy ML dependencies)
python setup_marker.py
```

### 4. Download Ollama model

```bash
ollama pull qwen2.5:7b-instruct
```

## Usage

### 1. Start Ollama

Ensure Ollama is running on `http://localhost:11434`:

```bash
ollama serve
```

### 2. Launch the application

```bash
python main.py
```

### 3. Ingest Content

**Option A: PDF Documents**

1. Go to the "Ingestion" tab
2. Select "📄 PDF Files (from folder)"
3. Click "Select Folder" and choose a directory containing PDF files
4. (Optional) Enable "Translate to Russian"
5. (Optional) Enable "Auto-tag content"
6. Click "Start Processing"
7. Monitor the log for progress

**Option B: Web Articles**

1. Go to the "Ingestion" tab
2. Select "🌐 Web Articles (URLs)"
3. Enter URLs in the text box (one per line)
4. (Optional) Enable "Use browser cookies for authentication" (for Medium, paywalled sites)
5. (Optional) Enable "Translate to Russian"
6. (Optional) Enable "Auto-tag content"
7. Click "Start Processing"
8. Monitor the log for progress

**Example URLs:**
```
https://medium.com/@username/article-title
https://blog.example.com/post/article
https://news.ycombinator.com/item?id=12345
```

**Note on Authentication:**
- For paywalled sites (Medium, etc.), make sure you're logged in to your browser first
- The app will use your browser's cookies automatically
- Works with Chrome, Firefox, Safari, Edge
- No need to enter passwords - uses your existing session

### 4. Chat with Your Knowledge Base

1. Go to the "Chat" tab
2. Type your question in the input field
3. Press Enter or click "Send"
4. The assistant will respond based on your ingested documents

## Configuration

Edit `app_config.py` to customize:

### Core Settings
- **Ollama URL and model**: Change LLM endpoint or model
- **Embedding model**: Choose different HuggingFace embedding model
- **Vector database path**: Location for ChromaDB storage
- **Output directory**: Where to save processed Markdown files
- **Chunk size and overlap**: Text splitting parameters for RAG

### Web Scraping Settings

```python
# In app_config.py
WEB_USE_BROWSER_COOKIES: bool = True  # Default: True
WEB_REQUEST_TIMEOUT: int = 30         # Seconds
WEB_USER_AGENT: str = "Mozilla/5.0..." # Browser user agent
```

- **`WEB_USE_BROWSER_COOKIES`**: Enable/disable browser cookie authentication
  - `True`: Use browser cookies (for paywalled sites like Medium)
  - `False`: Public access only

- **`WEB_REQUEST_TIMEOUT`**: How long to wait for page to load (in seconds)

- **`WEB_USER_AGENT`**: Browser identification string (rarely needs changing)

### Performance Settings

**Memory Management:**

```python
# In app_config.py
CLEANUP_MEMORY_AFTER_PDF: bool = True  # Default: True
```

- **`True` (Recommended)**: Frees ~10GB RAM after processing **all** content
  - Lower memory usage after batch completes
  - During processing: Still uses ~14GB (models stay loaded for PDFs)
  - After processing: Drops to ~4GB
  - **Best for**: MacBooks with 8-16GB RAM
  - **Note**: Cleanup happens once at the end, not between items (to prevent crashes)

- **`False`**: Keeps models in memory indefinitely
  - Memory usage: ~14GB remains even after processing
  - Faster if processing multiple batches
  - **Best for**: Workstations with 32GB+ RAM

## Project Structure

```
Lokal-RAG/
├── main.py                    # Application entry point
├── app_config.py              # Configuration (immutable dataclass)
├── app_services.py            # Pure functional business logic
├── app_storage.py             # Storage layer (ChromaDB, file I/O)
├── app_view.py                # CustomTkinter GUI
├── app_controller.py          # Controller/Orchestrator
├── requirements.txt           # Python dependencies
├── setup_marker.py            # marker-pdf installation script
├── output_markdown/           # Generated Markdown files (by tag)
└── lokal_rag_db/              # ChromaDB persistent storage
```

## Troubleshooting

### Ollama Connection Error

**Problem**: "Cannot connect to Ollama"

**Solution**:
- Ensure Ollama is running: `ollama serve`
- Check if the model is downloaded: `ollama list`
- Verify URL in `app_config.py`

### marker-pdf Installation Issues

**Problem**: marker-pdf fails to install

**Solution**:
- Ensure you have CUDA toolkit installed (for GPU support)
- Try CPU-only installation: `pip install marker-pdf --no-deps` then install dependencies manually
- Check [marker-pdf documentation](https://github.com/VikParuchuri/marker) for platform-specific instructions

### Out of Memory

**Problem**: Application crashes during processing

**Solution**:
- Process fewer files at once
- Use a smaller LLM model (e.g., `qwen2.5:3b-instruct`)
- Increase system swap space
- Close other memory-intensive applications

### Incorrect Text Extraction from PDF

**Problem**: The extracted Markdown contains wrong text or "hallucinated" content that doesn't match the PDF

**Causes**:
- PDFs with corrupted or low-quality text layers (common with web-saved PDFs like Medium articles)
- PDFs that are actually scanned images with broken OCR
- PDFs with mixed text/image content

**Solution (Fixed in v1.1+)**:

The application now uses aggressive OCR settings by default:
- `force_ocr: True` - Forces OCR on all pages
- `strip_existing_ocr: True` - Removes corrupted text layer and re-OCRs

If you still experience issues:

1. **Check the source PDF**: Open it in a PDF viewer and try to select text. If text selection is broken or shows wrong characters, the PDF has a corrupted text layer.

2. **Verify extracted content**: Check the saved `.md` file in `output_markdown/<tag>/` directory before assuming the extraction failed.

3. **Re-process problematic files**: Delete the vector database and re-run:
   ```bash
   rm -rf lokal_rag_db/
   python main.py
   ```

4. **Report the issue**: If marker-pdf consistently fails on a specific PDF type, please report it at [marker-pdf issues](https://github.com/VikParuchuri/marker/issues) with a sample PDF.

**Note**: OCR accuracy depends on PDF quality. Clean, high-resolution PDFs will produce better results than low-quality scans.

### Apple Silicon (M1/M2/M3) GPU Not Used

**Problem**: Log shows "TableRecEncoderDecoderModel is not compatible with mps backend. Defaulting to cpu instead"

**Explanation**:
- Apple Silicon Macs have powerful GPUs accessible via MPS (Metal Performance Shaders)
- However, marker-pdf's OCR engine (Surya) **does not support MPS** yet
- PyTorch automatically falls back to CPU

**Is this a problem?**
- **No**: CPU processing on Apple Silicon is quite fast
- The M-series chips have excellent CPU performance for ML inference
- Processing times are typically 5-10 seconds per page on CPU

**Future**: MPS support may be added to surya/marker-pdf in future releases. Track progress at:
- [PyTorch MPS support](https://github.com/pytorch/pytorch/issues/77764)
- [marker-pdf issues](https://github.com/VikParuchuri/marker/issues)

**Workaround**: None needed - CPU performance is acceptable for most use cases.

### High Memory Usage (14GB+)

**Problem**: Application uses 14GB+ RAM during PDF processing

**Cause**:
- marker-pdf loads 5-6 large ML models (~10GB total):
  - Layout detection model
  - OCR text recognition model
  - Table detection model
  - Text detection model
  - Equation recognition model

**Solution (Updated in v1.2.1)**:

The application now includes automatic memory cleanup **after batch completion**:
- Set `CLEANUP_MEMORY_AFTER_PDF = True` in `app_config.py` (default)
- During processing: Uses ~14GB (models must stay loaded for stability)
- After processing: Drops to ~4GB (cleanup runs once at the end)

**Why cleanup happens at the end, not between PDFs:**
- marker-pdf models don't handle mid-batch cleanup well
- Causes crashes (trace trap) on Apple Silicon when cleaning between files
- Keeping models loaded during batch is more stable

**Alternative solutions**:
1. **Process PDFs in smaller batches**: Select fewer files per run
2. **Close app between batches**: Memory is freed when app exits
3. **Increase swap space**: Allow OS to use disk as virtual RAM
4. **Use a workstation**: If you have 32GB+ RAM, set `CLEANUP_MEMORY_AFTER_PDF = False`

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| GUI | CustomTkinter | Modern, cross-platform UI |
| Orchestration | threading + queue.Queue | Non-blocking task execution |
| PDF Parser | marker-pdf | SOTA PDF-to-Markdown conversion |
| LLM | Ollama + Qwen2.5-7B | Translation, tagging, RAG |
| Vector DB | ChromaDB | Local persistent vector store |
| Embeddings | paraphrase-multilingual-MiniLM-L12-v2 | Fast multilingual embeddings |
| Text Processing | LangChain | Text splitting and RAG utilities |

## License

[Your License Here]

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.
