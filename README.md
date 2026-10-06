# LocalLens: AI for Knowledge Too Local for General Models

> **«Ask locally. Get answers you can verify.»**  
> *An open-weight, source-grounded AI knowledge assistant powered by Gemma 4, hybrid retrieval (BM25 + Dense RRF), native OCR, and zero-hallucination disciplined abstention.*

---

## 🌟 Overview

General-purpose AI models often struggle or hallucinate when asked about specialized, regional, administrative, or frequently changing regulations. **LocalLens** solves this through strict document-grounded retrieval and verifiable citations.

### Key Capabilities:
- 🏛️ **Maharashtra Government Domain**: 10 official Government Resolutions (GRs) across Education, Women & Child Development, Healthcare, Agriculture, Social Welfare, and Citizen Services.
- 📄 **AI Document Upload & Grounded Q&A**: Upload single or multi-PDF documents (digital or scanned). Automatically detects scanned pages and runs page-by-page OCR via Windows Native OCR.
- 🛡️ **Zero-Hallucination Policy**: If verifiable evidence is not present in the indexed documents, the model strictly abstains with `"I couldn't find sufficient information about this in the uploaded documents."`
- 📑 **1-Click Verifiable Citations**: Every answer provides exact Document Name, Page Number, Section Heading, and a `[View Source]` modal reader with text highlights.
- ⚡ **Side-by-Side Comparison**: Live demonstration comparing General AI hallucinations vs. LocalLens grounded facts.
- 📊 **Empirical 50-Question Benchmark**: Real-time evaluation report tracking answer accuracy, citation precision, groundedness score, and hallucination rate.
- 🌓 **Day & Night Mode**: Crisp, high-contrast theme switcher.
- 📂 **Interactive Collections Explorer**: Deep-dive modals for each administrative department and its associated policy resolutions.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Windows 10/11 (for Native Windows OCR support via `winocr`)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/yashpatil432/local-ai-.git
cd local-ai-

# Install required dependencies
pip install fastapi uvicorn pydantic rank-bm25 pypdf pillow winocr pytesseract
```

### 3. Run the Server
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open your browser and navigate to:
```
http://127.0.0.1:8000/
```

---

## 🏗️ Architecture

```
User Query / Document Upload
       │
       ▼
Query Understanding & Language Detection (English, Marathi, Hindi)
       │
       ▼
Hybrid Retrieval Engine
 ├── Okapi BM25 Multi-Script Index
 └── Dense Term Vector Space (RRF Fusion)
       │
       ▼
Answerability Gate & Contradiction Checker
 ├── Strict Overlap & Entity Verification
 └── Version Provenance (v1.0 vs v2.1 Resolution Detection)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[Sufficient Evidence]          [Insufficient Evidence]
       │                                 │
       ▼                                 ▼
Gemma 4 Grounding Layer         Disciplined Abstention
• Verbatim Quotes               • Verifiable Refusal Notice
• Exact Page Citations          • Zero Hallucinations
• [View Source] Highlighting
```

---

## 🧪 Evaluation & Benchmarks

LocalLens includes a built-in empirical 50-question evaluation suite covering:
- **Direct Eligibility Rules** (EBC income caps, Ladki Bahin age thresholds, RTE radius)
- **Edge Cases & Exclusions** (Management quota disqualification, 4-wheeler criteria)
- **Contradiction Testing** (June 2024 v1.0 draft vs. August 2024 v2.1 revised resolution)
- **Zero-Hallucination Abstentions** (Fictional electric vehicles, agricultural spacecraft schemes)
- **Multilingual Queries** (Formal Marathi script and Romanized Devanagari)

---

## 📜 License
MIT License. Built for the Gemma 4 AI Hackathon.
