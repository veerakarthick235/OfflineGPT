import { useCallback } from 'react';
import { useApp } from '../context/AppContext';
import {
  getConversations, createConversation, getConversation,
  updateConversation, deleteConversation,
} from '../api/client';

export function useConversations() {
  const { state, dispatch, toast } = useApp();

  const loadConversations = useCallback(async () => {
    try {
      const list = await getConversations();
      dispatch({ type: 'SET_CONVERSATIONS', payload: list });
    } catch {
      toast('Could not load conversations', 'error');
    }
  }, [dispatch, toast]);

  const selectConversation = useCallback(async (id) => {
    if (id === state.currentId) return;
    dispatch({ type: 'SET_CURRENT', payload: id });
    dispatch({ type: 'SET_STREAM', payload: '' });
    if (!id) { dispatch({ type: 'SET_MESSAGES', payload: [] }); return; }
    try {
      const conv = await getConversation(id);
      dispatch({
        type: 'SET_MESSAGES',
        payload: conv.messages.filter(m => m.role !== 'system'),
      });
    } catch {
      toast('Could not load conversation', 'error');
    }
  }, [state.currentId, dispatch, toast]);

  const newConversation = useCallback(async (model) => {
    try {
      const conv = await createConversation({ model: model || state.selectedModel });
      dispatch({ type: 'SET_CONVERSATIONS', payload: [conv, ...state.conversations] });
      dispatch({ type: 'SET_CURRENT', payload: conv.id });
      dispatch({ type: 'SET_MESSAGES', payload: [] });
      dispatch({ type: 'SET_STREAM', payload: '' });
      return conv;
    } catch {
      toast('Could not create conversation', 'error');
    }
  }, [state.selectedModel, state.conversations, dispatch, toast]);

  const renameConversation = useCallback(async (id, title) => {
    try {
      await updateConversation(id, { title });
      dispatch({ type: 'UPDATE_CONV_TITLE', payload: { id, title } });
    } catch {
      toast('Rename failed', 'error');
    }
  }, [dispatch, toast]);

  const removeConversation = useCallback(async (id) => {
    try {
      await deleteConversation(id);
      dispatch({ type: 'REMOVE_CONV', payload: id });
    } catch {
      toast('Delete failed', 'error');
    }
  }, [dispatch, toast]);

  return {
    conversations: state.conversations,
    currentId: state.currentId,
    loadConversations,
    selectConversation,
    newConversation,
    renameConversation,
    removeConversation,
  };
}
