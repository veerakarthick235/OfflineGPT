import { useEffect, useCallback } from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { useConversations } from './hooks/useConversations';
import Sidebar from './components/Sidebar/Sidebar';
import Header from './components/Header/Header';
import ChatArea from './components/Chat/ChatArea';
import MessageInput from './components/Input/MessageInput';
import SettingsModal from './components/Modals/SettingsModal';
import SearchModal from './components/Modals/SearchModal';
import ImageGenModal from './components/Modals/ImageGenModal';
import ModelManagerModal from './components/Modals/ModelManagerModal';
import LibraryModal from './components/Modals/LibraryModal';
import VoiceMode from './components/Voice/VoiceMode';
import RepoManagerModal from './components/Modals/RepoManagerModal';
import ToastStack from './components/Toast';

function AppInner() {
  const { state, dispatch } = useApp();
  const { loadConversations } = useConversations();

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Global keyboard shortcuts
  const handleKeyDown = useCallback((e) => {
    // Ctrl+/ → new chat
    if ((e.ctrlKey || e.metaKey) && e.key === '/') {
      e.preventDefault();
      dispatch({ type: 'SET_CURRENT', payload: null });
      dispatch({ type: 'SET_MESSAGES', payload: [] });
      dispatch({ type: 'SET_STREAM', payload: '' });
    }
    // Ctrl+K → search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      dispatch({ type: 'SHOW_SEARCH', payload: true });
    }
    // Escape → close modals
    if (e.key === 'Escape') {
      if (state.showSettings)     dispatch({ type: 'SHOW_SETTINGS',     payload: false });
      if (state.showSearch)       dispatch({ type: 'SHOW_SEARCH',       payload: false });
      if (state.showImageGen)     dispatch({ type: 'SHOW_IMAGEGEN',     payload: false });
      if (state.showModelManager) dispatch({ type: 'SHOW_MODELMANAGER', payload: false });
      if (state.showLibrary)      dispatch({ type: 'SHOW_LIBRARY',      payload: false });
      if (state.showVoice)        dispatch({ type: 'SHOW_VOICE',        payload: false });
      if (state.showRepo)         dispatch({ type: 'SHOW_REPO',         payload: false });
    }
  }, [state, dispatch]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <Sidebar />

      {/* Main */}
      <div className="main-area">
        <Header />
        <ChatArea />
        <MessageInput />
      </div>

      {/* Modals */}
      {state.showSettings     && <SettingsModal     onClose={() => dispatch({ type: 'SHOW_SETTINGS',     payload: false })} />}
      {state.showSearch       && <SearchModal       onClose={() => dispatch({ type: 'SHOW_SEARCH',       payload: false })} />}
      {state.showImageGen     && <ImageGenModal     onClose={() => dispatch({ type: 'SHOW_IMAGEGEN',     payload: false })} />}
      {state.showModelManager && <ModelManagerModal onClose={() => dispatch({ type: 'SHOW_MODELMANAGER', payload: false })} />}
      {state.showLibrary      && <LibraryModal      onClose={() => dispatch({ type: 'SHOW_LIBRARY',      payload: false })} />}
      {state.showVoice        && <VoiceMode         onClose={() => dispatch({ type: 'SHOW_VOICE',        payload: false })} />}
      {state.showRepo         && <RepoManagerModal  onClose={() => dispatch({ type: 'SHOW_REPO',         payload: false })} />}

      {/* Toasts */}
      <ToastStack />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <AppInner />
    </AppProvider>
  );
}
