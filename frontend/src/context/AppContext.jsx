import {
  createContext, useContext, useReducer, useCallback, useRef,
} from 'react';

// ── State shape ─────────────────────────────────────────
const initialState = {
  conversations:  [],       // summary list from API
  currentId:      null,
  messages:       [],       // messages for currentId
  streamContent:  '',       // in-progress AI text
  isGenerating:   false,
  models:         [],
  selectedModel:  localStorage.getItem('ogpt_model') || 'llama3.2',
  ollamaOnline:   false,
  sidebarOpen:    true,
  showSettings:   false,
  showSearch:     false,
  showImageGen:   false,
  showModelManager: false,
  showLibrary:      false,
  showVoice:        false,
  showRepo:         false,
  imageGenerating:  null,  // null | string (prompt being generated)
  toolActivity:     null,  // null | { tool, icon, label, status: 'running'|'done'|'error' }
  temperature:    parseFloat(localStorage.getItem('ogpt_temp') || '0.7'),
  systemPrompt:   localStorage.getItem('ogpt_sys') || '',
  toasts:         [],
};

// ── Reducer ─────────────────────────────────────────────
function reducer(state, action) {
  switch (action.type) {
    case 'SET_CONVERSATIONS':   return { ...state, conversations: action.payload };
    case 'SET_CURRENT':         return { ...state, currentId: action.payload };
    case 'SET_MESSAGES':        return { ...state, messages: action.payload };
    case 'ADD_MESSAGE':         return { ...state, messages: [...state.messages, action.payload] };
    case 'APPEND_STREAM':       return { ...state, streamContent: state.streamContent + action.payload };
    case 'SET_STREAM':          return { ...state, streamContent: action.payload };
    case 'SET_GENERATING':      return { ...state, isGenerating: action.payload };
    case 'SET_MODELS':          return { ...state, models: action.payload };
    case 'SET_MODEL':
      localStorage.setItem('ogpt_model', action.payload);
      return { ...state, selectedModel: action.payload };
    case 'SET_OLLAMA':          return { ...state, ollamaOnline: action.payload };
    case 'TOGGLE_SIDEBAR':      return { ...state, sidebarOpen: !state.sidebarOpen };
    case 'SET_SIDEBAR':         return { ...state, sidebarOpen: action.payload };
    case 'SHOW_SETTINGS':       return { ...state, showSettings: action.payload };
    case 'SHOW_SEARCH':         return { ...state, showSearch: action.payload };
    case 'SHOW_IMAGEGEN':       return { ...state, showImageGen: action.payload };
    case 'SHOW_MODELMANAGER':    return { ...state, showModelManager: action.payload };
    case 'SHOW_LIBRARY':          return { ...state, showLibrary: action.payload };
    case 'SHOW_VOICE':            return { ...state, showVoice: action.payload };
    case 'SHOW_REPO':             return { ...state, showRepo: action.payload };
    case 'SET_IMAGE_GENERATING': return { ...state, imageGenerating: action.payload };
    case 'SET_TOOL_ACTIVITY':    return { ...state, toolActivity: action.payload };
    case 'SET_TEMP':
      localStorage.setItem('ogpt_temp', action.payload);
      return { ...state, temperature: action.payload };
    case 'SET_SYS':
      localStorage.setItem('ogpt_sys', action.payload);
      return { ...state, systemPrompt: action.payload };
    case 'ADD_TOAST':           return { ...state, toasts: [...state.toasts, action.payload] };
    case 'REMOVE_TOAST':        return { ...state, toasts: state.toasts.filter(t => t.id !== action.payload) };
    case 'UPDATE_CONV_TITLE':
      return {
        ...state,
        conversations: state.conversations.map(c =>
          c.id === action.payload.id ? { ...c, title: action.payload.title } : c
        ),
      };
    case 'REMOVE_CONV':
      return {
        ...state,
        conversations: state.conversations.filter(c => c.id !== action.payload),
        currentId: state.currentId === action.payload ? null : state.currentId,
        messages:  state.currentId === action.payload ? [] : state.messages,
      };
    default: return state;
  }
}

// ── Context ─────────────────────────────────────────────
const Ctx = createContext(null);

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const abortRef = useRef(null);

  const toast = useCallback((msg, type = 'info', ms = 3500) => {
    const id = Math.random().toString(36).slice(2);
    dispatch({ type: 'ADD_TOAST', payload: { id, msg, type } });
    setTimeout(() => dispatch({ type: 'REMOVE_TOAST', payload: id }), ms);
  }, []);

  return (
    <Ctx.Provider value={{ state, dispatch, toast, abortRef }}>
      {children}
    </Ctx.Provider>
  );
}

export const useApp = () => useContext(Ctx);
