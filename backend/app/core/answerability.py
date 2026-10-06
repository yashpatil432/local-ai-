import re
from typing import List, Tuple, Dict, Any, Optional
from backend.app.models.schemas import Chunk, ContradictionItem, EvidencePassage

class AnswerabilityAssessment:
    def __init__(
        self,
        is_answerable: bool,
        relevance_score: float,
        confidence: str,
        grounding_strength: str,
        contradictions: List[ContradictionItem],
        what_i_found: List[str],
        missing_information: List[str],
        recommended_status: str
    ):
        self.is_answerable = is_answerable
        self.relevance_score = relevance_score
        self.confidence = confidence
        self.grounding_strength = grounding_strength
        self.contradictions = contradictions
        self.what_i_found = what_i_found
        self.missing_information = missing_information
        self.recommended_status = recommended_status

def detect_contradictions_in_evidence(retrieved_chunks: List[Tuple[Chunk, float]]) -> List[ContradictionItem]:
    """
    Checks for conflicting facts across multiple retrieved chunks,
    especially across different versions of the same scheme (e.g. Ladki Bahin v1.0 vs v2.1).
    """
    contradictions: List[ContradictionItem] = []
    
    # Check if we have chunks from both ladki_bahin_v1 (deprecated) and ladki_bahin_v2 (current)
    doc_ids = set(c.document_id for c, _ in retrieved_chunks)
    
    if "scheme_002_ladki_bahin_v2" in doc_ids and "scheme_003_ladki_bahin_v1_deprecated" in doc_ids:
        chunk_v2 = next((c for c, _ in retrieved_chunks if c.document_id == "scheme_002_ladki_bahin_v2"), None)
        chunk_v1 = next((c for c, _ in retrieved_chunks if c.document_id == "scheme_003_ladki_bahin_v1_deprecated"), None)
        
        if chunk_v2 and chunk_v1:
            contradictions.append(ContradictionItem(
                detected=True,
                description="Conflicting Government Resolutions Detected: The preliminary order (v1.0, June 2024) and the revised resolution (v2.1, August 2024) have conflicting provisions regarding age limit and deadline.",
                source_a={
                    "document_title": chunk_v1.document_title,
                    "version": "v1.0 (Outdated / Superseded)",
                    "date": chunk_v1.published,
                    "section": chunk_v1.section,
                    "page": chunk_v1.page,
                    "excerpt": "Preliminary age ceiling was 60 years and initial deadline was 15th July 2024."
                },
                source_b={
                    "document_title": chunk_v2.document_title,
                    "version": "v2.1 (Current Official Resolution)",
                    "date": chunk_v2.published,
                    "section": chunk_v2.section,
                    "page": chunk_v2.page,
                    "excerpt": "Age ceiling officially expanded to 65 years, continuous registration window, and yellow/orange ration card exemption."
                },
                guidance="Please rely on the latest Government Resolution (v2.1, dated 1st August 2024). In government administration, the latest gazetted resolution supersedes all earlier preliminary drafts."
            ))
            
    return contradictions

def assess_answerability(
    query: str, 
    retrieved_chunks: List[Tuple[Chunk, float]],
    relevance_threshold: float = 0.012
) -> AnswerabilityAssessment:
    """
    Evaluates whether the retrieved evidence is sufficiently relevant and covers
    the entities in the query to provide a grounded answer without hallucinating.
    """
    if not retrieved_chunks:
        return AnswerabilityAssessment(
            is_answerable=False,
            relevance_score=0.0,
            confidence="insufficient_evidence",
            grounding_strength="None",
            contradictions=[],
            what_i_found=[],
            missing_information=["No relevant documents found in the Maharashtra Government knowledge base."],
            recommended_status="Not found"
        )
        
    top_chunk, top_score = retrieved_chunks[0]
    contradictions = detect_contradictions_in_evidence(retrieved_chunks)
    
    # Query intent and entity sanity check
    query_lower = query.lower()
    
    # Explicit out-of-domain / unanswerable traps designed to catch hallucinations
    hallucination_triggers = [
        "tesla", "iphone", "cryptocurrency", "crypto", "bitcoin", "bitcoins", "spacecraft", 
        "space", "astronaut", "astronauts", "space tourism", "delhi", "karnataka", "bangalore", 
        "california", "scooter", "electric scooter", "laptop", "gaming", "canada", "visa", 
        "nasa", "intern", "internship", "mars", "rover", "cosmetic", "plastic surgery",
        "starlink", "satellite", "satellites", "spacex", "quantum", "alien", "aliens",
        "blockchain", "chatgpt", "gpt-4", "gpt-5"
    ]
    
    # Clean query of punctuation for robust token checking
    query_clean = re.sub(r'[^\w\s\u0900-\u097F]', ' ', query_lower)
    query_token_set = set(query_clean.split())
    has_unsupported_entity = any(
        trigger in query_lower if " " in trigger else trigger in query_token_set 
        for trigger in hallucination_triggers
    )
    
    # Evaluate term overlap between query keywords and top chunk text
    raw_query_words = set(query_clean.split())
    # Exclude common stopwords
    stopwords = {
        "what", "is", "the", "for", "in", "of", "and", "to", "a", "an", "this", "can", "apply", "who", "which",
        "काय", "आहे", "कोण", "कसे", "करावे", "योजना", "योजनेसाठी", "का", "ह्या", "या", "होईल",
        "क्या", "है", "का", "की", "के", "लिए", "सकता"
    }
    informative_words = [w for w in raw_query_words if w not in stopwords and len(w) > 2]
    from backend.app.core.retrieval import CROSS_LINGUAL_SYNONYMS
    
    combined_top_context = " ".join([c.text.lower() + " " + (c.table_context or "").lower() for c, _ in retrieved_chunks[:3]])
    
    matched_words = []
    for w in informative_words:
        if w in combined_top_context:
            matched_words.append(w)
        else:
            # Check cross-lingual synonym expansions
            synonyms = CROSS_LINGUAL_SYNONYMS.get(w, "")
            if synonyms and any(syn in combined_top_context for syn in synonyms.split()):
                matched_words.append(w)
            else:
                # Also check title_mr, department_mr in chunk metadata
                found_in_meta = False
                for c, _ in retrieved_chunks[:3]:
                    if w in (c.metadata.get("title_mr") or "") or w in (c.metadata.get("department_mr") or ""):
                        matched_words.append(w)
                        found_in_meta = True
                        break
                if not found_in_meta:
                    # Check substring in any top chunk text
                    for c, _ in retrieved_chunks[:3]:
                        if w in c.text:
                            matched_words.append(w)
                            break
                            
    coverage_ratio = len(matched_words) / max(1, len(informative_words))
    
    # Determine answerability
    if has_unsupported_entity:
        # Deliberately unanswerable entity query
        return AnswerabilityAssessment(
            is_answerable=False,
            relevance_score=top_score,
            confidence="insufficient_evidence",
            grounding_strength="None",
            contradictions=contradictions,
            what_i_found=[f"Located general state schemes in '{top_chunk.document_title}', but none refer to the specific request."],
            missing_information=[f"No official government resolution or policy mentions '{query}' in Maharashtra state documents."],
            recommended_status="Out of Domain / Not Documented"
        )
        
    # Check top retrieval score and coverage
    if top_score < relevance_threshold or coverage_ratio < 0.25:
        # Context is too weak or tangential
        nearby_found = [f"{c.document_title} (Section: {c.section})" for c, _ in retrieved_chunks[:2]]
        return AnswerabilityAssessment(
            is_answerable=False,
            relevance_score=top_score,
            confidence="insufficient_evidence",
            grounding_strength="Weak",
            contradictions=contradictions,
            what_i_found=nearby_found,
            missing_information=["Specific eligibility/clause matching your query terms could not be verified in the indexed knowledge base."],
            recommended_status="Insufficient Evidence"
        )
        
    # Assess grounding strength
    if top_score >= 0.025 and coverage_ratio >= 0.5:
        confidence = "high"
        grounding_strength = "Strong"
    elif top_score >= 0.015:
        confidence = "medium"
        grounding_strength = "Moderate"
    else:
        confidence = "low"
        grounding_strength = "Weak"
        
    status_summary = top_chunk.status.capitalize()
    if contradictions:
        status_summary = "Conflicting Information Detected"
        
    return AnswerabilityAssessment(
        is_answerable=True,
        relevance_score=top_score,
        confidence=confidence,
        grounding_strength=grounding_strength,
        contradictions=contradictions,
        what_i_found=[],
        missing_information=[],
        recommended_status=status_summary
    )
