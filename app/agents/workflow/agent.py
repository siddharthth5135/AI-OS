import json
import time
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.agents.research.agent import ResearchAgent
from app.services.llm.gemini_client import get_llm_client
from app.services.llm.prompt_templates import WORKFLOW_SYSTEM_PROMPT
from app.services.llm.schemas import LLMStreamChunk

class WorkflowAgent(BaseAgent):
    agent_type = "workflow"
    system_prompt = WORKFLOW_SYSTEM_PROMPT

    async def execute(self, query: str, context: AgentContext, stream: bool = False) -> Any:
        """
        Executes a multi-step workflow.
        1. Breaks the query into 2-4 steps as a JSON plan.
        2. Parses the JSON. Fallback to a single Research step on error.
        3. Formats the workflow plan details.
        4. Runs step 1 using ResearchAgent.
        5. Returns or streams the results.
        """
        start_time = time.time()
        llm = get_llm_client()

        plan_prompt = f'Break into 2-4 steps as JSON: {{"steps":[{{"step":1,"action":"research","query":"..."}}]}}\nTask: {query}'
        
        plan_resp = await llm.generate(plan_prompt, system_prompt=self.system_prompt)
        
        try:
            clean_text = plan_resp.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            plan = json.loads(clean_text)
            steps = plan.get("steps", [])
            if not steps:
                raise ValueError("No steps found in workflow plan.")
        except Exception:
            steps = [{"step": 1, "action": "research", "query": query}]

        response = "**Workflow Plan:**\n"
        for s in steps:
            action = s.get("action", "research")
            step_query = s.get("query", query)
            response += f"- Step {s.get('step', 1)}: {action} — {step_query[:80]}\n"
        response += "\n**Executing Step 1:**\n"

        if stream:
            async def workflow_stream_generator():
                yield LLMStreamChunk(text=response, is_final=False)
                research_agent = ResearchAgent()
                sub_stream = await research_agent.execute(steps[0]["query"], context, stream=True)
                async for chunk in sub_stream:
                    yield chunk
            return workflow_stream_generator()

        research_agent = ResearchAgent()
        sub = await research_agent.execute(steps[0]["query"], context, stream=False)
        elapsed_ms = int((time.time() - start_time) * 1000)

        return AgentResult(
            response=response + sub.response,
            agent_type=self.agent_type,
            tokens_used=(plan_resp.total_tokens or 0) + (sub.tokens_used or 0),
            latency_ms=elapsed_ms,
            confidence=0.9,
            sources=sub.sources,
            metadata={"steps": len(steps)}
        )
