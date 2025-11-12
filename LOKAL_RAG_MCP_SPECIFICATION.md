# Lokal-RAG MCP Server - Technical Specification

**Version:** 1.0.0
**Status:** RFC (Request for Comments)
**Last Updated:** 2025-11-12

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [MCP Tools Reference](#mcp-tools-reference)
4. [Use Cases & Scenarios](#use-cases--scenarios)
5. [Integration with Existing Codebase](#integration-with-existing-codebase)
6. [Configuration & Deployment](#configuration--deployment)
7. [Future Enhancements](#future-enhancements)

---

## Overview

### What is Lokal-RAG MCP Server?

The Lokal-RAG MCP (Model Context Protocol) Server is a bridge between AI assistants (like Claude Desktop) and your local knowledge base. It exposes the full power of Lokal-RAG's hybrid search, notes system, and chat capabilities through a standardized MCP interface.

### Key Features

- **🔍 Advanced Search**: Hybrid search (BM25 + Vector), full-text search, semantic search
- **📝 Notes Management**: Create, read, update, delete personal notes with vector search
- **💬 Contextual Chat**: Chat with AI using your knowledge base as context
- **🏷️ Tag System**: Organize and filter content by tags
- **📊 Knowledge Analytics**: Statistics, insights, and exploration of your knowledge base
- **🌐 Multi-language Support**: Russian/English translations, cross-language search
- **🎯 Smart Recommendations**: AI-powered content recommendations based on your reading history

### Why MCP?

The Model Context Protocol enables:
- Direct access to your knowledge base from Claude Desktop or any MCP client
- Seamless integration without running the GUI application
- Programmatic access to all Lokal-RAG features
- Extension capabilities for custom workflows

---

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Client                               │
│              (Claude Desktop, Cursor, etc.)                  │
└────────────────────┬────────────────────────────────────────┘
                     │ stdio/SSE
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Lokal-RAG MCP Server                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Search Tools  │  Notes Tools  │  Chat Tools         │   │
│  ├──────────────────────────────────────────────────────┤   │
│  │  Info Tools    │  Analytics    │  Recommendation     │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │         Core Service Layer                            │  │
│  │  (app_storage.py, app_chat.py, app_services.py)      │  │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  Data Layer                                  │
│  ┌────────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │  ChromaDB      │  │  Markdown   │  │  Notes JSON     │  │
│  │  (Vectors)     │  │  Files      │  │  Files          │  │
│  └────────────────┘  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### **MCP Server** (`server.py`)
- FastMCP-based server implementation
- Tool registration and routing
- Authentication and configuration management
- Error handling and logging

#### **Storage Service** (`storage.py`)
- Wrapper around `app_storage.py`
- Vector database operations
- Document and note persistence
- Metadata management

#### **Chat Service** (`chat.py`)
- Wrapper around `app_chat.py`
- Contextual chat with RAG
- LLM provider integration
- Conversation history management

---

## MCP Tools Reference

### 1. Search Tools

#### `lokal_rag_search`

**Description:** Universal search across all documents and notes with multiple search modes.

**Parameters:**
```typescript
{
  query: string;                    // Search query (required)
  mode?: "hybrid" | "vector" | "fulltext";  // Search mode (default: "hybrid")
  limit?: number;                   // Max results (default: 5, max: 50)
  filter_type?: "document" | "note" | "all";  // Content type filter (default: "all")
  filter_tags?: string[];           // Filter by tags (optional)
  filter_language?: "ru" | "en" | "all";  // Language filter (default: "all")
  include_metadata?: boolean;       // Include full metadata (default: true)
}
```

**Returns:**
```typescript
{
  results: Array<{
    id: string;
    title: string;
    content: string;           // Snippet of matching content
    score: number;             // Relevance score (0-1)
    type: "document" | "note";
    tags: string[];
    language: "ru" | "en";
    created_at: string;        // ISO timestamp
    source?: string;           // Original source (PDF path or URL)
    metadata: {
      bm25_score?: number;
      vector_score?: number;
      snippet_context?: string;  // Surrounding text
    }
  }>;
  search_info: {
    query: string;
    mode: string;
    total_found: number;
    search_time_ms: number;
  }
}
```

**Example Usage:**
```typescript
// Hybrid search across everything
lokal_rag_search({
  query: "machine learning optimization techniques",
  mode: "hybrid",
  limit: 10
})

// Search only in notes with specific tag
lokal_rag_search({
  query: "project ideas",
  filter_type: "note",
  filter_tags: ["ideas", "ai"],
  limit: 5
})

// Semantic search in Russian documents
lokal_rag_search({
  query: "оптимизация нейронных сетей",
  mode: "vector",
  filter_language: "ru"
})
```

---

#### `lokal_rag_get_document`

**Description:** Retrieve a complete document or note by ID with full content.

**Parameters:**
```typescript
{
  id: string;                    // Document/note ID (required)
  include_related?: boolean;     // Include related documents (default: false)
  related_limit?: number;        // Max related items (default: 5)
}
```

**Returns:**
```typescript
{
  id: string;
  type: "document" | "note";
  title: string;
  content: string;               // Full markdown content
  content_en?: string;           // English version (if translated)
  content_ru?: string;           // Russian version (if translated)
  tags: string[];
  language: "ru" | "en";
  created_at: string;
  updated_at: string;
  source?: string;
  metadata: {
    source_type: "pdf" | "web" | "note";
    original_filename?: string;
    url?: string;
    processed_at?: string;
    images_processed?: number;
  };
  related_documents?: Array<{   // If include_related=true
    id: string;
    title: string;
    score: number;
    tags: string[];
  }>;
}
```

**Example Usage:**
```typescript
// Get document with related content
lokal_rag_get_document({
  id: "doc_abc123",
  include_related: true,
  related_limit: 3
})
```

---

#### `lokal_rag_list_documents`

**Description:** List all documents and notes with pagination and filtering.

**Parameters:**
```typescript
{
  type?: "document" | "note" | "all";  // Filter by type (default: "all")
  tags?: string[];                     // Filter by tags (AND logic)
  language?: "ru" | "en" | "all";      // Filter by language (default: "all")
  sort_by?: "created_at" | "updated_at" | "title";  // Sort field (default: "created_at")
  sort_order?: "asc" | "desc";         // Sort direction (default: "desc")
  limit?: number;                      // Results per page (default: 20, max: 100)
  offset?: number;                     // Pagination offset (default: 0)
}
```

**Returns:**
```typescript
{
  items: Array<{
    id: string;
    type: "document" | "note";
    title: string;
    excerpt: string;           // First 200 chars
    tags: string[];
    language: "ru" | "en";
    created_at: string;
    updated_at: string;
  }>;
  pagination: {
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  }
}
```

**Example Usage:**
```typescript
// List all AI-related documents, newest first
lokal_rag_list_documents({
  type: "document",
  tags: ["ai", "machine-learning"],
  sort_by: "created_at",
  sort_order: "desc",
  limit: 20
})
```

---

### 2. Notes Tools

#### `lokal_rag_create_note`

**Description:** Create a new note in the knowledge base with automatic embedding generation.

**Parameters:**
```typescript
{
  title: string;                 // Note title (required)
  content: string;               // Note content in markdown (required)
  tags?: string[];               // Tags for organization (optional)
  language?: "ru" | "en";        // Content language (default: auto-detect)
}
```

**Returns:**
```typescript
{
  id: string;                    // Generated note ID
  title: string;
  created_at: string;
  message: string;               // Success message
}
```

**Example Usage:**
```typescript
lokal_rag_create_note({
  title: "Meeting Notes - AI Strategy Discussion",
  content: `
# Key Points

- Focus on RAG systems for enterprise
- Evaluate Granite-Docling for document processing
- Budget approved for GPU infrastructure

## Action Items
- [ ] Research vector database options
- [ ] Schedule follow-up next week
  `,
  tags: ["meeting", "ai", "strategy"]
})
```

---

#### `lokal_rag_list_notes`

**Description:** List all notes with filtering and search.

**Parameters:**
```typescript
{
  search?: string;               // Search in title/content (optional)
  tags?: string[];               // Filter by tags (optional)
  sort_by?: "created_at" | "updated_at" | "title";
  sort_order?: "asc" | "desc";
  limit?: number;
  offset?: number;
}
```

**Returns:**
```typescript
{
  notes: Array<{
    id: string;
    title: string;
    excerpt: string;
    tags: string[];
    created_at: string;
    updated_at: string;
  }>;
  pagination: {
    total: number;
    limit: number;
    offset: number;
  }
}
```

---

#### `lokal_rag_get_note`

**Description:** Retrieve a note by ID with full content.

**Parameters:**
```typescript
{
  id: string;                    // Note ID (required)
}
```

**Returns:**
```typescript
{
  id: string;
  title: string;
  content: string;               // Full markdown content
  tags: string[];
  language: "ru" | "en";
  created_at: string;
  updated_at: string;
}
```

---

#### `lokal_rag_update_note`

**Description:** Update an existing note.

**Parameters:**
```typescript
{
  id: string;                    // Note ID (required)
  title?: string;                // New title (optional)
  content?: string;              // New content (optional)
  tags?: string[];               // New tags (optional, replaces existing)
}
```

**Returns:**
```typescript
{
  id: string;
  updated_at: string;
  message: string;
}
```

---

#### `lokal_rag_delete_note`

**Description:** Delete a note from the knowledge base.

**Parameters:**
```typescript
{
  id: string;                    // Note ID (required)
  confirm?: boolean;             // Confirmation flag (default: false)
}
```

**Returns:**
```typescript
{
  deleted: boolean;
  message: string;
}
```

---

### 3. Chat Tools

#### `lokal_rag_chat`

**Description:** Chat with AI assistant using your knowledge base as context. Automatically retrieves relevant documents/notes and includes them in the conversation.

**Parameters:**
```typescript
{
  message: string;               // User message (required)
  context_mode?: "auto" | "documents" | "notes" | "all";  // What to search (default: "auto")
  context_limit?: number;        // Max context items (default: 5, max: 20)
  filter_tags?: string[];        // Limit context to specific tags (optional)
  include_sources?: boolean;     // Return source citations (default: true)
  temperature?: number;          // LLM temperature (default: 0.7, range: 0-1)
}
```

**Returns:**
```typescript
{
  response: string;              // AI assistant's response
  sources: Array<{               // Context sources used (if include_sources=true)
    id: string;
    title: string;
    type: "document" | "note";
    relevance_score: number;
    excerpt: string;
  }>;
  metadata: {
    context_items_used: number;
    total_context_chars: number;
    llm_provider: string;
    response_time_ms: number;
  }
}
```

**Example Usage:**
```typescript
// General question with automatic context retrieval
lokal_rag_chat({
  message: "What are the main optimization techniques for neural networks mentioned in my documents?",
  context_mode: "auto",
  context_limit: 10,
  include_sources: true
})

// Question limited to specific topic
lokal_rag_chat({
  message: "Summarize my notes about RAG systems",
  context_mode: "notes",
  filter_tags: ["rag", "ai"],
  context_limit: 5
})
```

---

#### `lokal_rag_chat_with_history`

**Description:** Multi-turn conversation with persistent context and history.

**Parameters:**
```typescript
{
  message: string;               // User message (required)
  session_id?: string;           // Conversation session ID (auto-generated if not provided)
  context_mode?: "auto" | "documents" | "notes" | "all";
  context_limit?: number;
  include_sources?: boolean;
  temperature?: number;
  max_history_turns?: number;    // Max conversation history to keep (default: 10)
}
```

**Returns:**
```typescript
{
  response: string;
  session_id: string;            // For continuing conversation
  sources: Array<{...}>;
  conversation_history: Array<{
    role: "user" | "assistant";
    content: string;
    timestamp: string;
  }>;
  metadata: {
    turn_number: number;
    context_items_used: number;
    llm_provider: string;
  }
}
```

**Example Usage:**
```typescript
// First message
const chat1 = lokal_rag_chat_with_history({
  message: "What are the main topics in my AI documents?"
})

// Follow-up using session_id
lokal_rag_chat_with_history({
  session_id: chat1.session_id,
  message: "Which ones discuss transformer architectures?"
})
```

---

### 4. Info & Analytics Tools

#### `lokal_rag_get_stats`

**Description:** Get comprehensive statistics about your knowledge base.

**Parameters:**
```typescript
{
  include_tag_stats?: boolean;   // Include tag distribution (default: true)
  include_temporal_stats?: boolean;  // Include timeline stats (default: false)
}
```

**Returns:**
```typescript
{
  overview: {
    total_documents: number;
    total_notes: number;
    total_items: number;
    total_tags: number;
    database_size_mb: number;
  };
  documents: {
    total: number;
    by_language: {
      en: number;
      ru: number;
    };
    by_source_type: {
      pdf: number;
      web: number;
    };
    with_translations: number;
    with_images: number;
  };
  notes: {
    total: number;
    by_language: {
      en: number;
      ru: number;
    };
    average_length_chars: number;
  };
  tags: {                        // If include_tag_stats=true
    most_used: Array<{
      tag: string;
      count: number;
    }>;
    total_unique: number;
  };
  temporal?: {                   // If include_temporal_stats=true
    documents_per_month: Array<{
      month: string;             // "2025-01", "2025-02", etc.
      count: number;
    }>;
    recent_activity: {
      last_7_days: number;
      last_30_days: number;
      last_90_days: number;
    };
  };
  last_updated: string;
}
```

---

#### `lokal_rag_list_tags`

**Description:** Get all tags with usage statistics.

**Parameters:**
```typescript
{
  min_usage?: number;            // Minimum document count (default: 1)
  sort_by?: "name" | "count";    // Sort method (default: "count")
  sort_order?: "asc" | "desc";   // Sort direction (default: "desc")
}
```

**Returns:**
```typescript
{
  tags: Array<{
    name: string;
    count: number;               // Number of items with this tag
    types: {                     // Breakdown by type
      documents: number;
      notes: number;
    };
    related_tags: string[];      // Tags that often appear together
  }>;
  total: number;
}
```

---

#### `lokal_rag_get_tag_documents`

**Description:** Get all documents/notes with a specific tag.

**Parameters:**
```typescript
{
  tag: string;                   // Tag name (required)
  type?: "document" | "note" | "all";
  sort_by?: "created_at" | "updated_at" | "title";
  limit?: number;
  offset?: number;
}
```

**Returns:**
```typescript
{
  tag: string;
  items: Array<{
    id: string;
    type: "document" | "note";
    title: string;
    excerpt: string;
    created_at: string;
    other_tags: string[];        // Other tags on this item
  }>;
  total_count: number;
  pagination: {...}
}
```

---

### 5. Advanced Analytics Tools

#### `lokal_rag_find_similar`

**Description:** Find documents/notes similar to a given item using vector similarity.

**Parameters:**
```typescript
{
  id: string;                    // Reference document/note ID (required)
  limit?: number;                // Max similar items (default: 10, max: 50)
  similarity_threshold?: number; // Min similarity score (default: 0.5, range: 0-1)
  filter_type?: "document" | "note" | "all";
  exclude_same_source?: boolean; // Exclude items from same PDF/URL (default: false)
}
```

**Returns:**
```typescript
{
  reference: {
    id: string;
    title: string;
    type: "document" | "note";
  };
  similar_items: Array<{
    id: string;
    title: string;
    type: "document" | "note";
    similarity_score: number;    // 0-1
    common_tags: string[];
    excerpt: string;
  }>;
  search_info: {
    total_found: number;
    threshold_used: number;
  }
}
```

---

#### `lokal_rag_get_recommendations`

**Description:** Get personalized content recommendations based on reading patterns and preferences.

**Parameters:**
```typescript
{
  based_on?: "recent" | "tags" | "manual";  // Recommendation strategy (default: "recent")
  reference_ids?: string[];      // Manual reference IDs (if based_on="manual")
  reference_tags?: string[];     // Reference tags (if based_on="tags")
  limit?: number;                // Max recommendations (default: 10)
  diversity?: number;            // Diversity factor (default: 0.3, range: 0-1)
                                 // Higher = more diverse, lower = more focused
}
```

**Returns:**
```typescript
{
  recommendations: Array<{
    id: string;
    title: string;
    type: "document" | "note";
    relevance_score: number;
    reason: string;              // Why recommended
    tags: string[];
    created_at: string;
  }>;
  strategy_used: string;
  metadata: {
    total_candidates: number;
    filters_applied: string[];
  }
}
```

**Example Usage:**
```typescript
// Recommendations based on recent reading
lokal_rag_get_recommendations({
  based_on: "recent",
  limit: 5
})

// Recommendations based on specific interests
lokal_rag_get_recommendations({
  based_on: "tags",
  reference_tags: ["machine-learning", "optimization"],
  limit: 10,
  diversity: 0.5
})
```

---

#### `lokal_rag_explore_topic`

**Description:** Deep dive into a topic across your knowledge base with clustering and relationships.

**Parameters:**
```typescript
{
  topic: string;                 // Topic to explore (required)
  max_items?: number;            // Max items to analyze (default: 50)
  include_clusters?: boolean;    // Group related content (default: true)
  include_timeline?: boolean;    // Show topic evolution (default: false)
}
```

**Returns:**
```typescript
{
  topic: string;
  overview: {
    total_matches: number;
    key_concepts: string[];      // Extracted key phrases
    sentiment?: "positive" | "neutral" | "negative";
  };
  items: Array<{
    id: string;
    title: string;
    type: "document" | "note";
    relevance: number;
    excerpt: string;
    created_at: string;
  }>;
  clusters?: Array<{             // If include_clusters=true
    name: string;                // Auto-generated cluster name
    items: string[];             // Document IDs in cluster
    common_themes: string[];
  }>;
  timeline?: Array<{             // If include_timeline=true
    period: string;              // "2024-Q4", "2025-Q1", etc.
    item_count: number;
    key_developments: string[];
  }>;
}
```

---

### 6. Utility Tools

#### `lokal_rag_export_data`

**Description:** Export documents/notes in various formats for backup or migration.

**Parameters:**
```typescript
{
  format: "json" | "markdown" | "zip";  // Export format (required)
  filter_type?: "document" | "note" | "all";
  filter_tags?: string[];
  include_metadata?: boolean;    // Include full metadata (default: true)
}
```

**Returns:**
```typescript
{
  export_id: string;             // Unique export ID
  format: string;
  item_count: number;
  download_url?: string;         // If format="zip"
  data?: object;                 // Inline data if format="json"
  message: string;
}
```

---

#### `lokal_rag_health_check`

**Description:** Check the health and status of the Lokal-RAG system.

**Parameters:**
```typescript
{
  include_diagnostics?: boolean; // Include detailed diagnostics (default: false)
}
```

**Returns:**
```typescript
{
  status: "healthy" | "degraded" | "error";
  components: {
    vector_db: {
      status: "ok" | "error";
      latency_ms: number;
    };
    storage: {
      status: "ok" | "error";
      free_space_gb: number;
    };
    llm_provider: {
      status: "ok" | "error";
      provider: string;
    };
  };
  diagnostics?: {                // If include_diagnostics=true
    database_integrity: "ok" | "issues";
    index_status: "up_to_date" | "needs_rebuild";
    warnings: string[];
  };
  timestamp: string;
}
```

---

## Use Cases & Scenarios

### Scenario 1: Research Assistant

**Use Case:** You're researching AI optimization techniques and want Claude to help you synthesize information from your saved papers.

```typescript
// Step 1: Search for relevant papers
const papers = await lokal_rag_search({
  query: "neural network optimization techniques",
  mode: "hybrid",
  filter_type: "document",
  limit: 10
});

// Step 2: Chat with context
const analysis = await lokal_rag_chat({
  message: "Compare the optimization techniques from these papers and create a summary table",
  context_mode: "documents",
  filter_tags: ["optimization", "neural-networks"],
  include_sources: true
});

// Step 3: Save insights as a note
await lokal_rag_create_note({
  title: "Neural Network Optimization - Comparative Analysis",
  content: analysis.response,
  tags: ["research", "optimization", "summary"]
});
```

---

### Scenario 2: Meeting Notes Management

**Use Case:** Take meeting notes and link them to relevant project documents.

```typescript
// Create meeting note
const meeting = await lokal_rag_create_note({
  title: "Weekly AI Team Sync - 2025-11-12",
  content: `
# Attendees
- Team Lead, Engineers, Product Manager

# Discussion Points
- Review RAG implementation progress
- Discuss vision model integration (Granite-Docling)
- Plan next sprint

# Decisions
- Approved: Separate vision provider configuration
- Next: Implement MCP server for knowledge base access

# Action Items
- [ ] Complete MCP server by end of week
- [ ] Test Granite-Docling on production PDFs
  `,
  tags: ["meeting", "ai-team", "2025-11"]
});

// Find related project documents
const related = await lokal_rag_find_similar({
  id: meeting.id,
  filter_type: "document",
  limit: 5
});
```

---

### Scenario 3: Knowledge Base Exploration

**Use Case:** Explore what you know about a topic and discover related content.

```typescript
// Deep dive into RAG systems
const exploration = await lokal_rag_explore_topic({
  topic: "retrieval augmented generation",
  max_items: 50,
  include_clusters: true,
  include_timeline: true
});

// Get recommendations for further reading
const recommendations = await lokal_rag_get_recommendations({
  based_on: "tags",
  reference_tags: ["rag", "vector-search"],
  limit: 10,
  diversity: 0.4
});
```

---

### Scenario 4: Content Curation

**Use Case:** Organize and curate content on specific topics.

```typescript
// Find all ML-related content
const mlContent = await lokal_rag_list_documents({
  tags: ["machine-learning"],
  sort_by: "created_at",
  sort_order: "desc",
  limit: 100
});

// Get tag statistics to understand coverage
const tagStats = await lokal_rag_list_tags({
  sort_by: "count",
  sort_order: "desc"
});

// Create a curated reading list note
const readingList = mlContent.items
  .slice(0, 10)
  .map(item => `- [${item.title}](id:${item.id})`)
  .join('\n');

await lokal_rag_create_note({
  title: "ML Reading List - Priority",
  content: `# Machine Learning - Must Read\n\n${readingList}`,
  tags: ["reading-list", "machine-learning", "curated"]
});
```

---

### Scenario 5: Multi-turn Research Conversation

**Use Case:** Have an extended conversation about a complex topic with persistent context.

```typescript
// Start conversation
const chat1 = await lokal_rag_chat_with_history({
  message: "What are the main approaches to document understanding in my knowledge base?"
});

// Follow-up: dive deeper
const chat2 = await lokal_rag_chat_with_history({
  session_id: chat1.session_id,
  message: "Which approach would be best for processing scientific papers with lots of equations?"
});

// Follow-up: compare solutions
const chat3 = await lokal_rag_chat_with_history({
  session_id: chat1.session_id,
  message: "Compare Granite-Docling with traditional OCR approaches based on my documents"
});

// Save the conversation insights
await lokal_rag_create_note({
  title: "Document Understanding Research - Insights",
  content: chat3.conversation_history
    .map(turn => `**${turn.role}:** ${turn.content}`)
    .join('\n\n'),
  tags: ["research", "document-understanding", "conversation"]
});
```

---

## Integration with Existing Codebase

### Reuse Strategy

The MCP server will be a thin wrapper around existing Lokal-RAG components:

```python
# Existing components to reuse:
from app_storage import VectorStorage      # Vector DB operations
from app_chat import fn_chat_with_context  # RAG chat
from app_services import (
    fn_translate_text,                     # Translation
    fn_generate_tags,                      # Tag generation
)
from app_config import AppConfig           # Configuration

# MCP server wraps these with MCP tool interface
```

### Data Flow

```
MCP Tool Call
    ↓
Server.py (validation, auth)
    ↓
Storage.py / Chat.py (business logic wrapper)
    ↓
app_storage.py / app_chat.py (existing implementation)
    ↓
ChromaDB / LLM Provider
    ↓
Response back through chain
```

### Minimal Code Duplication

- **Reuse:** All core logic (search, chat, embedding, translation)
- **New:** Only MCP-specific glue code and tool definitions
- **Benefit:** Bug fixes and features in main app automatically benefit MCP server

---

## Configuration & Deployment

### Installation

```bash
# Install as package
cd lokal-rag-mcp
pip install -e .

# Or with uv
uv pip install lokal-rag-mcp
```

### Configuration

#### Environment Variables

```bash
# Core settings
export LOKAL_RAG_DB_PATH="/path/to/lokal_rag_db"
export LOKAL_RAG_MARKDOWN_PATH="/path/to/output_markdown"
export LOKAL_RAG_NOTES_PATH="/path/to/notes"

# LLM Provider (will read from settings.json by default)
export LOKAL_RAG_LLM_PROVIDER="gemini"
export LOKAL_RAG_GEMINI_API_KEY="your-key"

# Optional: Override settings
export LOKAL_RAG_SETTINGS_PATH="/custom/path/settings.json"
```

#### Settings File

The server will automatically read from `~/.lokal-rag/settings.json` (same as GUI app):

```json
{
  "llm_provider": "gemini",
  "gemini_api_key": "...",
  "gemini_model": "gemini-2.5-pro-preview-03-25",
  "vision_mode": "auto",
  "vector_db_path": "./lokal_rag_db",
  "markdown_output_path": "./output_markdown"
}
```

### Claude Desktop Configuration

```json
{
  "mcpServers": {
    "lokal-rag": {
      "command": "uvx",
      "args": [
        "lokal-rag-mcp"
      ]
    }
  }
}
```

**With custom paths:**

```json
{
  "mcpServers": {
    "lokal-rag": {
      "command": "uvx",
      "args": [
        "lokal-rag-mcp",
        "--db-path", "/Users/ponyol/my-projects/Lokal-RAG/lokal_rag_db",
        "--settings", "/Users/ponyol/.lokal-rag/settings.json"
      ]
    }
  }
}
```

### Running Standalone

```bash
# Development mode
python -m lokal_rag_mcp.server

# With custom config
lokal-rag-mcp --db-path ./lokal_rag_db --settings ./settings.json

# Verbose logging
lokal-rag-mcp --log-level debug
```

---

## Future Enhancements

### Phase 2: Advanced Features

1. **Collaborative Features**
   - `lokal_rag_share_note` - Generate shareable links
   - `lokal_rag_export_collection` - Export filtered subset
   - `lokal_rag_import_collection` - Import from others

2. **Automation & Workflows**
   - `lokal_rag_create_workflow` - Define processing pipelines
   - `lokal_rag_schedule_task` - Scheduled updates/summaries
   - `lokal_rag_watch_folder` - Auto-process new PDFs

3. **Advanced Analytics**
   - `lokal_rag_generate_report` - Automated reports on topics
   - `lokal_rag_knowledge_graph` - Visual knowledge relationships
   - `lokal_rag_trend_analysis` - Topic trends over time

4. **Integration Hooks**
   - `lokal_rag_webhook_create` - Trigger external actions
   - `lokal_rag_plugin_install` - Extend with custom tools
   - `lokal_rag_api_key_create` - Generate API keys for external access

### Phase 3: Multi-User & Cloud

1. **Multi-User Support**
   - User authentication
   - Permission system
   - Shared collections

2. **Cloud Sync**
   - Sync across devices
   - Cloud backup
   - Mobile access

3. **Enterprise Features**
   - SSO integration
   - Audit logs
   - Compliance tools

---

## Security Considerations

### Authentication

- **Phase 1:** Local-only, no authentication (trust MCP client)
- **Phase 2:** Optional API key for remote access
- **Phase 3:** Full OAuth/JWT for multi-user

### Data Privacy

- All data stays local by default
- No telemetry or external calls (except to configured LLM providers)
- Encryption at rest (optional, for sensitive data)

### Rate Limiting

- Protect LLM API quota with rate limiting
- Configurable limits per tool
- Cost tracking and alerts

---

## Performance Targets

### Response Time Goals

- **Search operations:** < 200ms (p95)
- **Note CRUD:** < 100ms (p95)
- **Chat (without LLM):** < 300ms (p95)
- **Chat (with LLM):** < 3s (p95, depends on provider)
- **Analytics/Stats:** < 500ms (p95)

### Scalability

- Support up to 10,000 documents/notes efficiently
- Handle 100 concurrent MCP connections
- Maintain <100MB memory footprint base

---

## Testing Strategy

### Unit Tests

- All tools have unit tests
- Mock ChromaDB and LLM providers
- Test error handling and edge cases

### Integration Tests

- End-to-end tool workflows
- Real ChromaDB instance (ephemeral)
- Real LLM calls (optional, with API key)

### MCP Protocol Tests

- Tool schema validation
- Error response formats
- Transport layer (stdio, SSE)

---

## Documentation Deliverables

1. **README.md** - Quick start guide
2. **API_REFERENCE.md** - Complete tool documentation
3. **EXAMPLES.md** - Usage examples and recipes
4. **CONTRIBUTING.md** - Development guide
5. **CHANGELOG.md** - Version history

---

## Open Questions & Decisions Needed

1. **Tool Granularity:** Should we combine some tools (e.g., create/update note into single upsert)?

2. **Conversation History:** Where to store chat sessions?
   - Option A: In-memory (lost on restart)
   - Option B: SQLite database
   - Option C: ChromaDB metadata

3. **Embeddings:** Should MCP server use same embedding model as GUI app?
   - Option A: Always use configured model
   - Option B: Allow override per tool call
   - Option C: Support multiple embedding backends

4. **Tag Normalization:** Auto-normalize tags (lowercase, slugify)?
   - Pros: Consistent, easier search
   - Cons: Less flexible, might break existing tags

5. **Search Result Ranking:** Allow custom ranking formulas?
   - Default: BM25 + Vector weighted
   - Allow: Custom weights per query

6. **Resource Limits:** How to prevent abuse?
   - Max results per query
   - Rate limiting per client
   - Memory limits

---

## Success Metrics

### Adoption

- Number of active users
- Daily API calls
- Tool usage distribution

### Performance

- p50/p95/p99 latencies
- Error rate < 1%
- Uptime > 99.9%

### Quality

- Search result relevance (user feedback)
- Chat response quality
- Bug report rate

---

## Timeline Estimate

### Phase 1: MVP (2-3 weeks)

- Week 1: Core infrastructure, search tools
- Week 2: Notes tools, basic chat
- Week 3: Testing, documentation, deployment

### Phase 2: Advanced Features (4-6 weeks)

- Analytics tools
- Recommendations
- Export/import
- Performance optimization

### Phase 3: Enterprise (8-12 weeks)

- Multi-user support
- Cloud sync
- Advanced security
- Monitoring/observability

---

## Conclusion

The Lokal-RAG MCP Server transforms your local knowledge base into a powerful, AI-accessible resource. By leveraging the Model Context Protocol, we create a seamless bridge between your curated knowledge and AI assistants, enabling workflows that were previously impossible.

**Next Steps:**

1. Review this specification
2. Gather feedback and refine
3. Create proof-of-concept with 3-5 core tools
4. Iterate based on real-world usage
5. Expand to full feature set

**Questions? Ideas? Concerns?**

Please add comments or open issues. This is a living document that will evolve with the project.

---

**Document Version:** 1.0.0
**Author:** Claude (AI Assistant) + Ponyol (Project Owner)
**License:** Same as Lokal-RAG project
