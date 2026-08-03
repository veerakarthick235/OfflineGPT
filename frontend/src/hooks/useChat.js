import { useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { useConversations } from './useConversations';
import { streamChat } from '../api/client';

export function useChat() {
  const { state, dispatch, toast, abortRef } = useApp();
  const { newConversation, loadConversations } = useConversations();

  const send = useCallback(async (text, attachmentIds = []) => {
    if (!text.trim() || state.isGenerating) return;

    // Ensure a conversation exists
    let convId = state.currentId;
    if (!convId) {
      const conv = await newConversation(state.selectedModel);
      if (!conv) return;
      convId = conv.id;
    }

    dispatch({ type: 'SET_GENERATING',      payload: true });
    dispatch({ type: 'SET_STREAM',          payload: '' });
    dispatch({ type: 'SET_IMAGE_GENERATING', payload: null });
    dispatch({ type: 'SET_TOOL_ACTIVITY',   payload: null });

    const payload = {
      conversation_id: convId,
      content:         text.trim(),
      model:           state.selectedModel,
      temperature:     state.temperature,
      max_tokens:      2048,
      attachment_ids:  attachmentIds,   // Phase 6
    };

    const ctrl = await streamChat(payload, {
      onUserMessage: (msg) => {
        dispatch({ type: 'ADD_MESSAGE', payload: msg });
      },

      onImageGenerating: ({ prompt }) => {
        dispatch({ type: 'SET_IMAGE_GENERATING', payload: prompt });
      },

      onImageDone: () => {
        dispatch({ type: 'SET_IMAGE_GENERATING', payload: null });
      },

      onChunk: (chunk) => {
        dispatch({ type: 'APPEND_STREAM', payload: chunk });
      },

      onDone: (aiMsg) => {
        dispatch({ type: 'ADD_MESSAGE',          payload: aiMsg });
        dispatch({ type: 'SET_STREAM',           payload: '' });
        dispatch({ type: 'SET_GENERATING',       payload: false });
        dispatch({ type: 'SET_IMAGE_GENERATING', payload: null });
        dispatch({ type: 'SET_TOOL_ACTIVITY',    payload: null });
        loadConversations();
      },

      onTitleUpdate: ({ conversation_id, title }) => {
        dispatch({ type: 'UPDATE_CONV_TITLE', payload: { id: conversation_id, title } });
      },

      onError: (err) => {
        dispatch({ type: 'SET_GENERATING',       payload: false });
        dispatch({ type: 'SET_STREAM',           payload: '' });
        dispatch({ type: 'SET_IMAGE_GENERATING', payload: null });
        dispatch({ type: 'SET_TOOL_ACTIVITY',    payload: null });
        toast(err.message || 'Generation failed', 'error', 6000);
      },

      // ── Phase 3: Agent tool events ─────────────────────────
      onToolStart: ({ tool, icon, label }) => {
        dispatch({
          type: 'SET_TOOL_ACTIVITY',
          payload: { tool, icon: icon || '⚡', label, status: 'running' },
        });
      },

      onToolResult: ({ tool, icon, label, success, data }) => {
        dispatch({
          type: 'SET_TOOL_ACTIVITY',
          payload: { tool, icon: icon || '✅', label, status: success ? 'done' : 'error', data },
        });
        // Auto-clear after 4 s
        setTimeout(() => {
          dispatch({ type: 'SET_TOOL_ACTIVITY', payload: null });
        }, 4000);
      },

      onToolError: ({ tool, message }) => {
        dispatch({
          type: 'SET_TOOL_ACTIVITY',
          payload: { tool, icon: '⚠️', label: message || 'Tool failed', status: 'error' },
        });
        setTimeout(() => {
          dispatch({ type: 'SET_TOOL_ACTIVITY', payload: null });
        }, 5000);
      },
    });

    abortRef.current = ctrl;
  }, [state, dispatch, toast, abortRef, newConversation, loadConversations]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: 'SET_GENERATING',       payload: false });
    dispatch({ type: 'SET_STREAM',           payload: '' });
    dispatch({ type: 'SET_IMAGE_GENERATING', payload: null });
    dispatch({ type: 'SET_TOOL_ACTIVITY',    payload: null });
  }, [abortRef, dispatch]);

  return { send, stop };
}
