# Roha Future Roadmap (Phases 4 & 5)

This document maps out the remaining enhancement ideas for Roha's Odysseus-style web interface to be implemented in future phases.

## Phase 4: Advanced Memory & RAG Visualization

*   **Interactive Memory Graph / Node Viewer:**
    *   Integrate a force-directed graph library (e.g., `vis.js` or standard SVGs) to visualize connections and semantic clusters of memory entries within the SQLite and Vector stores.
*   **Vector Search Playground:**
    *   Add a dedicated interactive console tab to perform and debug raw vector/semantic searches and compare results directly side-by-side with keyword-based retrieval.
*   **CRUD Memory Manager:**
    *   An administrative dashboard to browse, search, edit, delete, or flag specific memory records directly without writing manual SQL queries.

## Phase 5: File Sandbox & Code Execution Workspace

*   **Interactive Markdown Code Previewer:**
    *   Enable executing HTML/CSS/JS snippets directly within a sandboxed `iframe` or previewing outputs in real-time.
*   **File Explorer Tree:**
    *   For verified creators, render a workspace file-tree explorer allowing file viewing, direct edits, and creation of scripts inside the workspace directory directly from the Roha console.
