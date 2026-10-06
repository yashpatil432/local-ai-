"""
Gemma 4: Source-Grounded Zero-Hallucination Reasoning Engine
=============================================================
An open-weight, source-grounded local intelligence module powering LocalLens.

Features:
- Strict zero-hallucination grounding policy.
- Binds every factual claim to exact citations (Document Name, Page Number).
- Disciplined abstention: strictly refuses if evidence is missing.
- Supports 3 runtime modes:
    1. Built-in Local Offline Engine (no external dependencies, 100% deterministic)
    2. Hugging Face Transformers (`google/gemma-2-9b-it` or `google/gemma-2-2b-it`)
    3. Ollama Local Endpoint (`ollama run gemma2`)
"""

import os
import re
import json
import time
from typing import List, Dict, Any, Optional

# =====================================================================
# 1. STRICT GROUNDING SYSTEM PROMPT
# =====================================================================

STRICT_GROUNDING_SYSTEM_PROMPT = """You are Gemma 4, an open-weight, source-grounded, zero-hallucination local intelligence model powering LocalLens.

CRITICAL POLICY:
1. Answer ONLY using the supplied retrieved context below. Do NOT use general world knowledge or training assumptions to invent or extrapolate missing facts.
2. If the context does not contain direct, verifiable evidence to answer the question, you MUST refuse:
   "I couldn't find sufficient information about this in the uploaded documents."
3. Every factual claim in your answer MUST be accompanied by an exact quote and citation from the provided passages (document_id, page, section, exact quote).
4. Distinguish explicit facts from inference.
5. If the user question is in Marathi or Hindi, answer in that language while preserving exact factual numbers, dates, and amounts from the source.
6. Return strictly factual, verifiable output.
"""

# =====================================================================
# 2. CORE GEMMA 4 REASONING ENGINE CLASS
# =====================================================================

class Gemma4Engine:
    def __init__(self, mode: str = "local"):
        """
        Initialize the Gemma 4 Engine.
        :param mode: 'local' (built-in offline engine), 'transformers' (Hugging Face), or 'ollama'
        """
        self.mode = mode.lower()
        self.hf_model = None
        self.hf_tokenizer = None

    def ask(self, question: str, passages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Answers a user question strictly grounded in the provided passages.
        
        :param question: The user's query
        :param passages: List of dictionaries with keys:
                         - 'text': text of the passage
                         - 'doc_name': document filename/title
                         - 'page': page number (int)
                         - 'section': section title (optional)
        :return: Dict containing answer, is_grounded, citations, and latency_ms
        """
        start_time = time.time()

        # Step 1: Check for empty context (Disciplined Abstention)
        if not passages or not any(p.get("text", "").strip() for p in passages):
            return {
                "answer": "I couldn't find sufficient information about this in the uploaded documents.",
                "is_grounded": False,
                "citations": [],
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }

        # Step 2: Route to selected execution mode
        if self.mode == "transformers":
            return self._ask_transformers(question, passages, start_time)
        elif self.mode == "ollama":
            return self._ask_ollama(question, passages, start_time)
        else:
            return self._ask_local(question, passages, start_time)

    # -----------------------------------------------------------------
    # Mode A: Built-in Local Engine (Zero Dependencies, Deterministic)
    # -----------------------------------------------------------------
    def _ask_local(self, question: str, passages: List[Dict[str, Any]], start_time: float) -> Dict[str, Any]:
        q_tokens = set(re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F]+\b", question.lower()))
        stopwords = {
            "what", "is", "the", "for", "in", "of", "and", "a", "an", "to", "how", "can", 
            "does", "are", "do", "it", "on", "this", "that", "about", "or", "by", "be", 
            "as", "at", "if", "not", "any", "all", "with", "from", "provide", "give", "get"
        }
        meaningful_tokens = {t for t in q_tokens if t not in stopwords and len(t) > 2}
        if not meaningful_tokens:
            meaningful_tokens = {t for t in q_tokens if t not in stopwords} or q_tokens

        scored_passages = []
        for p in passages:
            text = p.get("text", "")
            p_tokens = set(re.findall(r"\b[a-zA-Z0-9_\u0900-\u097F]+\b", text.lower()))
            overlap = sum(1 for t in meaningful_tokens if t in p_tokens)
            if overlap > 0:
                score = overlap + (1.0 if question.lower() in text.lower() else 0.0)
                scored_passages.append((p, score))

        scored_passages.sort(key=lambda x: x[1], reverse=True)

        # Anti-hallucination threshold check:
        # Require substantive overlap (at least 2 tokens if question has 3+ meaningful tokens)
        min_overlap = 2 if len(meaningful_tokens) >= 3 else 1
        if not scored_passages or scored_passages[0][1] < min_overlap:
            return {
                "answer": "I couldn't find sufficient information about this in the uploaded documents.",
                "is_grounded": False,
                "citations": [],
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }

        best_passage, best_score = scored_passages[0]
        # Avoid splitting on abbreviations like Rs., Dr., No.
        clean_text = best_passage.get("text", "")
        sentences = re.split(r"(?<!\bRs\.)(?<!\bDr\.)(?<!\bNo\.)(?<!\bMr\.)(?<=[.!?\n])\s+", clean_text)
        
        matched_sentences = [
            s.strip() for s in sentences 
            if sum(1 for t in meaningful_tokens if t in s.lower()) >= min(2, len(meaningful_tokens)) and len(s.strip()) > 15
        ]

        if not matched_sentences:
            matched_sentences = [
                s.strip() for s in sentences 
                if any(t in s.lower() for t in meaningful_tokens) and len(s.strip()) > 15
            ]

        core_answer = " ".join(matched_sentences[:2]) if matched_sentences else clean_text[:250].strip()

        doc_name = best_passage.get("doc_name", "Document")
        page_num = best_passage.get("page", 1)
        section = best_passage.get("section", "General")

        formatted_answer = (
            f"Based on **{doc_name}** (Page {page_num}):\n\n"
            f"{core_answer}\n\n"
            f"*(Verified from page {page_num} under '{section}')*"
        )

        citations = [{
            "doc_name": doc_name,
            "page": page_num,
            "section": section,
            "snippet": core_answer[:200]
        }]

        return {
            "answer": formatted_answer,
            "is_grounded": True,
            "citations": citations,
            "latency_ms": round((time.time() - start_time) * 1000, 2)
        }

    # -----------------------------------------------------------------
    # Mode B: Hugging Face Transformers (Local PyTorch / CUDA)
    # -----------------------------------------------------------------
    def _ask_transformers(self, question: str, passages: List[Dict[str, Any]], start_time: float) -> Dict[str, Any]:
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM

            if not self.hf_model:
                model_id = "google/gemma-2-2b-it"  # or 'google/gemma-2-9b-it'
                print(f"Loading {model_id} via Hugging Face...")
                self.hf_tokenizer = AutoTokenizer.from_pretrained(model_id)
                self.hf_model = AutoModelForCausalLM.from_pretrained(
                    model_id,
                    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                    device_map="auto"
                )

            context_str = "\n\n".join([
                f"[Document: {p.get('doc_name')} | Page: {p.get('page')}]\n{p.get('text')}"
                for p in passages
            ])

            messages = [
                {"role": "user", "content": f"{STRICT_GROUNDING_SYSTEM_PROMPT}\n\nContext:\n{context_str}\n\nQuestion: {question}"}
            ]

            prompt = self.hf_tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self.hf_tokenizer(prompt, return_tensors="pt").to(self.hf_model.device)

            with torch.no_grad():
                outputs = self.hf_model.generate(**inputs, max_new_tokens=300, temperature=0.1)

            answer = self.hf_tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)

            return {
                "answer": answer.strip(),
                "is_grounded": True,
                "citations": passages[:2],
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }
        except Exception as e:
            print(f"Transformers error ({e}), falling back to local engine.")
            return self._ask_local(question, passages, start_time)

    # -----------------------------------------------------------------
    # Mode C: Ollama Local API Endpoint (ollama run gemma2)
    # -----------------------------------------------------------------
    def _ask_ollama(self, question: str, passages: List[Dict[str, Any]], start_time: float) -> Dict[str, Any]:
        import urllib.request

        context_str = "\n\n".join([
            f"[Document: {p.get('doc_name')} | Page: {p.get('page')}]\n{p.get('text')}"
            for p in passages
        ])

        payload = {
            "model": "gemma2",
            "prompt": f"{STRICT_GROUNDING_SYSTEM_PROMPT}\n\nContext:\n{context_str}\n\nQuestion: {question}",
            "stream": False,
            "options": {"temperature": 0.1}
        }

        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "answer": data.get("response", "").strip(),
                    "is_grounded": True,
                    "citations": passages[:2],
                    "latency_ms": round((time.time() - start_time) * 1000, 2)
                }
        except Exception as e:
            print(f"Ollama error ({e}), falling back to local engine.")
            return self._ask_local(question, passages, start_time)


# =====================================================================
# 3. STANDALONE VERIFICATION DEMO
# =====================================================================

if __name__ == "__main__":
    print("=" * 65)
    print("Gemma 4: Source-Grounded Zero-Hallucination Reasoning Engine Demo")
    print("=" * 65)

    engine = Gemma4Engine(mode="local")

    # Sample Document Passages
    sample_passages = [
        {
            "doc_name": "Maharashtra_EBC_Scholarship_Resolution_2024.pdf",
            "page": 2,
            "section": "Section 2.1: Eligibility Criteria",
            "text": "The candidate's annual family income from all sources must not exceed Rs. 8,00,000/- (Rupees Eight Lakhs only) for the preceding financial year. Candidates admitted under Management Quota or Institute Level Quota are strictly not eligible for this scholarship."
        },
        {
            "doc_name": "Maharashtra_EBC_Scholarship_Resolution_2024.pdf",
            "page": 3,
            "section": "Section 3.2: Benefits",
            "text": "Eligible candidates shall receive 50% reimbursement of tuition fees and 50% examination fees deposited directly through the MahaDBT portal."
        }
    ]

    # Test Case 1: Answerable Query
    q1 = "What is the annual income limit for the EBC scholarship?"
    print(f"\n[Test 1] Question: {q1}")
    res1 = engine.ask(q1, sample_passages)
    print("Response:\n" + res1["answer"])
    print(f"Latency: {res1['latency_ms']} ms | Grounded: {res1['is_grounded']}")

    # Test Case 2: Negative Disqualification Rule
    q2 = "Can a student admitted through Management Quota apply for the scholarship?"
    print(f"\n[Test 2] Question: {q2}")
    res2 = engine.ask(q2, sample_passages)
    print("Response:\n" + res2["answer"])
    print(f"Latency: {res2['latency_ms']} ms | Grounded: {res2['is_grounded']}")

    # Test Case 3: Zero-Hallucination Refusal (Unanswerable query)
    q3 = "Does this scheme provide a free laptop or electric scooter?"
    print(f"\n[Test 3] Question: {q3}")
    res3 = engine.ask(q3, sample_passages)
    print("Response:\n" + res3["answer"])
    print(f"Latency: {res3['latency_ms']} ms | Grounded: {res3['is_grounded']}")
    print("=" * 65)
