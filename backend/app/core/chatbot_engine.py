"""
LocalLens Gemma 4 Conversational Chatbot Engine
================================================
Orchestrates multi-turn grounded conversations with Google Gemma 4 and Gemini models,
seamlessly integrated with hybrid BM25 retrieval over official Maharashtra Government
Resolutions (GRs) and user-uploaded documents.
"""

import os
import re
import json
import time
import requests
from typing import List, Dict, Any, Optional, Tuple

from backend.app.core.env_loader import get_gemini_api_key, get_merged_ca_bundle
from backend.app.core.retrieval import get_retriever, detect_language
from backend.app.core.user_documents import get_user_document_store

# System instruction for Gemma 4 Chatbot
CHATBOT_SYSTEM_INSTRUCTION = """You are LocalLens AI, an intelligent, authoritative, and source-grounded assistant for Maharashtra Government Schemes, Citizen Services, and official resolutions (GRs), powered by Google Gemma 4 architecture.

GUIDELINES:
1. When answering questions regarding government schemes, quotas, benefits, income criteria, or legal deadlines, prioritize the provided official context.
2. Always cite the exact source document title, page number, and section whenever available.
3. If the user greets or asks general conversational questions ("Hello", "Who are you?", "What can you do?"), respond warmly, professionally, and concisely explaining your capabilities.
4. Support English, Marathi (मराठी), and Hindi (हिंदी) natively. If the user asks in Marathi or Hindi, reply fluently in that language while preserving exact factual figures, amounts, and dates.
5. If the context does not contain sufficient details to verify a specific legal or statutory rule, acknowledge what is verified and advise checking the official state portal (Aaple Sarkar / MahaDBT).
6. Provide direct, beautifully structured markdown responses with bullet points where appropriate. DO NOT output internal reasoning drafts, options analysis, or planning notes.
"""


def clean_reasoning_artifacts(text: str) -> str:
    """
    Strips internal thinking/reasoning tags if produced by reasoning models.
    """
    if not text:
        return ""
    cleaned = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL).strip()
    return cleaned if cleaned else text.strip()


class Gemma4ChatbotEngine:
    def __init__(self):
        self.api_key = get_gemini_api_key()
        self.ca_bundle = get_merged_ca_bundle()
        # Candidate model hierarchy: ultra-fast low-latency Gemini Flash Lite first, then Gemma 4
        self.models_priority = [
            "models/gemini-flash-lite-latest",
            "models/gemini-3.5-flash",
            "models/gemma-4-26b-a4b-it",
            "models/gemini-3.1-flash-lite"
        ]

    def is_api_active(self) -> bool:
        self.api_key = get_gemini_api_key()
        return bool(self.api_key and len(self.api_key) > 10)

    def generate_chat_response(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes hybrid retrieval over official GRs + user docs, constructs grounded prompt,
        and generates response using Gemma 4 / Gemini API with fallback.
        """
        start_time = time.time()
        self.api_key = get_gemini_api_key()
        self.ca_bundle = get_merged_ca_bundle()

        # Step 1: Detect Language
        lang = detect_language(user_message)

        # Step 2: Hybrid Retrieval (Official KB + User Uploaded Docs)
        citations: List[Dict[str, Any]] = []
        retrieved_context_blocks: List[str] = []

        try:
            # Search official 10 Maharashtra GRs
            retriever = get_retriever()
            if not retriever.chunks:
                from backend.app.main import initialize_knowledge_base
                initialize_knowledge_base()

            kb_chunks = retriever.search(user_message, top_k=6)
            for chunk, score in kb_chunks:
                if score > 0.015:
                    retrieved_context_blocks.append(
                        f"[OFFICIAL GR: {chunk.document_title} | PAGE: {chunk.page} | SECTION: {chunk.section}]\n{chunk.text}"
                    )
                    citations.append({
                        "doc_id": chunk.document_id,
                        "title": chunk.document_title,
                        "page": chunk.page,
                        "section": chunk.section,
                        "snippet": chunk.text[:200] + ("..." if len(chunk.text) > 200 else ""),
                        "type": "official_gr"
                    })
        except Exception as e:
            print("KB retrieval warning in chatbot:", e)

        # Search user-uploaded documents if session_id is active
        if session_id:
            try:
                user_doc_store = get_user_document_store()
                user_docs_response = user_doc_store.query(session_id, user_message)
                if user_docs_response and user_docs_response.is_sufficient:
                    for cit in user_docs_response.citations[:2]:
                        retrieved_context_blocks.append(
                            f"[USER UPLOADED DOC: {cit.doc_name} | PAGE: {cit.page_number} | HEADING: {cit.heading}]\n{cit.snippet}"
                        )
                        citations.append({
                            "doc_id": cit.doc_id,
                            "title": cit.doc_name,
                            "page": cit.page_number,
                            "section": cit.heading,
                            "snippet": cit.snippet,
                            "type": "user_doc"
                        })
            except Exception as e:
                print("User doc retrieval warning in chatbot:", e)

        context_str = "\n\n".join(retrieved_context_blocks)

        # Step 3: Check if API key is present
        if not self.is_api_active():
            # Return deterministic grounded local answer
            return self._generate_local_fallback(
                user_message, citations, context_str, lang, start_time
            )

        # Step 4: Construct multi-turn contents payload for Google GenAI REST API
        contents = []
        if conversation_history:
            for turn in conversation_history[-6:]:
                role = "user" if turn.get("role") in ["user", "human"] else "model"
                text = turn.get("content", "").strip()
                if text:
                    contents.append({
                        "role": role,
                        "parts": [{"text": text}]
                    })

        # Append current user prompt with injected grounding context
        user_prompt_with_context = user_message
        if context_str:
            user_prompt_with_context = (
                f"{user_message}\n\n"
                f"[GROUNDING VERIFIED CONTEXT FROM OFFICIAL DOCUMENTS]:\n{context_str}\n\n"
                f"Please cite relevant sources directly in your response."
            )

        contents.append({
            "role": "user",
            "parts": [{"text": user_prompt_with_context}]
        })

        payload = {
            "system_instruction": {
                "parts": [{"text": CHATBOT_SYSTEM_INSTRUCTION}]
            },
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 800,
                "topP": 0.95
            }
        }

        # Step 5: Try Candidate Models
        last_error = None
        for model_name in self.models_priority:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={self.api_key}"
            try:
                resp = requests.post(
                    url,
                    json=payload,
                    verify=self.ca_bundle,
                    timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_reply = parts[0]["text"]
                            clean_reply = clean_reasoning_artifacts(raw_reply)
                            latency = round((time.time() - start_time) * 1000, 2)
                            
                            display_model = "Gemma 4" if "gemma" in model_name else "Gemini Flash"
                            return {
                                "reply": clean_reply,
                                "model_used": f"{display_model} ({model_name.replace('models/', '')})",
                                "citations": citations,
                                "is_grounded": len(citations) > 0,
                                "latency_ms": latency,
                                "success": True
                            }
                else:
                    last_error = f"{model_name} HTTP {resp.status_code}: {resp.text[:120]}"
            except Exception as ex:
                last_error = f"{model_name} Exception: {str(ex)}"

        # If all API calls timed out or failed, fall back safely to local deterministic engine
        print("Chatbot API failover triggered:", last_error)
        return self._generate_local_fallback(
            user_message, citations, context_str, lang, start_time, note=last_error
        )

    def _generate_local_fallback(
        self,
        user_message: str,
        citations: List[Dict[str, Any]],
        context_str: str,
        lang: str,
        start_time: float,
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Local deterministic grounded synthesis if offline or API is unreachable.
        """
        q_lower = user_message.lower()

        # Greetings & General queries
        if any(w in q_lower for w in ["hi", "hello", "hey", "who are you", "what can you do", "नमस्कार", "नमस्ते"]):
            if lang in ["mr", "mr_latin"]:
                reply = (
                    "नमस्कार! मी **LocalLens AI** आहे — महाराष्ट्र शासनाचे अधिकृत शासन निर्णय (GRs) "
                    "आणि योजनांची पडताळणीकृत माहिती देणारा सुरक्षित सहाय्यक. तुम्ही शिष्यवृत्ती, "
                    "लाडकी बहीण योजना, आरोग्य विमा (MJPJAY), किंवा अपलोड केलेल्या PDF कागदपत्रांबद्दल विचारू शकता."
                )
            else:
                reply = (
                    "Hello! I am **LocalLens AI**, powered by Gemma 4 architecture. "
                    "I provide verified, source-grounded guidance on Maharashtra Government Resolutions (GRs), "
                    "citizen welfare schemes (EBC Scholarship, Majhi Ladki Bahin, MJPJAY, RTS Act), "
                    "and any documents you upload."
                )
            return {
                "reply": reply,
                "model_used": "LocalLens Rule Engine (Deterministic)",
                "citations": citations,
                "is_grounded": True,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "success": True
            }

        # Grounded answer if citations present
        if citations:
            best = citations[0]
            if lang in ["mr", "mr_latin"]:
                reply = (
                    f"**{best['title']}** (पृष्ठ {best['page']}, {best['section']}) नुसार:\n\n"
                    f"{best['snippet']}\n\n"
                    f"*(अधिकृत शासन निर्णयानुसार पडताळणीकृत)*"
                )
            else:
                reply = (
                    f"According to **{best['title']}** (Page {best['page']}, Section '{best['section']}'):\n\n"
                    f"{best['snippet']}\n\n"
                    f"*(Verified from official state resolution)*"
                )
            return {
                "reply": reply,
                "model_used": "LocalLens Grounded Engine",
                "citations": citations,
                "is_grounded": True,
                "latency_ms": round((time.time() - start_time) * 1000, 2),
                "success": True
            }

        # Strict Refusal if no citations found
        if lang in ["mr", "mr_latin"]:
            refusal = "उपलब्ध अधिकृत शासकीय दस्तऐवजांमध्ये याबद्दल पुरेशी माहिती सापडली नाही."
        else:
            refusal = "I couldn't find sufficient verified information about this in the official documents."

        return {
            "reply": refusal,
            "model_used": "LocalLens Zero-Hallucination Guard",
            "citations": [],
            "is_grounded": False,
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "success": True
        }


# Global singleton instance
_chatbot_engine = Gemma4ChatbotEngine()

def get_chatbot_engine() -> Gemma4ChatbotEngine:
    return _chatbot_engine
