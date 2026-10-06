import os
import json
import re
import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from rank_bm25 import BM25Okapi

from backend.app.models.schemas import Chunk, DocumentMetadata
from backend.app.core.chunking import chunk_document

# Multilingual and Cross-Lingual Synonyms dictionary for Maharashtra schemes
CROSS_LINGUAL_SYNONYMS = {
    # Marathi -> English/Concepts
    "कागदपत्रे": "documents required checklist proof certificates",
    "कागदपत्र": "documents required checklist",
    "दस्तावेज": "documents required certificates",
    "प्रमाणपत्र": "certificate proof",
    "पात्रता": "eligibility criteria eligible conditions qualification",
    "पात्र": "eligible criteria",
    "अपात्र": "ineligible disqualified excluded",
    "उत्पन्न": "income annual family ceiling limit lakh",
    "उत्पन्नाची": "income limit annual ceiling",
    "आय": "income annual salary earnings",
    "वय": "age limit years completed",
    "वयाची": "age limit criteria years",
    "उम्र": "age limit years",
    "मुदत": "deadline last date submission closing",
    "शेवटची": "deadline last final date",
    "अंतिम": "last date deadline",
    "अर्ज": "application apply registration form portal",
    "अर्जाची": "application procedure apply steps process",
    "पद्धत": "procedure process method portal steps",
    "कसा करावा": "how to apply procedure online",
    "लाभ": "benefit allowance reimbursement grant financial amount",
    "फायदा": "benefit entitlement concession",
    "रक्कम": "amount financial assistance rupees",
    "मोफत": "free 100% waiver zero bill concession",
    "सवलत": "concession waiver subsidy free",
    "वसतिगृह": "hostel accommodation rent boarding",
    "शेतकरी": "farmer agriculture marginal alpabhudharak",
    "अल्पभूधारक": "marginal farmer 2 hectares landholding",
    "शेतमजूर": "agricultural laborer farm worker",
    "निराधार": "destitute orphan widow disabled helpless",
    "आरोग्य": "health insurance hospital cashless treatment mjpjay",
    "उपचार": "treatment surgery procedures cashless",
    "विमा": "insurance sum insured cover 5 lakh",
    "वीज": "electricity pump power agricultural 7.5 hp",
    "पंप": "pump agricultural electricity 7.5 hp",
    "प्रवेश": "admission quota lottery entry school",
    "शाळा": "school education admission rte",
    "स्वाधार": "swadhar sc students higher education hostel",
    "सेवा": "services citizen rts aaple sarkar deadline",
    "हमी": "guarantee statutory delivery timeline days",
    "कालावधी": "time limit delivery working days deadline",
    "अपील": "appeal first appeal second appeal days 30",
    "दंड": "penalty fine defaulting officer rs 500 5000",
    "नाशिक": "nashik tier 1 30000 city eligible",
    "पुणे": "pune tier 1 city",
    "मुंबई": "mumbai tier 1 city",
    "लाडकी बहीण": "ladki bahin women 1500 monthly ration card",
    "ईबीसी": "ebc scholarship 8 lakh cap quota centralized admission",
    "व्यवस्थापन कोटा": "management quota institutional ineligible disqualified",
    "रेशन कार्ड": "ration card yellow orange white exemption",
    "पिवळे": "yellow ration card exempt income",
    "केशरी": "orange ration card exempt income"
}

def detect_language(query: str) -> str:
    """
    Detects if query is Marathi (Devanagari with Marathi specific particles),
    Hindi, or English/mixed.
    """
    marathi_markers = ["आहे", "नाही", "काय", "कसे", "करावे", "कोण", "लागतात", "होतो", "शकेल", "शकतो", "योजनेसाठी", "मिळेल", "का?"]
    hindi_markers = ["है", "नहीं", "क्या", "कैसे", "कौन", "लगते", "सकता", "मिलेगा", "चाहिए", "होगा"]
    
    # Check Devanagari script presence
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', query))
    if has_devanagari:
        for marker in marathi_markers:
            if marker in query:
                return "mr"
        for marker in hindi_markers:
            if marker in query:
                return "hi"
        return "mr"  # Default to Marathi in Maharashtra portal context
    
    # Hinglish / Marathi in Latin script check
    query_lower = query.lower()
    marathi_latin = ["aahe", "nahi", "sathi", "karu", "shakto", "shakle", "lagtat", "mahiti", "kiti", "kasa", "kase"]
    if any(m in query_lower.split() for m in marathi_latin):
        return "mr_latin"
        
    return "en"

def normalize_and_expand_query(query: str) -> str:
    """
    Normalizes query and adds cross-lingual conceptual expansion terms.
    Preserves original tokens while adding synonyms to maximize recall across languages.
    """
    expanded_tokens = [query]
    query_clean = re.sub(r'[^\w\s\u0900-\u097F]', ' ', query.lower())
    
    for term, expansion in CROSS_LINGUAL_SYNONYMS.items():
        if term in query or term in query_clean:
            expanded_tokens.append(expansion)
            
    return " ".join(expanded_tokens)

def tokenize_multilingual(text: str) -> List[str]:
    """
    Tokenizes both Latin and Devanagari scripts, splitting on whitespace and punctuation.
    """
    clean_text = re.sub(r'[^\w\s\u0900-\u097F]', ' ', text.lower())
    tokens = clean_text.split()
    return [t for t in tokens if len(t) > 1]

class HybridRetriever:
    """
    Production Hybrid Retriever combining:
    1. Okapi BM25 keyword matching with multilingual tokenization
    2. Dense/Term-vector TF-IDF cosine similarity
    3. Reciprocal Rank Fusion (RRF)
    4. Document freshness weighting
    """
    def __init__(self):
        self.chunks: List[Chunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.chunk_vectors: Optional[np.ndarray] = None
        self.documents_metadata: List[DocumentMetadata] = []
        
    def index_documents(self, documents: List[Tuple[DocumentMetadata, str]]):
        """
        Indexes a list of (metadata, raw_markdown_text) tuples.
        """
        self.chunks = []
        self.documents_metadata = [doc[0] for doc in documents]
        
        for doc_meta, raw_text in documents:
            doc_chunks = chunk_document(doc_meta, raw_text)
            self.chunks.extend(doc_chunks)
            
        if not self.chunks:
            return
            
        # 1. Build BM25 index
        corpus_tokens = []
        for chunk in self.chunks:
            # Combine title, section, text, and table context for maximum chunk representation
            full_chunk_text = f"{chunk.document_title} {chunk.section} {chunk.text} {chunk.table_context or ''}"
            tokens = tokenize_multilingual(full_chunk_text)
            corpus_tokens.append(tokens)
            
        self.bm25 = BM25Okapi(corpus_tokens)
        
        # 2. Build TF-IDF dense term vector space
        all_vocab = set()
        for tokens in corpus_tokens:
            all_vocab.update(tokens)
            
        self.vocab = {term: idx for idx, term in enumerate(sorted(all_vocab))}
        num_docs = len(corpus_tokens)
        
        # Calculate IDF
        self.idf = {}
        for term, idx in self.vocab.items():
            doc_freq = sum(1 for tokens in corpus_tokens if term in tokens)
            self.idf[term] = math.log((num_docs + 1) / (doc_freq + 1)) + 1.0
            
        # Build document matrix
        matrix = np.zeros((num_docs, len(self.vocab)), dtype=np.float32)
        for doc_idx, tokens in enumerate(corpus_tokens):
            term_counts = {}
            for t in tokens:
                term_counts[t] = term_counts.get(t, 0) + 1
            for t, count in term_counts.items():
                if t in self.vocab:
                    col_idx = self.vocab[t]
                    tf = math.log(count + 1)
                    matrix[doc_idx, col_idx] = tf * self.idf[t]
                    
            # Normalize row vector
            norm = np.linalg.norm(matrix[doc_idx])
            if norm > 0:
                matrix[doc_idx] /= norm
                
        self.chunk_vectors = matrix

    def search(
        self, 
        query: str, 
        top_k: int = 5,
        category_filter: Optional[str] = None,
        department_filter: Optional[str] = None,
        status_filter: Optional[str] = None
    ) -> List[Tuple[Chunk, float]]:
        """
        Performs hybrid retrieval using RRF (Reciprocal Rank Fusion)
        between BM25 and Dense TF-IDF, applying filters and freshness scoring.
        """
        if not self.chunks or self.bm25 is None or self.chunk_vectors is None:
            return []
            
        expanded_query = normalize_and_expand_query(query)
        query_tokens = tokenize_multilingual(expanded_query)
        if not query_tokens:
            return []
            
        # 1. BM25 Scores
        bm25_scores = self.bm25.get_scores(query_tokens)
        bm25_ranking = np.argsort(bm25_scores)[::-1]
        
        # 2. Dense Vector Cosine Similarity
        query_vec = np.zeros(len(self.vocab), dtype=np.float32)
        q_counts = {}
        for t in query_tokens:
            q_counts[t] = q_counts.get(t, 0) + 1
        for t, count in q_counts.items():
            if t in self.vocab:
                col_idx = self.vocab[t]
                tf = math.log(count + 1)
                query_vec[col_idx] = tf * self.idf[t]
        q_norm = np.linalg.norm(query_vec)
        if q_norm > 0:
            query_vec /= q_norm
            
        dense_scores = np.dot(self.chunk_vectors, query_vec)
        dense_ranking = np.argsort(dense_scores)[::-1]
        
        # 3. Reciprocal Rank Fusion (RRF with k=60)
        rrf_scores = np.zeros(len(self.chunks), dtype=np.float32)
        k_const = 60.0
        
        for rank, doc_idx in enumerate(bm25_ranking):
            if bm25_scores[doc_idx] > 0:
                rrf_scores[doc_idx] += 1.0 / (k_const + rank + 1)
                
        for rank, doc_idx in enumerate(dense_ranking):
            if dense_scores[doc_idx] > 0:
                rrf_scores[doc_idx] += 1.0 / (k_const + rank + 1)
                
        # 4. Apply Freshness & Exact Title Boost
        is_historical_query = any(w in query.lower() for w in ["june", "v1", "v1.0", "initial", "preliminary", "superseded", "draft", "earlier", "order"])
        
        for idx, chunk in enumerate(self.chunks):
            # Boost current versions unless query asks specifically about historical/draft versions
            if chunk.status == "current":
                rrf_scores[idx] *= 1.15
            elif chunk.status == "outdated":
                if is_historical_query:
                    rrf_scores[idx] *= 1.40  # Boost outdated version when asked about past draft
                else:
                    rrf_scores[idx] *= 0.85
                
            # Boost if query mentions scheme keywords directly in title
            doc_title_tokens = set(tokenize_multilingual(chunk.document_title))
            common_title_tokens = set(query_tokens).intersection(doc_title_tokens)
            if common_title_tokens:
                rrf_scores[idx] += 0.005 * len(common_title_tokens)

        # 5. Filter, Enforce Document Diversity, and Sort
        filtered_results: List[Tuple[Chunk, float]] = []
        sorted_indices = np.argsort(rrf_scores)[::-1]
        doc_counts: Dict[str, int] = {}
        
        for idx in sorted_indices:
            chunk = self.chunks[idx]
            score = float(rrf_scores[idx])
            
            if score <= 0.0001:
                continue
                
            # Filters
            if category_filter and chunk.metadata.get("category", "").lower() != category_filter.lower():
                continue
            if department_filter and department_filter.lower() not in chunk.department.lower():
                continue
            if status_filter and chunk.status.lower() != status_filter.lower():
                continue
                
            # Document diversity: at most 2 chunks per document in top results
            current_count = doc_counts.get(chunk.document_id, 0)
            if current_count >= 2:
                continue
                
            doc_counts[chunk.document_id] = current_count + 1
            filtered_results.append((chunk, score))
            if len(filtered_results) >= top_k:
                break
                
        return filtered_results

# Global retriever singleton
retriever_instance = HybridRetriever()

def get_retriever() -> HybridRetriever:
    return retriever_instance
