# Thai Novel RAG Pipeline & MCP Server

This project implements a complete Retrieval-Augmented Generation (RAG) pipeline for indexing, managing, and retrieving passages from the Thai translation of the novel **"Return of the Mount Hua Sect"** (Chapters 724–819).

It features a parsing, cleaning, and chunking ingestion pipeline, a local/OpenAI embedding system, a PostgreSQL `pgvector` index database, and a standard **Model Context Protocol (MCP)** server for semantic search integration with LLM agents.

---

## 🛠️ System Architecture & Workflow

The project is structured as a layered pipeline. Below is the workflow diagram showing how raw chapter text becomes searchable vector embeddings:

```mermaid
graph TD
    A[Raw Chapter .txt Files] --> B[Text Cleaning & Metadata Extraction]
    B --> C[Paragraph-Aligned Chunking & Overlapping]
    C --> D[Character Candidate Detection & Filtering]
    D --> E[Chunk Quality Assurance Report]
    E --> F[Generate Embeddings OpenAI / Local E5]
    F --> G[Index & Insert into pgvector PostgreSQL]
    G --> H[FastMCP Server stdio]
    H --> I[LLM Agent tool call: search_novel_chunks]
```

### 1. Ingestion & Text Normalization
* **Cleaning**: Removes carriage returns, strips trailing spaces, and normalizes consecutive blank lines to exactly two.
* **Metadata Parsing**: Matches chapter patterns (e.g. `ตอนที่ 724 — ข้ากลับมาแล้ว (4)`) to extract the chapter number and title.

### 2. Paragraph-Aligned Chunking
* **Boundary Alignment**: Chunks do not split paragraphs mid-sentence; they split on paragraph breaks (`\n\n`) to preserve context.
* **Dialogue Safety Guards**: Recognizes open/unbalanced quotes (`“`, `‘`, `"`) and allows a slight length overflow (up to 250 characters) to complete the dialogue before cutting.
* **Tiny Chunk Merger**: Automatically merges small final fragments into the previous chunk if the total length stays within safety limits.
* **Context Overlapping**: Slides paragraph-based overlaps (default 150 characters) onto subsequent chunks to maintain narrative flow.

### 3. Named Entity Resolution (Thai-Korean Characters)
* Heuristics extract potential Korean character names transcribed into Thai (identifying prefixes like *ช็อง, แบ็ก, ฮยอน, ยู, โจ*) adjacent to narrative verbs (*กล่าว, ถาม, ตอบ*).
* A character candidates file is generated for review. Confirmed names are saved in `characters.txt` and attached to relevant chunks for index metadata.

### 4. Vector Database & Indexing (`pgvector`)
* Chunks are sent to the embedding model (`intfloat/multilingual-e5-small` locally, or OpenAI embeddings).
* Embeddings and chunk metadata (chapter, index, title, characters, source file) are stored in a local PostgreSQL database using the `pgvector` extension.
* Cosine distance is used to retrieve the most similar passages.

---

## 🚀 The Model Context Protocol (MCP) Server

The MCP server provides standard integration for developer tools and AI clients (like Claude Desktop or Gemini).

### Features & Anti-Feedback Loop Safeguards
To prevent agent loop overheads and API quota drain, the `search_novel_chunks` tool is designed with:
1. **LRU Cache**: Caches up to 64 query results in-memory. Identical repeated queries are served instantly.
2. **Capped Limits**: The request parameter `limit` is clamped to a maximum of 10 results.
3. **Structured Marker**: Results conclude with a `[SEARCH COMPLETE]` marker signaling to the agent that the search has finished and no further rephrased queries are needed.
4. **Agent Docstring Guidance**: Instructs LLM agents to call the tool at most once per user question.

---

## ⚙️ Setup & Prerequisites

### 1. Run the pgvector Database
Use Docker Compose to launch the database container:
```bash
docker compose up -d
```
This starts PostgreSQL with `pgvector` on port `5435` (database name: `basic_rag`, username: `rag_user`, password: `rag_password`).

### 2. Set Up Virtual Environment & Dependencies
Initialize your virtual environment and install packages:
```bash
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.venv\Scripts\activate

# Activate (macOS/Linux)
source .venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env` and configure:
```env
DATABASE_URL=postgresql://rag_user:rag_password@localhost:5435/basic_rag
EMBEDDING_PROVIDER=local  # Or 'openai'
EMBEDDING_MODEL=intfloat/multilingual-e5-small  # Or 'text-embedding-3-small'
EMBEDDING_DIMENSION=384   # 384 for E5-small, 1536 for OpenAI
HF_HUB_OFFLINE=1          # Speeds up local model load by skipping remote updates
```

---

## 📖 How to Run the Pipeline

### Step 1: Export & Chunk Chapter Files
Process all `.txt` chapter files in a directory and output JSON chunks:
```bash
python -m app.ingest data --characters characters.txt --out chunks
```

### Step 2: Extract & Refine Characters (Optional)
Extract character name candidates from your source texts to compile `characters.txt`:
```bash
python -m app.character_candidates data --out character_candidates.md --json character_candidates.json
```

### Step 3: Run Chunk Quality Assurance
Evaluate chunk quality (checking for unbalanced quotes, short lengths, soft endings):
```bash
python -m app.chunk_qa chunks --out chunk_quality_report.md --json chunk_quality_report.json
```

### Step 4: Index Chunks into PostgreSQL
Embed the JSON chunks and write them to the vector database:
```bash
python -m app.index_chunks chunks
```

### Step 5: Test Similarity Search via CLI
Query the database directly from the CLI:
```bash
python -m app.search "ชองมย็อง โจรสลัด"
```

---

## 🔌 Running & Testing the MCP Server

### Start the Server
Start the MCP server using stdio transport:
```bash
python -m app.mcp_server
```

### Test the MCP Server Client
You can verify the MCP server functionality using the built-in async client:
```bash
python test_mcp_client.py
```
This tests the session initialization, lists available tools, and runs a semantic search query through the stdio interface.

### Running Tests
Execute the unit and integration test suite:
```bash
pytest
```
