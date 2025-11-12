# PaddleOCR-VL Setup (Optional)

PaddleOCR-VL is an optional, local document understanding model that enhances image extraction from PDFs. If installed, it will be automatically used instead of Vision LLM APIs (Claude/Gemini) for image description.

## Benefits

- **Local & Free**: No API keys required, no usage costs
- **Specialized for Documents**: Excels at OCR, tables, formulas, and document structure
- **Multilingual**: Supports 109 languages including Russian, English, Chinese, Japanese, Korean, Arabic, Hindi, and more
- **Lightweight**: Only 0.9B parameters (~3-4GB disk space)
- **Better Quality**: SOTA performance on document parsing benchmarks

## Installation

### Prerequisites

- **Linux** (recommended) or **macOS** with Docker/WSL
- **Python 3.8+**
- **Optional but recommended**: CUDA-capable GPU for faster processing

### Step 1: Install PaddlePaddle

Choose the appropriate command for your system:

**With CUDA 12.6 (GPU):**
```bash
python -m pip install paddlepaddle-gpu==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cu126/
```

**CPU-only:**
```bash
python -m pip install paddlepaddle==3.2.0
```

### Step 2: Install PaddleOCR with Document Parser

```bash
python -m pip install -U "paddleocr[doc-parser]"
```

### Step 3: (Optional) Install SafeTensors

For better performance:
```bash
python -m pip install https://paddle-whl.bj.bcebos.com/nightly/cu126/safetensors/safetensors-0.6.2.dev0-cp38-abi3-linux_x86_64.whl
```

## Verification

Test that PaddleOCR is properly installed:

```python
from paddleocr import PaddleOCRVL

# Should import without errors
print("PaddleOCR-VL is available!")
```

## Usage in Lokal-RAG

Once installed, PaddleOCR-VL will be **automatically used** when:

1. "Extract images with vision model" checkbox is enabled in the Ingestion tab
2. A PDF contains images

The system will:
- First try to use PaddleOCR-VL (if installed)
- Fall back to Vision LLM API (Ollama/LM Studio) if PaddleOCR is not available

You'll see this in the logs:
```
Using PaddleOCR-VL for image description (local, specialized for documents)
PaddleOCR-VL extracted 1234 chars from image
```

## Troubleshooting

### Import Error
If you get `ModuleNotFoundError: No module named 'paddleocr'`:
- Ensure you installed paddleocr with the doc-parser feature: `pip install "paddleocr[doc-parser]"`

### Framework Error on macOS
If you get `framework paddle is invalid`:
- PaddleOCR may have limited support on macOS (especially Apple Silicon)
- The system will automatically fall back to Vision LLM API (Claude/Gemini/Ollama/LM Studio)
- For best results on macOS, use Docker or a Linux VM

### CUDA Errors
If you get CUDA-related errors:
- Install the CPU-only version of PaddlePaddle instead
- Or ensure your CUDA version matches the PaddlePaddle build

### Slow Performance
- Use GPU version for faster processing
- First run will download the model (~1-2GB), subsequent runs are faster

### Fallback to Vision LLM
If PaddleOCR fails for any reason, the system automatically falls back to:
- **Claude Vision API** (if provider is Claude and API key is set)
- **Gemini Vision API** (if provider is Gemini and API key is set)
- **Ollama Vision** (if provider is Ollama with vision-capable model)
- **LM Studio Vision** (if provider is LM Studio with vision-capable model)

You'll see this in the logs:
```
PaddleOCR-VL failed, falling back to LLM vision: framework paddle is invalid
Describing image using gemini with model gemini-2.5-flash
```

## Uninstallation

If you want to remove PaddleOCR and go back to using Vision LLM APIs:

```bash
pip uninstall paddleocr paddlepaddle paddlepaddle-gpu
```

Lokal-RAG will automatically fall back to the Vision LLM API method.

## References

- [PaddleOCR-VL HuggingFace](https://huggingface.co/PaddlePaddle/PaddleOCR-VL)
- [PaddleOCR Documentation](https://github.com/PaddlePaddle/PaddleOCR)
- [PaddleOCR-VL Online Demo](https://huggingface.co/spaces/PaddlePaddle/PaddleOCR-VL_Online_Demo)
