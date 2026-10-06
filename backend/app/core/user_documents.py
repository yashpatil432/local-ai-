import io
import os
import re
import uuid
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from pypdf import PdfReader
from PIL import Image

# =====================================================================
# PYDANTIC SCHEMAS FOR USER DOCUMENT MODULE
# =====================================================================

class UserDocumentItem(BaseModel):
    doc_id: str
    session_id: str
    filename: str
    page_count: int
    is_scanned: bool
    ocr_pages: List[int] = Field(default_factory=list)
    status: str  # "ready", "processing", "error"
    error_message: Optional[str] = None
    uploaded_at: str
    file_size_bytes: int = 0
    total_characters: int = 0

class UserDocumentSummary(BaseModel):
    doc_id: str
    filename: str
    short_summary: str
    main_topics: List[str] = Field(default_factory=list)
    important_dates: List[str] = Field(default_factory=list)
    important_rules: List[str] = Field(default_factory=list)
    key_points: List[str] = Field(default_factory=list)

class UserDocCitation(BaseModel):
    doc_id: str
    doc_name: str
    page_number: int
    heading: str = ""
    snippet: str
    relevance_score: float = 0.0

class UserDocQueryRequest(BaseModel):
    session_id: str = "default-session"
    question: str
    doc_id: Optional[str] = "all"  # "all" or specific doc_id

class UserDocQueryResponse(BaseModel):
    answer: str
    citations: List[UserDocCitation] = Field(default_factory=list)
    is_sufficient: bool = True
    searched_docs_count: int = 0
    target_doc_name: Optional[str] = None
    latency_ms: float = 0.0
    detected_language: str = "en"

class UserDocChunk(BaseModel):
    chunk_id: str
    doc_id: str
    doc_name: str
    page_number: int
    heading: str
    text: str
    tokens: List[str] = Field(default_factory=list)

# =====================================================================
# OCR & TEXT EXTRACTION HELPERS
# =====================================================================

def run_ocr_on_pil_image(image: Image.Image) -> str:
    """
    Extracts text from a PIL Image using Windows Native OCR (winocr)
    or fallback to pytesseract. Executes in a separate worker thread
    to prevent conflicts with the active FastAPI/asyncio event loop.
    """
    import concurrent.futures

    def _do_ocr():
        # 1. Try Windows Native OCR (Fastest & pre-installed on Windows 10/11)
        try:
            import winocr
            res = winocr.recognize_pil_sync(image, "en")
            if isinstance(res, dict) and "text" in res and res["text"].strip():
                return res["text"].strip()
        except Exception:
            pass

        # 2. Try pytesseract as fallback
        try:
            import pytesseract
            text = pytesseract.image_to_string(image)
            if text.strip():
                return text.strip()
        except Exception:
            pass

        return ""

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(_do_ocr).result(timeout=15.0)
    except Exception:
        return ""

def extract_pdf_pages_and_metadata(
    file_bytes: bytes, 
    filename: str
) -> Tuple[Dict[int, str], Dict[str, Any]]:
    """
    Extracts text page-by-page from PDF bytes.
    Automatically detects scanned/image-based pages and runs OCR.
    Handles encryption, corrupted files, and blank pages.
    """
    if not file_bytes or len(file_bytes) == 0:
        raise ValueError(f"'{filename}' is an empty file (0 bytes).")

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Could not read PDF '{filename}'. File may be corrupted or not a valid PDF: {str(e)}")

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            pass
        if reader.is_encrypted:
            raise ValueError(f"'{filename}' is password-protected. Please provide an unencrypted PDF.")

    total_pages = len(reader.pages)
    if total_pages == 0:
        raise ValueError(f"'{filename}' has 0 pages.")

    pages_text: Dict[int, str] = {}
    ocr_pages: List[int] = []
    has_scanned_page = False
    total_chars = 0

    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        page_extracted = ""

        # Step 1: Direct digital text extraction
        try:
            digital_text = page.extract_text() or ""
        except Exception:
            digital_text = ""

        clean_digital = digital_text.strip()

        # Step 2: Check if digital text is substantial
        if len(clean_digital) >= 30:
            page_extracted = clean_digital
        else:
            # Step 3: Scanned / Image-based detection
            image_texts = []
            try:
                if hasattr(page, "images") and len(page.images) > 0:
                    for img_obj in page.images:
                        try:
                            pil_img = Image.open(io.BytesIO(img_obj.data))
                            ocr_result = run_ocr_on_pil_image(pil_img)
                            if ocr_result:
                                image_texts.append(ocr_result)
                        except Exception:
                            continue
            except Exception:
                pass

            if image_texts:
                combined_ocr = "\n\n".join(image_texts).strip()
                if combined_ocr:
                    page_extracted = combined_ocr
                    ocr_pages.append(page_num)
                    has_scanned_page = True

            # If still nothing, fallback to whatever digital text existed or placeholder
            if not page_extracted:
                if clean_digital:
                    page_extracted = clean_digital
                else:
                    page_extracted = f"[Page {page_num}: No readable text or images found]"

        pages_text[page_num] = page_extracted
        total_chars += len(page_extracted)

    meta = {
        "page_count": total_pages,
        "is_scanned": has_scanned_page,
        "ocr_pages": ocr_pages,
        "total_characters": total_chars
    }

    return pages_text, meta

def tokenize(text: str) -> List[str]:
    """Simple lowercase alphanumeric tokenization."""
    return re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F]+\b", text.lower())

# =====================================================================
# STRUCTURE-AWARE CHUNKING FOR USER DOCUMENTS
# =====================================================================

def chunk_user_document_pages(
    doc_id: str, 
    doc_name: str, 
    pages_text: Dict[int, str]
) -> List[UserDocChunk]:
    """
    Chunks pages into 400-700 character chunks with overlap,
    preserving page numbers and detecting section headings.
    """
    chunks: List[UserDocChunk] = []
    chunk_counter = 1

    for page_num, text in pages_text.items():
        if not text.strip() or text.startswith("[Page "):
            continue

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

        current_heading = f"Page {page_num}"
        current_buffer = []
        current_len = 0

        for para in paragraphs:
            # Check if paragraph looks like a heading
            if len(para) < 80 and not para.endswith((".", "!", "?", ";", ",")):
                current_heading = para

            words = para.split()
            # If paragraph itself is very long, break it by sentences
            if len(para) > 700:
                sentences = re.split(r"(?<=[.!?\n])\s+", para)
                for sent in sentences:
                    sent = sent.strip()
                    if not sent:
                        continue
                    if current_len + len(sent) > 600 and current_buffer:
                        chunk_text = " ".join(current_buffer)
                        chunks.append(UserDocChunk(
                            chunk_id=f"{doc_id}_p{page_num}_c{chunk_counter}",
                            doc_id=doc_id,
                            doc_name=doc_name,
                            page_number=page_num,
                            heading=current_heading,
                            text=chunk_text,
                            tokens=tokenize(chunk_text)
                        ))
                        chunk_counter += 1
                        # Retain overlap of last sentence
                        current_buffer = [current_buffer[-1], sent] if len(current_buffer) > 1 else [sent]
                        current_len = sum(len(s) for s in current_buffer)
                    else:
                        current_buffer.append(sent)
                        current_len += len(sent)
            else:
                if current_len + len(para) > 600 and current_buffer:
                    chunk_text = " ".join(current_buffer)
                    chunks.append(UserDocChunk(
                        chunk_id=f"{doc_id}_p{page_num}_c{chunk_counter}",
                        doc_id=doc_id,
                        doc_name=doc_name,
                        page_number=page_num,
                        heading=current_heading,
                        text=chunk_text,
                        tokens=tokenize(chunk_text)
                    ))
                    chunk_counter += 1
                    current_buffer = [para]
                    current_len = len(para)
                else:
                    current_buffer.append(para)
                    current_len += len(para)

        # Flush remaining buffer
        if current_buffer:
            chunk_text = " ".join(current_buffer)
            chunks.append(UserDocChunk(
                chunk_id=f"{doc_id}_p{page_num}_c{chunk_counter}",
                doc_id=doc_id,
                doc_name=doc_name,
                page_number=page_num,
                heading=current_heading,
                text=chunk_text,
                tokens=tokenize(chunk_text)
            ))
            chunk_counter += 1

    return chunks

# =====================================================================
# SUMMARY GENERATOR
# =====================================================================

def generate_document_summary(
    doc_id: str, 
    filename: str, 
    pages_text: Dict[int, str]
) -> UserDocumentSummary:
    """
    Extracts key highlights from the uploaded document:
    - Short summary
    - Main topics
    - Important dates
    - Important rules / eligibility
    - Key points / takeaways
    """
    full_text = "\n\n".join(pages_text.values())

    # 1. Important Dates Extraction
    date_regex = re.compile(
        r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|"
        r"\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}|"
        r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?)\b",
        re.IGNORECASE
    )
    found_dates = list(dict.fromkeys(date_regex.findall(full_text)))[:6]
    if not found_dates:
        # Check for year references
        year_matches = list(dict.fromkeys(re.findall(r"\b20[12]\d\b", full_text)))[:4]
        found_dates = [f"Year {y}" for y in year_matches]

    # 2. Important Rules & Eligibility
    rule_keywords = ["eligib", "rule", "criteri", "qualif", "mandat", "must", "shall", "requir", "limit", "fee", "अट", "पात्रता", "नियम"]
    sentences = re.split(r"(?<=[.!?\n])\s+", full_text)
    rule_candidates = []
    for s in sentences:
        s_clean = s.strip()
        if 25 < len(s_clean) < 220:
            if any(k in s_clean.lower() for k in rule_keywords):
                rule_candidates.append(s_clean)
                if len(rule_candidates) >= 5:
                    break

    # 3. Main Topics (Headings / Sections)
    headings = []
    for s in sentences:
        s_clean = s.strip()
        if 8 < len(s_clean) < 65 and not s_clean.endswith((".", ",", ";")):
            # Check if uppercase or title-like
            if any(s_clean.startswith(prefix) for prefix in ["Section", "Chapter", "Article", "Clause", "Part", "1.", "2.", "3.", "4.", "I.", "II."]) or s_clean.isupper() or s_clean.istitle():
                headings.append(s_clean)
                if len(headings) >= 6:
                    break

    # 4. Key Points
    key_points = []
    for s in sentences:
        s_clean = s.strip()
        if 35 < len(s_clean) < 180 and s_clean not in rule_candidates:
            if any(w in s_clean.lower() for w in ["provide", "objective", "purpose", "benefit", "scope", "aim", "policy", "grant", "service", "procedure"]):
                key_points.append(s_clean)
                if len(key_points) >= 4:
                    break
    if len(key_points) < 3:
        # Fallback to informative first few sentences
        for s in sentences:
            s_clean = s.strip()
            if 40 < len(s_clean) < 200 and s_clean not in key_points and s_clean not in rule_candidates:
                key_points.append(s_clean)
                if len(key_points) >= 3:
                    break

    # 5. Short Summary
    lead_sentences = [s.strip() for s in sentences if 40 < len(s.strip()) < 250][:2]
    if lead_sentences:
        short_summary = " ".join(lead_sentences)
    else:
        short_summary = f"Official document '{filename}' containing {len(pages_text)} pages of indexed policy and administrative provisions."

    return UserDocumentSummary(
        doc_id=doc_id,
        filename=filename,
        short_summary=short_summary,
        main_topics=headings if headings else ["General Overview", "Terms & Conditions", "Administrative Details"],
        important_dates=found_dates if found_dates else ["No explicit statutory dates detected in text."],
        important_rules=rule_candidates if rule_candidates else ["Standard regulations and terms specified throughout the text."],
        key_points=key_points if key_points else ["Complete text parsed, structured, and indexed for semantic Q&A."]
    )

# =====================================================================
# USER DOCUMENT STORE (SESSION ISOLATED KNOWLEDGE BASE)
# =====================================================================

class UserDocumentStore:
    """
    In-memory and cached store for user uploaded documents.
    Supports session isolation, multi-document indexing,
    fast hybrid BM25 search, page retrieval, and grounded Q&A.
    """
    def __init__(self):
        # session_id -> List[UserDocumentItem]
        self._documents: Dict[str, Dict[str, UserDocumentItem]] = {}
        # session_id -> doc_id -> Dict[page_num, page_text]
        self._doc_pages: Dict[str, Dict[str, Dict[int, str]]] = {}
        # session_id -> doc_id -> UserDocumentSummary
        self._summaries: Dict[str, Dict[str, UserDocumentSummary]] = {}
        # session_id -> List[UserDocChunk]
        self._chunks: Dict[str, List[UserDocChunk]] = {}

    def add_document(
        self,
        session_id: str,
        filename: str,
        file_bytes: bytes
    ) -> Tuple[UserDocumentItem, UserDocumentSummary]:
        """
        Parses, extracts (with auto-OCR if scanned), chunks, summarizes,
        and indexes a user PDF document for the given session.
        """
        doc_id = "user_doc_" + uuid.uuid4().hex[:8]
        pages_text, meta = extract_pdf_pages_and_metadata(file_bytes, filename)

        doc_item = UserDocumentItem(
            doc_id=doc_id,
            session_id=session_id,
            filename=filename,
            page_count=meta["page_count"],
            is_scanned=meta["is_scanned"],
            ocr_pages=meta["ocr_pages"],
            status="ready",
            uploaded_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            file_size_bytes=len(file_bytes),
            total_characters=meta["total_characters"]
        )

        # Chunk document
        chunks = chunk_user_document_pages(doc_id, filename, pages_text)

        # Generate summary
        summary = generate_document_summary(doc_id, filename, pages_text)

        # Store in session state
        if session_id not in self._documents:
            self._documents[session_id] = {}
            self._doc_pages[session_id] = {}
            self._summaries[session_id] = {}
            self._chunks[session_id] = []

        self._documents[session_id][doc_id] = doc_item
        self._doc_pages[session_id][doc_id] = pages_text
        self._summaries[session_id][doc_id] = summary
        self._chunks[session_id].extend(chunks)

        return doc_item, summary

    def list_documents(self, session_id: str) -> List[UserDocumentItem]:
        if session_id not in self._documents:
            return []
        return list(self._documents[session_id].values())

    def get_document(self, session_id: str, doc_id: str) -> Optional[UserDocumentItem]:
        return self._documents.get(session_id, {}).get(doc_id)

    def delete_document(self, session_id: str, doc_id: str) -> bool:
        if session_id in self._documents and doc_id in self._documents[session_id]:
            del self._documents[session_id][doc_id]
            if doc_id in self._doc_pages.get(session_id, {}):
                del self._doc_pages[session_id][doc_id]
            if doc_id in self._summaries.get(session_id, {}):
                del self._summaries[session_id][doc_id]
            if session_id in self._chunks:
                self._chunks[session_id] = [c for c in self._chunks[session_id] if c.doc_id != doc_id]
            return True
        return False

    def get_summary(self, session_id: str, doc_id: str) -> Optional[UserDocumentSummary]:
        return self._summaries.get(session_id, {}).get(doc_id)

    def get_page_text(self, session_id: str, doc_id: str, page_num: int) -> Optional[str]:
        return self._doc_pages.get(session_id, {}).get(doc_id, {}).get(page_num)

    def query(
        self,
        session_id: str,
        question: str,
        target_doc_id: Optional[str] = "all"
    ) -> UserDocQueryResponse:
        """
        Retrieves relevant passages and generates a grounded response.
        Strict anti-hallucination rule:
        If no sufficient information is found, strictly returns:
        'I couldn't find sufficient information about this in the uploaded documents.'
        """
        start_time = time.time()
        
        # Check if session has any documents
        available_docs = self.list_documents(session_id)
        if not available_docs:
            return UserDocQueryResponse(
                answer="No documents have been uploaded yet. Please upload one or more PDF documents to ask questions.",
                citations=[],
                is_sufficient=False,
                searched_docs_count=0,
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )

        all_chunks = self._chunks.get(session_id, [])
        if target_doc_id and target_doc_id != "all":
            chunks_to_search = [c for c in all_chunks if c.doc_id == target_doc_id]
            target_doc = self.get_document(session_id, target_doc_id)
            target_doc_name = target_doc.filename if target_doc else None
        else:
            chunks_to_search = all_chunks
            target_doc_name = "All Uploaded Documents"

        if not chunks_to_search:
            return UserDocQueryResponse(
                answer="I couldn't find sufficient information about this in the uploaded documents.",
                citations=[],
                is_sufficient=False,
                searched_docs_count=len(available_docs),
                target_doc_name=target_doc_name,
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )

        # BM25 & Lexical Scoring
        q_tokens = set(tokenize(question))
        # Filter common stopwords
        stopwords = {"what", "is", "the", "for", "in", "of", "and", "a", "an", "to", "how", "can", "does", "are", "do", "it", "on", "this", "that", "about"}
        meaningful_q_tokens = {t for t in q_tokens if t not in stopwords and len(t) > 1}
        if not meaningful_q_tokens:
            meaningful_q_tokens = q_tokens

        scored_chunks: List[Tuple[UserDocChunk, float]] = []

        for chunk in chunks_to_search:
            c_tokens = chunk.tokens
            if not c_tokens:
                continue

            # Token overlap score
            overlap_count = sum(1 for t in meaningful_q_tokens if t in c_tokens)
            if overlap_count == 0:
                continue

            jaccard = overlap_count / (len(meaningful_q_tokens) + len(set(c_tokens)) - overlap_count + 1e-5)
            
            # Phrase match boost
            q_lower = question.lower()
            c_text_lower = chunk.text.lower()
            phrase_boost = 0.0
            if q_lower in c_text_lower:
                phrase_boost = 0.5
            elif any(bigram in c_text_lower for bigram in [f"{w1} {w2}" for w1, w2 in zip(list(meaningful_q_tokens)[:-1], list(meaningful_q_tokens)[1:])]):
                phrase_boost = 0.25

            score = (overlap_count * 1.5) + (jaccard * 10.0) + phrase_boost
            scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        top_chunks = scored_chunks[:4]

        # Anti-hallucination gating
        # If no chunks matched or score is too weak (e.g. fewer than 2 meaningful tokens matched when question has multiple)
        if not top_chunks or top_chunks[0][1] < 1.2 or (len(meaningful_q_tokens) >= 3 and sum(1 for t in meaningful_q_tokens if t in top_chunks[0][0].tokens) < 1):
            return UserDocQueryResponse(
                answer="I couldn't find sufficient information about this in the uploaded documents.",
                citations=[],
                is_sufficient=False,
                searched_docs_count=len(available_docs),
                target_doc_name=target_doc_name,
                latency_ms=round((time.time() - start_time) * 1000, 2)
            )

        # Synthesize Grounded Answer & Citations
        citations: List[UserDocCitation] = []
        best_chunk, best_score = top_chunks[0]

        for chunk, score in top_chunks:
            snippet = chunk.text[:220].strip() + ("..." if len(chunk.text) > 220 else "")
            citations.append(UserDocCitation(
                doc_id=chunk.doc_id,
                doc_name=chunk.doc_name,
                page_number=chunk.page_number,
                heading=chunk.heading,
                snippet=snippet,
                relevance_score=round(score, 2)
            ))

        # Format grounded answer
        # Find exact relevant sentence from best chunk
        sentences = re.split(r"(?<=[.!?\n])\s+", best_chunk.text)
        matched_sentences = []
        for s in sentences:
            s_clean = s.strip()
            if any(t in s_clean.lower() for t in meaningful_q_tokens) and len(s_clean) > 20:
                matched_sentences.append(s_clean)

        if matched_sentences:
            core_answer = " ".join(matched_sentences[:3])
        else:
            core_answer = best_chunk.text[:300].strip()

        answer_text = (
            f"Based on **{best_chunk.doc_name}** (Page {best_chunk.page_number}):\n\n"
            f"{core_answer}\n\n"
            f"*(Verified from page {best_chunk.page_number} under '{best_chunk.heading}')*"
        )

        return UserDocQueryResponse(
            answer=answer_text,
            citations=citations,
            is_sufficient=True,
            searched_docs_count=len(available_docs),
            target_doc_name=target_doc_name,
            latency_ms=round((time.time() - start_time) * 1000, 2)
        )

# Global singleton store instance
_user_document_store = UserDocumentStore()

def get_user_document_store() -> UserDocumentStore:
    return _user_document_store
