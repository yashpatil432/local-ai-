import sys
import os

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add workspace to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.retrieval import get_retriever, detect_language
from backend.app.core.answerability import assess_answerability
from backend.app.core.model_provider import get_model_provider
from backend.app.models.schemas import QueryRequest
from backend.app.evaluation.benchmark_runner import run_benchmark_evaluation
from backend.app.main import initialize_knowledge_base

def test_pipeline():
    print("=== Testing LocalLens Backend Pipeline ===")
    
    # 1. Initialize
    initialize_knowledge_base()
    retriever = get_retriever()
    print(f"Total documents: {len(retriever.documents_metadata)}")
    print(f"Total chunks indexed: {len(retriever.chunks)}")
    assert len(retriever.documents_metadata) >= 10, "Failed to load 10 documents"
    assert len(retriever.chunks) >= 20, "Failed to generate chunks"
    
    # 2. Test Answerable Query
    q1 = "What is the annual income limit for the EBC scholarship in Maharashtra?"
    print(f"\n--- Test 1: Answerable Query: '{q1}' ---")
    retrieved = retriever.search(q1, top_k=3)
    assert len(retrieved) > 0, "Retrieval returned no chunks"
    print(f"Top chunk: {retrieved[0][0].document_title} (Page {retrieved[0][0].page}, Score: {retrieved[0][1]:.4f})")
    
    assessment = assess_answerability(q1, retrieved)
    print(f"Answerability: {assessment.is_answerable}, Grounding: {assessment.grounding_strength}")
    assert assessment.is_answerable == True, "Failed answerability check"
    
    provider = get_model_provider("local")
    resp = provider.generate_grounded_answer(q1, retrieved, assessment, "en")
    print(f"Answer: {resp.answer}")
    print(f"Citations: {len(resp.evidence)} (Page {resp.evidence[0].page})")
    assert resp.answerable == True
    assert "8,00,000" in resp.answer or "Eight Lakh" in resp.answer
    
    # 3. Test Unanswerable Query (Strict Zero-Hallucination Abstention)
    q2 = "Does Maharashtra offer a free Tesla electric vehicle scheme for agricultural pump owners?"
    print(f"\n--- Test 2: Unanswerable Query: '{q2}' ---")
    retrieved2 = retriever.search(q2, top_k=3)
    assessment2 = assess_answerability(q2, retrieved2)
    print(f"Answerability: {assessment2.is_answerable}, Status: {assessment2.recommended_status}")
    assert assessment2.is_answerable == False, "Abstention gate should refuse this query!"
    
    resp2 = provider.generate_grounded_answer(q2, retrieved2, assessment2, "en")
    print(f"Answer: {resp2.answer}")
    print(f"Missing Info: {resp2.missing_information}")
    assert resp2.answerable == False
    assert resp2.confidence == "insufficient_evidence"
    
    # 4. Test Multilingual Marathi Query
    q3 = "मुख्यमंत्री माझी लाडकी बहीण योजनेसाठी वयाची अट काय आहे?"
    print(f"\n--- Test 3: Marathi Query: '{q3}' ---")
    lang = detect_language(q3)
    print(f"Detected language: {lang}")
    assert lang in ["mr", "mr_latin"], f"Expected Marathi, got {lang}"
    
    retrieved3 = retriever.search(q3, top_k=3)
    assessment3 = assess_answerability(q3, retrieved3)
    resp3 = provider.generate_grounded_answer(q3, retrieved3, assessment3, lang)
    print(f"Answer (Marathi): {resp3.answer}")
    assert resp3.answerable == True
    assert "२१" in resp3.answer or "65" in resp3.answer or "६५" in resp3.answer
    
    # 5. Test Contradiction Detection (v1.0 vs v2.1)
    q4 = "What was the application deadline in the June 2024 order of Ladki Bahin Yojna vs current resolution?"
    print(f"\n--- Test 4: Contradiction Detection: '{q4}' ---")
    retrieved4 = retriever.search(q4, top_k=5)
    assessment4 = assess_answerability(q4, retrieved4)
    print(f"Contradictions found: {len(assessment4.contradictions)}")
    if assessment4.contradictions:
        print(f"Contradiction alert: {assessment4.contradictions[0].description}")
        print(f"Guidance: {assessment4.contradictions[0].guidance}")
    
    # 6. Run Benchmark Evaluation Suite (50 questions)
    print("\n--- Test 5: Running 50-Question Benchmark Suite ---")
    report = run_benchmark_evaluation()
    print(f"Total Questions Evaluated: {report.total_questions}")
    print(f"Answer Accuracy: {report.answer_accuracy}%")
    print(f"Citation Accuracy: {report.citation_accuracy}%")
    print(f"Evidence Recall@5: {report.evidence_recall_at_5}%")
    print(f"Groundedness Score: {report.groundedness_score}%")
    print(f"Hallucination Rate: {report.hallucination_rate}%")
    print(f"Correct Abstention Rate: {report.correct_abstention_rate}%")
    print(f"Average Latency: {report.avg_latency_ms} ms")
    
    assert report.total_questions == 50, "Expected 50 questions evaluated"
    assert report.hallucination_rate == 0.0, f"Expected 0% hallucination rate, got {report.hallucination_rate}%"
    assert report.correct_abstention_rate == 100.0, f"Expected 100% abstention rate, got {report.correct_abstention_rate}%"
    assert report.answer_accuracy >= 90.0, f"Expected >= 90% accuracy, got {report.answer_accuracy}%"
    
    print("\n✅ ALL BACKEND AND BENCHMARK TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_pipeline()
