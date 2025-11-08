# Lokal-RAG

A local-first desktop application for building a private RAG (Retrieval-Augmented Generation) knowledge base from PDF documents.

## Features

- 📄 **PDF Ingestion**: Convert PDF files to high-quality Markdown using marker-pdf
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

### 3. Ingest Documents

1. Go to the "Ingestion" tab
2. Click "Select Folder" and choose a directory containing PDF files
3. (Optional) Enable "Translate to Russian"
4. (Optional) Enable "Auto-tag content"
5. Click "Start Processing"
6. Monitor the log for progress

### 4. Chat with Your Knowledge Base

1. Go to the "Chat" tab
2. Type your question in the input field
3. Press Enter or click "Send"
4. The assistant will respond based on your ingested documents

## Configuration

Edit `app_config.py` to customize:
- Ollama URL and model
- Embedding model
- Vector database path
- Output directory for Markdown files
- Chunk size and overlap for text splitting

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
