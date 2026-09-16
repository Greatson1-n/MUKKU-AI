import json
import logging
import re
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from app.tools.calculator import calculate
from app.tools.datetime_tool import get_current_datetime
from app.tools.web_search import search_web, fetch_url
from app.services.rag_service import rag_service
from app.services.memory_service import memory_service
from app.services.ollama_service import ollama_service

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "name": "calculator",
        "description": "Perform mathematical calculations, arithmetic, square roots, powers, or percentages.",
        "ui_status": "Calculating...",
        "parameters": {"expression": "math expression to evaluate, e.g. 'sqrt(144) + 25 * 4'"}
    },
    {
        "name": "current_time",
        "description": "Get the current local date, time, day, or year.",
        "ui_status": "Checking local time...",
        "parameters": {}
    },
    {
        "name": "web_search",
        "description": "Search the internet for up-to-date information, news, or external web facts.",
        "ui_status": "Searching the web...",
        "parameters": {"query": "search query"}
    },
    {
        "name": "document_search",
        "description": "Search uploaded documents for specific content, citations, or references.",
        "ui_status": "Reading documents...",
        "parameters": {"query": "document search query"}
    },
    {
        "name": "memory_search",
        "description": "Search memories and stored facts about the user.",
        "ui_status": "Recalling memories...",
        "parameters": {"query": "memory query"}
    }
]

class ToolService:
    @staticmethod
    def _quick_pattern_match(user_message: str, web_search_enabled: bool, has_docs: bool) -> Optional[Dict[str, Any]]:
        """Fast regex/keyword matcher to avoid LLM inference latency when obvious."""
        msg = user_message.strip().lower()

        # Math patterns: "calculate 12 * 45", "what is 50 * 20", "sqrt(144)"
        math_match = re.search(r'(?:calculate|what is|compute)\s+([0-9\.\s\+\-\*\/\^\(\)\%sqrtpi]+)$', msg)
        if math_match and any(op in math_match.group(1) for op in ['+', '-', '*', '/', '^', '%', 'sqrt']):
            return {"tool": "calculator", "args": {"expression": math_match.group(1)}}

        if re.search(r'^(?:[0-9\.\s\+\-\*\/\^\(\)]+|sqrt\([0-9\.]+\))$', msg) and any(op in msg for op in ['+', '-', '*', '/', '^']):
            return {"tool": "calculator", "args": {"expression": msg}}

        # Time patterns: "what time is it", "current date", "what is today's date"
        if any(p in msg for p in ["what time is it", "current time", "what is the date", "today's date", "what day is today", "what year is it"]):
            return {"tool": "current_time", "args": {}}

        # URL fetch pattern: "fetch https://..." or "read https://..."
        url_match = re.search(r'https?://[^\s]+', user_message)
        if url_match and any(verb in msg for verb in ["fetch", "read", "summarize", "analyze", "look at", "check"]):
            return {"tool": "web_search", "args": {"url": url_match.group(0)}}

        return None

    @classmethod
    async def decide_tool(
        cls,
        user_message: str,
        web_search_enabled: bool = False,
        has_documents: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Determines if a tool is needed for the user message."""
        # 1. Fast match
        quick = cls._quick_pattern_match(user_message, web_search_enabled, has_documents)
        if quick:
            if quick["tool"] == "web_search" and not web_search_enabled and "url" not in quick.get("args", {}):
                pass
            else:
                return quick

        # 2. Structured JSON decision via Qwen2.5 3B
        available = ["calculator", "current_time"]
        if web_search_enabled:
            available.append("web_search")
        if has_documents:
            available.append("document_search")
        available.append("memory_search")

        decision_prompt = (
            f"You are a tool dispatcher. Available tools: {', '.join(available)}, or 'none'.\n"
            f"User query: \"{user_message}\"\n"
            "Rules:\n"
            "- If calculation/arithmetic is needed: {\"tool\": \"calculator\", \"args\": {\"expression\": \"<math>\"}}\n"
            "- If asking current date or time: {\"tool\": \"current_time\", \"args\": {}}\n"
            "- If asking about uploaded documents: {\"tool\": \"document_search\", \"args\": {\"query\": \"<keywords>\"}}\n"
            "- If asking what you remember about the user: {\"tool\": \"memory_search\", \"args\": {\"query\": \"<keywords>\"}}\n"
            "- If asking for real-time web info or URL: {\"tool\": \"web_search\", \"args\": {\"query\": \"<search query>\"}}\n"
            "- If normal conversation, coding, reasoning, or general knowledge: {\"tool\": \"none\", \"args\": {}}\n\n"
            "Respond strictly in JSON:"
        )

        try:
            raw_response = await ollama_service.generate(
                prompt=decision_prompt,
                format_type="json",
                options={"temperature": 0.0, "num_predict": 100}
            )
            data = json.loads(raw_response)
            tool_name = data.get("tool", "none")
            if tool_name in available:
                return {"tool": tool_name, "args": data.get("args", {})}
        except Exception as e:
            logger.debug(f"Tool decision skipped/failed: {e}")

        return None

    @classmethod
    async def execute_tool(
        cls,
        tool_name: str,
        args: Dict[str, Any],
        db: Session,
        user_id: str,
        document_ids: Optional[List[str]] = None
    ) -> Tuple[str, Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Executes the selected tool safely.
        Returns: (observation_text, ui_status, citations_list)
        """
        ui_status = "Processing tool..."
        citations = None

        if tool_name == "calculator":
            ui_status = "Calculating..."
            expr = args.get("expression", "")
            result = calculate(expr)
            observation = f"Calculator Result for '{expr}': {result}"

        elif tool_name == "current_time":
            ui_status = "Checking time..."
            observation = get_current_datetime()

        elif tool_name == "web_search":
            ui_status = "Searching the web..."
            url = args.get("url")
            if url:
                ui_status = f"Reading webpage {url}..."
                fetch_res = await fetch_url(url)
                observation = f"Webpage Content ({url}):\n{fetch_res['content']}"
                citations = [{"document_name": url, "page_number": 1, "chunk_index": 0, "snippet": fetch_res['content'][:200], "score": 1.0}]
            else:
                query = args.get("query", "")
                results = search_web(query, max_results=4)
                if results:
                    obs_lines = [f"Web Search Results for '{query}':"]
                    citations = []
                    for r in results:
                        obs_lines.append(f"- **{r['title']}**: {r['snippet']} (Source: {r['url']})")
                        citations.append({"document_name": r['title'], "page_number": 1, "chunk_index": 0, "snippet": r['snippet'], "score": 0.9, "url": r['url']})
                    observation = "\n".join(obs_lines)
                else:
                    observation = f"No web search results found for '{query}'."

        elif tool_name == "document_search":
            ui_status = "Searching documents..."
            query = args.get("query", "")
            chunks = await rag_service.search_relevant_chunks(db, query, user_id, document_ids=document_ids, top_k=4)
            if chunks:
                obs_lines = [f"Retrieved Document Content for '{query}':"]
                citations = []
                for c in chunks:
                    obs_lines.append(f"--- Source: {c['document_name']} (Page {c['page_number']}) ---\n{c['content']}")
                    citations.append({
                        "document_name": c["document_name"],
                        "page_number": c["page_number"],
                        "chunk_index": c["chunk_index"],
                        "snippet": c["content"][:200],
                        "score": c["score"]
                    })
                observation = "\n\n".join(obs_lines)
            else:
                observation = "No relevant content found in uploaded documents for this query."

        elif tool_name == "memory_search":
            ui_status = "Searching memories..."
            query = args.get("query", "")
            memories = await memory_service.get_relevant_memories(db, user_id, query, limit=5)
            if memories:
                observation = "Stored user memories:\n" + "\n".join(f"- {m}" for m in memories)
            else:
                observation = "No specific memories found for this query."

        else:
            observation = f"Unknown tool: {tool_name}"

        return observation, ui_status, citations

tool_service = ToolService()
