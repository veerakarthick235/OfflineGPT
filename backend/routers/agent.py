"""
Agent Router — /api/agent/*

Endpoints:
  GET  /api/agent/tools          — list all registered tools
  POST /api/agent/classify       — classify a message without executing
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from ..services.agent import planner

router = APIRouter(prefix="/api/agent", tags=["agent"])


class ClassifyRequest(BaseModel):
    message:   str
    model:     str = "llama3.2"
    doc_count: int = 0


@router.get("/tools")
async def list_tools():
    """List all registered agent tools."""
    return {"tools": planner.list_tools(), "count": len(planner.list_tools())}


@router.post("/classify")
async def classify_intent(req: ClassifyRequest):
    """
    Classify a user message and return the tool plan.
    Useful for debugging and testing the intent classifier.
    """
    tool_plan = await planner.plan(req.message, model=req.model, doc_count=req.doc_count)
    return {
        "message":    req.message,
        "tool":       tool_plan.tool_name,
        "params":     tool_plan.params,
        "confidence": tool_plan.confidence,
        "reasoning":  tool_plan.reasoning,
        "stage":      tool_plan.stage,
    }
