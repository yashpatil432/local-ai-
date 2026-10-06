from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class DocumentMetadata(BaseModel):
    id: str
    title: str
    title_mr: Optional[str] = None
    department: str
    department_mr: Optional[str] = None
    gr_number: Optional[str] = None
    source: str
    publication_date: str
    last_updated_date: Optional[str] = None
    language: str = "en"
    document_type: str = "Government Resolution (GR)"
    region: str = "Maharashtra State"
    category: str = "Citizen Services"
    url: Optional[str] = None
    version: str = "v1.0"
    status: str = "current"  # "current", "older", "outdated"
    total_pages: int = 1
    file_path: Optional[str] = None

class Chunk(BaseModel):
    id: str
    document_id: str
    document_title: str
    department: str
    page: int
    section: str
    language: str
    published: str
    last_updated: Optional[str] = None
    status: str
    text: str
    table_context: Optional[str] = None
    char_start: int = 0
    char_end: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EvidencePassage(BaseModel):
    document_id: str
    document_title: str
    department: str
    page: int
    section: str
    quote: str
    source_url: Optional[str] = None
    status: str = "current"
    published: str = ""
    last_updated: Optional[str] = None
    relevance_score: float = 0.0

class ContradictionItem(BaseModel):
    detected: bool
    description: str
    source_a: Dict[str, Any]
    source_b: Dict[str, Any]
    guidance: str

class QueryRequest(BaseModel):
    question: str
    language: Optional[str] = "auto"
    category_filter: Optional[str] = None
    department_filter: Optional[str] = None
    status_filter: Optional[str] = None
    top_k: int = 5
    model_provider: Optional[str] = "gemma-4"

class QueryResponse(BaseModel):
    answerable: bool
    answer: str
    why_reasoning: str
    key_points: List[str] = Field(default_factory=list)
    evidence: List[EvidencePassage] = Field(default_factory=list)
    confidence: str  # "high", "medium", "low", "insufficient_evidence"
    grounding_strength: str  # "Strong", "Moderate", "Weak", "None"
    contradictions: List[ContradictionItem] = Field(default_factory=list)
    related_questions: List[str] = Field(default_factory=list)
    document_status: str  # "Current", "Older document", "Potentially outdated", "Multiple versions"
    detected_language: str = "en"
    latency_ms: float = 0.0
    what_i_found: Optional[List[str]] = None
    missing_information: Optional[List[str]] = None

class CompareRequest(BaseModel):
    question: str

class CompareResponse(BaseModel):
    question: str
    generic_llm: Dict[str, Any]
    locallens: Dict[str, Any]
    why_local_grounding_wins: str

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    category: Optional[str] = None
    department: Optional[str] = None

class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    department: str
    page: int
    section: str
    snippet: str
    relevance_score: float
    status: str
    published: str
    source_url: Optional[str] = None

class IngestionRequest(BaseModel):
    title: str
    title_mr: Optional[str] = None
    department: str
    category: str
    language: str = "en"
    publication_date: str
    version: str = "v1.0"
    content: str
    document_type: str = "Policy Guidelines"
    source_url: Optional[str] = None

class IngestionTelemetry(BaseModel):
    step: str
    status: str
    details: str
    timestamp: str

class IngestionResponse(BaseModel):
    success: bool
    document_id: str
    chunks_indexed: int
    telemetry: List[IngestionTelemetry]

class EvalQuestion(BaseModel):
    id: str
    question: str
    question_mr: Optional[str] = None
    category: str  # "answerable", "unanswerable", "ambiguous", "multilingual"
    expected_answerable: bool
    expected_sources: List[str] = Field(default_factory=list)
    expected_key_facts: List[str] = Field(default_factory=list)

class EvalResultItem(BaseModel):
    id: str
    question: str
    category: str
    expected_answerable: bool
    actual_answerable: bool
    answer: str
    evidence_found: int
    correct: bool
    grounded: bool
    hallucination: bool
    correct_abstention: bool
    latency_ms: float
    retrieved_sources: List[str] = Field(default_factory=list)

class BenchmarkReport(BaseModel):
    total_questions: int
    answerable_count: int
    unanswerable_count: int
    ambiguous_count: int
    multilingual_count: int
    answer_accuracy: float
    citation_accuracy: float
    evidence_recall_at_5: float
    groundedness_score: float
    hallucination_rate: float
    correct_abstention_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    results: List[EvalResultItem] = Field(default_factory=list)
    timestamp: str

class ChatbotMessageRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)
    session_id: Optional[str] = "default-session"

class ChatbotMessageResponse(BaseModel):
    reply: str
    model_used: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    is_grounded: bool = False
    latency_ms: float = 0.0
    success: bool = True
