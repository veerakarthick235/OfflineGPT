"""
SSE streaming chat endpoint — Phase 3: Agentic Tool Calling.

POST /api/chat/stream

Flow:
  1. Validate conversation + persist user message
  2. Build Hierarchical Memory context (Phase 2)
  3. Agent Planner: classify intent → ToolPlan (Phase 3)
  4. Execute tool if needed (RAG / Image / Calculator / DateTime / Memory)
     → stream tool_start / tool_result / tool_error events
  5. Inject tool context into system prompt
  6. Ollama streaming inference
  7. Persist AI message
  8. Background: extract facts, summarize (Phase 2 memory)
  9. Auto-title on first turn
"""
import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..schemas import ChatRequest
from ..services import sqlite_db, chroma_db, ollama as ol
from ..services.image.manager import get_manager
from ..services import image_library as lib
from ..services.memory import manager as memory_mgr
from ..services.agent import planner as agent_planner
from ..services.agent import executor as agent_executor
from ..services.attachments.pipeline import build_attachment_context

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _stream_image_caption(model: str, prompt: str) -> AsyncIterator[str]:
    system = ("You are a helpful assistant. The image has already been generated. "
              "Respond in 1-2 sentences confirming what you created.")
    messages = [
        {"role": "system", "content": system},
        {"role": "user",   "content": f"I asked you to: {prompt}. Confirm what you generated."},
    ]
    async for chunk in ol.stream_chat(model, messages, temperature=0.5, max_tokens=120):
        yield chunk


# ── Main generator ─────────────────────────────────────────────────────

async def _generate(req: ChatRequest) -> AsyncIterator[str]:

    # 1. Validate + load conversation
    conv = await sqlite_db.get_conversation(req.conversation_id)
    if not conv:
        yield await _sse({"type": "error", "content": "Conversation not found"})
        return

    # 2. Persist user message
    user_msg = await sqlite_db.add_message(
        req.conversation_id, "user", req.content,
        tokens=len(req.content) // 4,
    )
    yield await _sse({"type": "user_message", "message": user_msg})

    try:
        chroma_db.add_message(
            user_msg["id"], req.content,
            req.conversation_id, conv["title"],
            "user", user_msg["created_at"],
        )
    except Exception:
        pass

    model = req.model or conv.get("model", "llama3.2")

    # Reload conv with all messages
    conv = await sqlite_db.get_conversation(req.conversation_id)
    raw_messages = [{"role": m["role"], "content": m["content"]} for m in conv["messages"]]

    # ── Phase 6: Attachment context ───────────────────────────────
    attachment_context = ""
    if req.attachment_ids:
        yield await _sse({
            "type":  "tool_start",
            "tool":  "attachment",
            "icon":  "📎",
            "label": f"Reading {len(req.attachment_ids)} attachment(s)…",
        })
        try:
            attachment_context = await build_attachment_context(
                req.attachment_ids, req.content
            )
            yield await _sse({
                "type":    "tool_result",
                "tool":    "attachment",
                "icon":    "📎",
                "success": True,
                "label":   f"{len(req.attachment_ids)} file(s) loaded",
            })
        except Exception as e:
            print(f"[Chat] Attachment context error: {e}")
            attachment_context = f"[Could not load attachment context: {e}]"
    # ── 3. Hierarchical Memory context (Phase 2) ──────────────────────
    mem = await memory_mgr.build_context(
        query           = req.content,
        conversation_id = req.conversation_id,
        messages        = raw_messages,
        model           = model,
    )

    # ── 4. Agent Planning (Phase 3) ───────────────────────────────────
    doc_count = len(await sqlite_db.list_documents())
    tool_plan = await agent_planner.plan(
        user_message = req.content,
        model        = model,
        doc_count    = doc_count,
    )

    tool_context   = ""    # injected into prompt if a tool returns context
    full_content   = ""
    ai_msg         = None
    image_generated = False

    # ── 5. Execute tool if planned ────────────────────────────────────
    if tool_plan.tool_name:

        # Special case: image_generate → full image SSE flow
        if tool_plan.tool_name == "image_generate":
            prompt = tool_plan.params.get("prompt", req.content)

            yield await _sse({
                "type":    "tool_start",
                "tool":    "image_generate",
                "icon":    "🎨",
                "label":   f"Generating image: {prompt[:60]}…",
            })
            yield await _sse({
                "type":    "image_generating",
                "prompt":  prompt,
                "message": f"Generating image: {prompt}",
            })

            try:
                manager = get_manager()
                result  = await manager.generate(prompt=prompt)

                yield await _sse({
                    "type":    "tool_result",
                    "tool":    "image_generate",
                    "icon":    "🎨",
                    "success": True,
                    "label":   "Image generated",
                })
                yield await _sse({
                    "type":     "image_done",
                    "url":      result.url,
                    "filename": result.filename,
                    "prompt":   result.prompt,
                    "width":    result.width,
                    "height":   result.height,
                    "provider": result.provider,
                    "model_id": result.model_id,
                    "seed":     result.seed,
                })

                # Save to library
                try:
                    from pathlib import Path as _P
                    _size = _P(result.path).stat().st_size if _P(result.path).exists() else 0
                    await lib.add_image(
                        filename=result.filename, prompt=result.prompt,
                        model_id=result.model_id, provider=result.provider,
                        width=result.width, height=result.height,
                        steps=result.steps, seed=result.seed, file_bytes=_size,
                    )
                except Exception as _e:
                    print(f"[WARN] library save: {_e}")

                # Caption
                full_content = ""
                try:
                    async for chunk in _stream_image_caption(model, prompt):
                        full_content += chunk
                        yield await _sse({"type": "chunk", "content": chunk})
                        await asyncio.sleep(0)
                except Exception:
                    full_content = f"Here is your generated image of: **{prompt}**"
                    yield await _sse({"type": "chunk", "content": full_content})

                full_content = f"![generated]({result.url})\n\n{full_content}"
                image_generated = True

            except RuntimeError as e:
                yield await _sse({
                    "type":    "tool_error",
                    "tool":    "image_generate",
                    "message": str(e),
                })
                full_content = (
                    f"I can generate images, but no image model is loaded yet.\n\n"
                    f"> **{e}**\n\n"
                    "Open **Models → Image Models** to download one."
                )
                yield await _sse({"type": "chunk", "content": full_content})

            except Exception as e:
                full_content = f"Image generation failed: {e}"
                yield await _sse({"type": "chunk", "content": full_content})

            ai_msg = await sqlite_db.add_message(
                req.conversation_id, "assistant", full_content,
                tokens=len(full_content) // 4,
            )

        else:
            # All other tools — execute and collect context
            async for sse_str, tool_result in agent_executor.execute(
                tool_plan, model=model, doc_ids=None
            ):
                yield sse_str
                if tool_result is not None:
                    if tool_result.success and tool_result.context:
                        tool_context = tool_result.context
                    elif not tool_result.success and tool_result.error:
                        # Inform the AI that the tool failed
                        tool_context = f"[Tool Error: {tool_result.error}]"

    # ── 6. Ollama inference (if not a pure image generation) ──────────
    if not image_generated:
        api_msgs = []

        # Build system prompt with memory + tool context
        base_system = conv.get("system_prompt", "").strip() or "You are a helpful, knowledgeable AI assistant."

        system_parts = [base_system]

        if mem["memory_block"]:
            system_parts.append(
                "═══ MEMORY ════════════════════════════════\n"
                + mem["memory_block"] +
                "\n══════════════════════════════════════════"
            )

        if attachment_context:
            system_parts.append(
                "═══ ATTACHED FILES ══════════════════════\n"
                + attachment_context +
                "\n═══════════════════════════════════════"
            )

        if tool_context:
            system_parts.append(
                "═══ TOOL RESULTS ═══════════════════════════\n"
                + tool_context +
                "\n═══════════════════════════════════════════\n"
                "Use the above tool results to answer the user's question accurately. "
                "Cite the source when referencing document content."
            )

        # If tool failed / returned error context, still let AI respond naturally
        api_msgs.append({"role": "system", "content": "\n\n".join(system_parts)})

        # Add trimmed conversation history
        for m in mem["trimmed_messages"]:
            if m.get("role") != "system":
                api_msgs.append({"role": m["role"], "content": m["content"]})

        # Stream
        full_content = ""
        try:
            async for chunk in ol.stream_chat(model, api_msgs, req.temperature, req.max_tokens):
                full_content += chunk
                yield await _sse({"type": "chunk", "content": chunk})
                await asyncio.sleep(0)
        except Exception as exc:
            yield await _sse({"type": "error", "content": str(exc)})
            return

        ai_msg = await sqlite_db.add_message(
            req.conversation_id, "assistant", full_content,
            tokens=len(full_content) // 4,
        )

        try:
            chroma_db.add_message(
                ai_msg["id"], full_content,
                req.conversation_id, conv["title"],
                "assistant", ai_msg["created_at"],
            )
        except Exception:
            pass

        # ── 8. Background memory tasks ─────────────────────────────────
        all_msgs = raw_messages + [{"role": "assistant", "content": full_content}]
        asyncio.create_task(memory_mgr.post_turn_tasks(req.conversation_id, all_msgs, model))

    # ── 9. Auto-title on first turn ───────────────────────────────────
    user_msgs_count = len([m for m in conv["messages"] if m["role"] == "user"])
    if user_msgs_count <= 1:
        title = req.content[:55].rstrip() + ("…" if len(req.content) > 55 else "")
        await sqlite_db.update_conversation(req.conversation_id, title=title)
        yield await _sse({"type": "title_update", "title": title,
                          "conversation_id": req.conversation_id})

    yield await _sse({"type": "done", "message": ai_msg})


@router.post("/stream")
async def stream_chat(req: ChatRequest):
    return StreamingResponse(
        _generate(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "Connection":        "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
