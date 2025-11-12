# Granite-Docling-258m Setup (Recommended for Document Vision)

IBM's **granite-docling-258m** is a lightweight vision model (258M parameters) specifically designed for document understanding. It excels at OCR, table extraction, and document structure analysis while being much smaller than general-purpose vision models.

## Why Granite-Docling?

- **Lightweight**: Only 258M parameters (~500MB disk space)
- **Document-Specialized**: Built specifically for PDF/document understanding
- **Fast**: Runs efficiently on CPU or GPU
- **Local**: No API costs, runs through Ollama
- **macOS Compatible**: Works on Apple Silicon (unlike PaddleOCR)
- **Better than General Vision Models**: Outperforms LLaVA and similar models on document tasks

## Installation

### Step 1: Install Ollama

If you haven't already, install Ollama:

**macOS/Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

**Or download from:** https://ollama.com/download

### Step 2: Pull Granite-Docling Model

```bash
ollama pull granite-docling:258m
```

This will download the model (~500MB). First run may take a minute.

### Step 3: Verify Installation

Test the model works:

```bash
ollama run granite-docling:258m
```

You should see a prompt. Type `/exit` to quit.

## Configuration in Lokal-RAG

There are two ways to use granite-docling for image extraction:

### Option A: Set as Vision Model (Recommended)

In the **Settings** tab:

1. Set **LLM Provider** to `ollama`
2. Set **Vision Model** field to: `granite-docling:258m`
3. Keep **Ollama Model** as your main model (e.g., `qwen2.5:7b-instruct`)
4. Save settings

Now when you enable "Extract images with vision model", it will use granite-docling for images.

### Option B: Use as Main Model

If you want to use granite-docling for both text and images:

1. Set **LLM Provider** to `ollama`
2. Set **Ollama Model** to: `granite-docling:258m`
3. Leave **Vision Model** empty
4. Save settings

⚠️ **Note**: granite-docling is optimized for document vision, not general chat. Use Option A for best results.

## Usage

1. Go to **Ingestion** tab
2. Check ✅ **"Extract images with vision model"**
3. Select your PDF files
4. Click **"Start Processing"**

In the logs you'll see:
```
Describing image using ollama with model granite-docling:258m
✓ Image description complete
```

## Performance Comparison

| Model | Size | Speed (CPU) | Quality (Docs) | API Cost |
|-------|------|-------------|----------------|----------|
| **granite-docling:258m** | 258M | ⚡ Fast | ⭐⭐⭐⭐⭐ | Free |
| PaddleOCR-VL | 900M | ⚡⚡ Medium | ⭐⭐⭐⭐⭐ | Free |
| Claude Vision | N/A | ⚡⚡⚡ Fast | ⭐⭐⭐⭐ | $$ |
| Gemini Vision | N/A | ⚡⚡⚡ Fast | ⭐⭐⭐⭐ | $ |
| LLaVA 7B | 7B | 🐌 Slow | ⭐⭐⭐ | Free |

## Best Use Cases

Granite-docling excels at:
- ✅ **OCR**: Text extraction from images
- ✅ **Tables**: Complex table structures
- ✅ **Formulas**: Mathematical notation (though not LaTeX)
- ✅ **Charts**: Basic chart understanding
- ✅ **Multi-column layouts**: Document structure
- ✅ **Low-quality scans**: Robust to noise

It's less ideal for:
- ❌ General image understanding (photos, art)
- ❌ Complex reasoning about images
- ❌ Creative image descriptions

## Troubleshooting

### Model Not Found
If you get "model not found" error:
```bash
ollama list  # Check installed models
ollama pull granite-docling:258m  # Re-download if needed
```

### Slow Performance
- First run downloads the model and may be slow
- Subsequent runs should be fast
- Consider using GPU for better performance

### Wrong Provider Error
Make sure you set:
- **LLM Provider** = `ollama` (not claude/gemini)
- **Vision Model** = `granite-docling:258m`

### Connection Error
Ensure Ollama is running:
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama service if needed (usually runs automatically)
ollama serve
```

## Alternative: Using with Docker

If you prefer Docker:

```bash
docker run -d -p 11434:11434 --name ollama ollama/ollama
docker exec -it ollama ollama pull granite-docling:258m
```

## Comparison with PaddleOCR-VL

| Feature | Granite-Docling | PaddleOCR-VL |
|---------|----------------|--------------|
| Size | 258M | 900M |
| macOS Support | ✅ Yes | ❌ Limited |
| Installation | Easy (Ollama) | Complex |
| OCR Quality | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Table Extraction | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Multi-language | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (109 langs) |
| Speed | Faster | Slower |

**Recommendation**:
- **macOS users**: Use granite-docling (PaddleOCR doesn't work)
- **Linux users**: Try both and compare quality
- **Multilingual docs**: PaddleOCR-VL has better language support

## Combining with PaddleOCR

The system automatically uses the best available method:

1. **PaddleOCR-VL** (if installed and working)
2. **Granite-Docling** (if Ollama + model configured)
3. **Gemini/Claude Vision** (API fallback)

This gives you maximum flexibility!

## References

- [Granite-Docling on Ollama](https://ollama.com/library/granite-docling)
- [IBM Granite Models](https://github.com/ibm-granite/granite-docling)
- [Ollama Documentation](https://github.com/ollama/ollama)

## Uninstallation

To remove the model:

```bash
ollama rm granite-docling:258m
```

The system will automatically fall back to other vision methods.
