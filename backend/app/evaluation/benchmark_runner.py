import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any

from backend.app.models.schemas import EvalQuestion, EvalResultItem, BenchmarkReport
from backend.app.core.retrieval import get_retriever, detect_language
from backend.app.core.answerability import assess_answerability
from backend.app.core.model_provider import get_model_provider

DATASET_PATH = os.path.join(os.path.dirname(__file__), "test_dataset.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "results.json")
METRICS_PATH = os.path.join(os.path.dirname(__file__), "metrics.json")

def load_test_dataset() -> List[EvalQuestion]:
    if not os.path.exists(DATASET_PATH):
        return []
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [EvalQuestion(**item) for item in data]

def run_benchmark_evaluation() -> BenchmarkReport:
    """
    Executes live evaluation of all 50 questions against the actual LocalLens engine.
    Calculates empirical metrics without hardcoding.
    """
    questions = load_test_dataset()
    if not questions:
        raise ValueError("Evaluation test dataset is empty or not found.")
        
    retriever = get_retriever()
    model_provider = get_model_provider("local")
    
    results: List[EvalResultItem] = []
    latencies: List[float] = []
    
    answerable_correct = 0
    total_answerable = 0
    citation_correct = 0
    evidence_recall_hits = 0
    grounded_count = 0
    hallucination_count = 0
    correct_abstention_count = 0
    total_unanswerable = 0
    
    for q in questions:
        start_t = time.time()
        
        # 1. Retrieval
        retrieved = retriever.search(q.question, top_k=5)
        retrieved_ids = [c.document_id for c, _ in retrieved]
        
        # 2. Answerability Gate
        assessment = assess_answerability(q.question, retrieved)
        
        # 3. Model Generation
        lang = detect_language(q.question)
        response = model_provider.generate_grounded_answer(
            question=q.question,
            retrieved_chunks=retrieved,
            assessment=assessment,
            detected_language=lang
        )
        
        latency = (time.time() - start_t) * 1000
        latencies.append(latency)
        
        actual_answerable = response.answerable
        
        # Metric Calculations
        is_correct = False
        is_grounded = False
        is_hallucination = False
        is_correct_abstention = False
        
        if not q.expected_answerable:
            total_unanswerable += 1
            if not actual_answerable:
                is_correct = True
                is_correct_abstention = True
                correct_abstention_count += 1
            else:
                # Answered an unanswerable query -> Hallucination!
                is_hallucination = True
                hallucination_count += 1
        else:
            total_answerable += 1
            if actual_answerable:
                # Check key facts presence in answer or why
                resp_text = (response.answer + " " + response.why_reasoning).lower()
                matches_fact = any(fact.lower() in resp_text for fact in q.expected_key_facts)
                
                # Check citation correctness
                source_overlap = any(s in retrieved_ids for s in q.expected_sources)
                if source_overlap:
                    evidence_recall_hits += 1
                    
                has_valid_citations = len(response.evidence) > 0 and any(e.document_id in q.expected_sources for e in response.evidence)
                if has_valid_citations:
                    citation_correct += 1
                    
                if matches_fact and source_overlap:
                    is_correct = True
                    answerable_correct += 1
                    
                if has_valid_citations and response.grounding_strength in ["Strong", "Moderate"]:
                    is_grounded = True
                    grounded_count += 1
            else:
                # Abstention on answerable query
                is_correct = False
                
        results.append(EvalResultItem(
            id=q.id,
            question=q.question,
            category=q.category,
            expected_answerable=q.expected_answerable,
            actual_answerable=actual_answerable,
            answer=response.answer,
            evidence_found=len(response.evidence),
            correct=is_correct,
            grounded=is_grounded,
            hallucination=is_hallucination,
            correct_abstention=is_correct_abstention,
            latency_ms=round(latency, 2),
            retrieved_sources=retrieved_ids
        ))

    # Compute final rates
    total_q = len(questions)
    ans_acc = round((answerable_correct + correct_abstention_count) / total_q * 100, 1)
    cit_acc = round(citation_correct / max(1, total_answerable) * 100, 1)
    rec_5 = round(evidence_recall_hits / max(1, total_answerable) * 100, 1)
    ground_score = round(grounded_count / max(1, total_answerable) * 100, 1)
    hal_rate = round(hallucination_count / max(1, total_unanswerable) * 100, 1)
    abst_acc = round(correct_abstention_count / max(1, total_unanswerable) * 100, 1)
    
    avg_lat = round(sum(latencies) / len(latencies), 1)
    sorted_lat = sorted(latencies)
    p95_lat = round(sorted_lat[int(len(sorted_lat) * 0.95)], 1)
    
    report = BenchmarkReport(
        total_questions=total_q,
        answerable_count=total_answerable,
        unanswerable_count=total_unanswerable,
        ambiguous_count=sum(1 for q in questions if q.category == "ambiguous"),
        multilingual_count=sum(1 for q in questions if q.category == "multilingual"),
        answer_accuracy=ans_acc,
        citation_accuracy=cit_acc,
        evidence_recall_at_5=rec_5,
        groundedness_score=ground_score,
        hallucination_rate=hal_rate,
        correct_abstention_rate=abst_acc,
        avg_latency_ms=avg_lat,
        p95_latency_ms=p95_lat,
        results=results,
        timestamp=datetime.now().isoformat()
    )
    
    # Save results to file
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump([r.model_dump() for r in results], f, indent=2, ensure_ascii=False)
        
    metrics_summary = report.model_dump()
    del metrics_summary["results"]
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2)
        
    return report

def get_latest_benchmark_report() -> Optional[BenchmarkReport]:
    if not os.path.exists(RESULTS_PATH) or not os.path.exists(METRICS_PATH):
        return None
    try:
        with open(METRICS_PATH, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        with open(RESULTS_PATH, "r", encoding="utf-8") as f:
            results_data = json.load(f)
        metrics["results"] = [EvalResultItem(**r) for r in results_data]
        return BenchmarkReport(**metrics)
    except Exception:
        return None
