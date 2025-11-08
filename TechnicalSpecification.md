## Technical Specification: "Lokal-RAG" Desktop Application

### 1.0 Overview

**Project:** Lokal-RAG
**Objective:** A local-first, Python-based desktop application for building a private RAG (Retrieval-Augmented Generation) knowledge base from PDF documents.
**Core Functionality:**

1.  Ingest PDF files from a user-selected directory.
2.  Convert PDFs to high-quality Markdown (`.md`).
3.  (Optional) Translate Markdown content to Russian.
4.  (Optional) Auto-tag content based on its subject matter.
5.  Save the processed Markdown files to a structured output directory, sorted by tag.
6.  Ingest the final text content into a local, persistent vector database.
7.  Provide a simple chat interface to query the ingested knowledge base.

**Guiding Principles:**

  * **Local-First:** All processing and data storage remain on the user's machine. The only I/O is to the local file system and a local `Ollama` instance.
  * **Functional Core:** The data processing pipeline (`app_services.py`) will be built using functional programming principles (pure functions, immutability, composition).
  * **Responsive GUI:** The user interface must **never** freeze. All heavy I/O and compute tasks (PDF parsing, LLM calls, embedding) must run in a separate, non-blocking thread.
  * **Modularity:** The application will be split into four distinct layers: `View` (GUI), `Controller` (State/Event Management), `Services` (Functional Logic), and `Storage` (Data Access).

### 2.0 System Architecture & Technology Stack

| Component | Layer | Technology / Library | Purpose |
| :--- | :--- | :--- | :--- |
| **GUI** | View | `CustomTkinter` | For a modern, lightweight, and cross-platform UI. |
| **Orchestrator** | Controller | `threading`, `queue.Queue` | To manage application state (e.g., `idle`, `processing`) and coordinate the View and Services in a non-blocking way. |
| **PDF Parser** | Services | `marker-pdf` | SOTA quality for PDF-to-Markdown conversion, including tables. |
| **LLM Runner** | Services (I/O) | `Ollama` (via `httpx`) | External dependency. Manages and serves the LLM. |
| **LLM Model** | Services (I/O) | `Qwen2.5-7B-Instruct` | Primary model for Translation, Tagging, and RAG. Chosen for its 128K context window. |
| **Vector DB** | Storage | `ChromaDB` (Persistent) | Local, file-based vector store. |
| **Embedding Model** | Storage | `paraphrase-multilingual-MiniLM-L12-v2` | Fast, lightweight multilingual model for creating embeddings on CPU. |
| **Orchestration** | Services | `LangChain` | Used as "glue" for text splitting (`RecursiveCharacterTextSplitter`) and RAG chain setup. |

### 3.0 Module & Component Specification

#### 3.1. `app_config.py` (Configuration)

A module defining a `dataclass` or `Pydantic` model to hold application settings. This object will be created once and passed immutably to all functions that need it.

```python
# app_config.py
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class AppConfig:
    """Immutable configuration for the application."""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b-instruct"
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    VECTOR_DB_PATH: Path = Path("./lokal_rag_db")
    MARKDOWN_OUTPUT_PATH: Path = Path("./output_markdown")
    # ... other settings
```

#### 3.2. `app_storage.py` (Storage Layer)

This module initializes and encapsulates the heavy, stateful objects (`ChromaDB` client and the `Embedding` model).

  * **`StorageService` (Class):**
      * `__init__(self, config: AppConfig)`: Initializes the `HuggingFaceEmbeddings` model (loading it into memory) and the `ChromaDB` persistent client.
      * `get_vectorstore(self) -> Chroma`: Returns the Chroma collection instance.
      * `add_documents(self, docs: list) -> None`: A stateful method to add documents to the DB.
  * **`fn_save_markdown_to_disk(text: str, tag: str, filename: str, config: AppConfig) -> Path`:**
      * A **pure function** that takes the content and metadata.
      * It determines the `output_path` (e.g., `config.MARKDOWN_OUTPUT_PATH / tag / filename`).
      * It performs the I/O (side effect) of writing the file.
      * Returns the `Path` to the newly created file.

#### 3.3. `app_services.py` (Functional Core)

This is the **purely functional** module. It contains *only* functions. No classes, no global state.

  * **`fn_call_ollama(prompt: str, system_prompt: str, config: AppConfig) -> str`:**
      * A pure function (aside from the I/O side effect).
      * Takes a prompt and configuration.
      * Uses `httpx` to send the request to `config.OLLAMA_BASE_URL`.
      * Returns the `str` response.
  * **`fn_extract_markdown(pdf_path: Path) -> str`:**
      * A pure function (aside from I/O).
      * Calls `marker.convert_single_pdf` on the `pdf_path`.
      * Returns the `str` content of the generated Markdown.
  * **`fn_translate_text(text: str, config: AppConfig) -> str`:**
      * A pure function.
      * Composes `fn_call_ollama` with a specific system prompt for translation.
  * **`fn_generate_tags(text: str, config: AppConfig) -> list[str]`:**
      * A pure function.
      * Composes `fn_call_ollama` with a prompt to extract key themes.
      * Parses the LLM response into a `list` of tags (e.g., `["python", "ai"]`).
  * **`fn_create_text_chunks(text: str, source_file: str) -> list[Document]`:**
      * A pure function.
      * Uses `LangChain`'s `RecursiveCharacterTextSplitter`.
      * Returns a list of `Document` objects, each with `page_content` and `metadata={"source": source_file}`.
  * **`fn_get_rag_response(query: str, vectorstore: Chroma, config: AppConfig) -> str`:**
      * A pure function.
      * 1.  Retrieves relevant documents (`vectorstore.similarity_search`).
      * 2.  Composes a new prompt from the query and the retrieved context.
      * 3.  Composes `fn_call_ollama` to get the final answer.
      * 4.  Returns the answer string.

#### 3.4. `app_view.py` (The View)

This module contains the `AppView` class, built with `CustomTkinter`.

  * **`AppView` (Class):**
      * `__init__(self, master)`: Sets up the main window, tabs ("Ingestion", "Chat"), and widgets.
      * **Ingestion Tab Widgets:**
          * `self.folder_path_var` (StringVar)
          * `self.select_folder_button`
          * `self.translate_var` (BooleanVar)
          * `self.translate_checkbox`
          * `self.tag_var` (BooleanVar)
          * `self.tag_checkbox`
          * `self.start_button`
          * `self.log_textbox` (CTkTextbox, state="disabled")
      * **Chat Tab Widgets:**
          * `self.chat_history_textbox` (CTkTextbox, state="disabled")
          * `self.chat_entry` (CTkEntry)
          * `self.send_button`
      * **Methods:**
          * `get_ingestion_settings(self) -> dict`: Returns a dictionary of the current UI settings (path, checkboxes).
          * `set_processing_state(self, is_processing: bool)`: Disables/enables buttons and shows a progress indicator.
          * `append_log(self, message: str)`: Thread-safe method to append a message to `self.log_textbox`.
          * `append_chat_message(self, role: str, message: str)`: Appends a message to the chat history.

#### 3.5. `app_controller.py` (The Controller)

This is the central state machine of the application.

  * **`AppOrchestrator` (Class):**
      * `__init__(self, view: AppView, config: AppConfig, storage: StorageService)`: Stores references to the other layers.
      * `self.view_queue = queue.Queue()`: A queue for worker threads to send messages *to* the View (e.g., log updates).
      * `self.is_processing = False`
      * `bind_events(self)`: Connects View widgets to controller methods (e.g., `view.start_button.configure(command=self.on_start_ingestion)`).
      * `check_view_queue(self)`: A method called every 100ms by the `CustomTkinter` main loop (`view.after(100, self.check_view_queue)`). It reads messages from `self.view_queue` and calls `view.append_log()`. This is the **only** thread-safe way to update the GUI from a worker.
      * `on_start_ingestion(self)`:
        1.  If `self.is_processing`, return.
        2.  Set `self.is_processing = True`.
        3.  Call `self.view.set_processing_state(True)`.
        4.  Get settings from `self.view.get_ingestion_settings()`.
        5.  Find all PDF files in the selected path.
        6.  Create and start a new `threading.Thread`, passing it the `processing_pipeline_worker` function, the list of files, the config, and the queue.
      * `on_send_chat_message(self)`: (Similar pattern, spawns a thread for `rag_chat_worker`).

### 4.0 Worker Functions (Thread Targets)

These are the *imperative* functions that live in `app_controller.py` and are run in separate threads. They are the "glue" that calls the pure *functional* services.

  * **`processing_pipeline_worker(pdf_files: list[Path], settings: dict, config: AppConfig, storage: StorageService, view_queue: queue.Queue) -> None`:**

      * This function **IS RUN IN A THREAD.**
      * It iterates through `pdf_files`: `for pdf in pdf_files:`
      * Inside a `try...except` block:
        1.  `view_queue.put(f"Processing {pdf.name}...")`
        2.  `markdown = fn_extract_markdown(pdf)`
        3.  `final_text = markdown`
        4.  `if settings['do_translation']:`
              * `final_text = fn_translate_text(markdown, config)`
        5.  `if settings['do_tagging']:`
              * `tags = fn_generate_tags(final_text, config)`
        6.  `fn_save_markdown_to_disk(final_text, tags[0], pdf.stem, config)`
        7.  `chunks = fn_create_text_chunks(final_text, source_file=pdf.name)`
        8.  `storage.add_documents(chunks)`
        9.  `view_queue.put(f"SUCCESS: {pdf.name} ingested.")`
      * `except Exception as e:`
        1.  `view_queue.put(f"ERROR: {pdf.name} failed. {e}")`
      * Finally:
        1.  `view_queue.put("--- Processing Complete ---")`
        2.  `view_queue.put("STOP_PROCESSING")` (A special message for the controller to reset its state).

  * **`rag_chat_worker(query: str, config: AppConfig, storage: StorageService, view_queue: queue.Queue) -> None`:**

      * **IS RUN IN A THREAD.**
      * `try...except` block:
        1.  `response = fn_get_rag_response(query, storage.get_vectorstore(), config)`
        2.  `view_queue.put(f"ASSISTANT: {response}")`
      * `except Exception as e:`
        1.  `view_queue.put(f"ERROR: {e}")`

### 5.0 Definition of Done (v1.0)

1.  Application launches and displays the "Ingestion" and "Chat" tabs.
2.  User can select a folder.
3.  User can click "Start Processing".
4.  The GUI remains responsive, and the log text box fills with status updates.
5.  Processed `.md` files appear in the `output_markdown/<tag>/` directory.
6.  The `lokal_rag_db` directory is created and populated.
7.  The user can go to the "Chat" tab and ask a question related to the ingested documents.
8.  The chat interface displays a relevant answer retrieved from the local documents.
