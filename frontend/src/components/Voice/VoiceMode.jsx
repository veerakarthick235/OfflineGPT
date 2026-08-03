/**
 * VoiceMode — Offline voice conversation.
 *
 * UX:
 *  Click mic → 🔴 recording, orb pulses with voice amplitude
 *  Stop speaking → silence detected → auto-transcribes (faster-whisper)
 *  AI responds → 🔊 spoken in female voice
 *  Ready again automatically
 *
 * 100% offline: STT = faster-whisper, TTS = browser SpeechSynthesis
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { useApp }           from '../../context/AppContext';
import { useConversations } from '../../hooks/useConversations';
import { streamChat }       from '../../api/client';
import { useWhisperSTT }    from '../../hooks/useWhisperSTT';
import { useTTS }           from '../../hooks/useTTS';

const STYLE = `
@keyframes orbBreath{0%,100%{transform:scale(1)}50%{transform:scale(1.09)}}
@keyframes orbRing{0%{transform:scale(.88);opacity:.75}100%{transform:scale(1.8);opacity:0}}
@keyframes voiceBar{0%,80%,100%{transform:scaleY(1)}40%{transform:scaleY(2.8)}}
@keyframes fadeUp{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:translateY(0)}}
@keyframes spin{to{transform:rotate(360deg)}}
`;

function VoiceBars({ amp, color = 'rgba(255,255,255,.9)' }) {
  return (
    <div style={{ display: 'flex', gap: 5, alignItems: 'center', height: 28 }}>
      {[1, 1.6, 2.2, 1.6, 1].map((h, i) => (
        <div key={i} style={{
          width: 4, borderRadius: 99, background: color,
          height: `${Math.max(4, h * (6 + amp * 180))}px`,
          transition: 'height .05s',
        }} />
      ))}
    </div>
  );
}

const PHASE_LABEL = {
  idle:         '🎙 Click mic to speak',
  recording:    '🔴 Listening… (stops on silence)',
  transcribing: '⌛ Transcribing…',
  thinking:     '💭 Thinking…',
  speaking:     '🔊 Speaking…',
};

export default function VoiceMode() {
  const { state, dispatch, toast, abortRef } = useApp();
  const { newConversation, loadConversations } = useConversations();
  const tts = useTTS();

  const [phase,      setPhase]      = useState('idle');
  const [transcript, setTranscript] = useState('');
  const [aiText,     setAiText]     = useState('');
  const [sttReady,   setSttReady]   = useState(false);

  const phaseRef = useRef('idle');
  const sendRef  = useRef(null);

  const go = (p) => { phaseRef.current = p; setPhase(p); };

  /* ── Whisper STT — auto-sends on transcript ─────────────── */
  const stt = useWhisperSTT({
    onTranscript: (text) => {
      setTranscript(text);
      sendRef.current?.(text);
    },
  });

  /* ── Check model availability ────────────────────────────── */
  useEffect(() => {
    fetch('/api/stt/models')
      .then(r => r.json())
      .then(m => setSttReady(m.some(x => x.downloaded)))
      .catch(() => setSttReady(false));
  }, []);

  /* ── Send to AI ─────────────────────────────────────────── */
  const sendToAI = useCallback(async (text) => {
    if (!text?.trim()) { go('idle'); return; }
    go('thinking');
    setAiText('');

    let convId = state.currentId;
    if (!convId) {
      const conv = await newConversation(state.selectedModel);
      if (!conv) { go('idle'); return; }
      convId = conv.id;
    }

    dispatch({ type: 'SET_GENERATING', payload: true });
    dispatch({ type: 'SET_STREAM', payload: '' });

    let full = '';
    const ctrl = await streamChat({
      conversation_id: convId,
      content: text.trim(),
      model: state.selectedModel,
      temperature: state.temperature,
      max_tokens: 2048,
    }, {
      onUserMessage: (m) => dispatch({ type: 'ADD_MESSAGE', payload: m }),
      onChunk: (c) => {
        full += c;
        dispatch({ type: 'APPEND_STREAM', payload: c });
        setAiText(full);
      },
      onImageGenerating: () => {}, onImageDone: () => {},
      onDone: (m) => {
        dispatch({ type: 'ADD_MESSAGE', payload: m });
        dispatch({ type: 'SET_STREAM',  payload: '' });
        dispatch({ type: 'SET_GENERATING', payload: false });
        dispatch({ type: 'SET_IMAGE_GENERATING', payload: null });
        loadConversations();
        go('speaking');
        tts.speak(full, { onEnd: () => go('idle') });
      },
      onTitleUpdate: ({ conversation_id, title }) =>
        dispatch({ type: 'UPDATE_CONV_TITLE', payload: { id: conversation_id, title } }),
      onError: (e) => {
        dispatch({ type: 'SET_GENERATING', payload: false });
        dispatch({ type: 'SET_STREAM', payload: '' });
        toast(e.message || 'Error', 'error');
        go('idle');
      },
    });
    abortRef.current = ctrl;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, dispatch, toast, abortRef, newConversation, loadConversations, tts]);

  useEffect(() => { sendRef.current = sendToAI; }, [sendToAI]);

  /* ── Track phase changes from STT ────────────────────────── */
  useEffect(() => {
    if (stt.recording)    go('recording');
    if (stt.transcribing) go('transcribing');
  }, [stt.recording, stt.transcribing]);

  /* ── Mic click handler ───────────────────────────────────── */
  const handleMicClick = useCallback(async () => {
    if (phase === 'speaking') { tts.cancel(); go('idle'); return; }
    if (phase === 'thinking') return; // wait for AI
    if (phase === 'transcribing') return;

    if (phase === 'recording') {
      // Manual stop (don't wait for silence)
      stt.stopRecording();
      return;
    }

    // idle → start
    if (!sttReady) {
      toast('Download a Whisper STT model first: Models → STT Models', 'error');
      return;
    }
    tts.cancel();
    setTranscript('');
    try {
      await stt.startRecording();
    } catch {
      toast('Microphone access denied', 'error');
    }
  }, [phase, sttReady, stt, tts, toast]);

  /* ── Cleanup on unmount ──────────────────────────────────── */
  useEffect(() => () => { stt.cancel(); tts.cancel(); }, []); // eslint-disable-line

  /* ── Orb visuals ─────────────────────────────────────────── */
  const amp     = stt.amplitude;
  const scale   = phase === 'recording' ? 1 + Math.min(amp * 2, 0.45) : 1;
  const isActive = phase === 'recording' || phase === 'speaking';
  const isRed    = phase === 'recording';

  const orbGrad = isRed
    ? `radial-gradient(circle at 36% 33%,
        rgba(255,200,200,.9) 0%,rgba(255,120,120,.75) 20%,
        rgba(220,50,50,.88) 45%,rgba(160,20,20,.95) 70%,rgba(80,0,0,1) 100%)`
    : `radial-gradient(circle at 36% 33%,
        rgba(255,255,255,.88) 0%,rgba(155,175,255,.72) 16%,
        rgba(85,110,250,.82) 40%,rgba(55,80,225,.92) 64%,rgba(25,30,110,1) 100%)`;

  const orbShadow = isRed
    ? `0 0 ${36 + amp * 120}px rgba(239,68,68,.6),0 0 ${70 + amp * 200}px rgba(239,68,68,.22),inset 0 0 36px rgba(255,200,200,.08)`
    : `0 0 36px rgba(100,130,255,.5),0 0 70px rgba(75,100,245,.22),inset 0 0 36px rgba(200,215,255,.1)`;

  const micBg = phase === 'recording'
    ? 'linear-gradient(135deg,#dc2626,#ef4444)'
    : phase === 'speaking'
    ? 'linear-gradient(135deg,#7c3aed,#a855f7)'
    : sttReady
    ? 'linear-gradient(135deg,#4f46e5,#7c3aed)'
    : 'rgba(255,255,255,.1)';

  return (
    <>
      <style>{STYLE}</style>
      <div style={{
        position: 'fixed', inset: 0, zIndex: 8000,
        background: 'rgba(0,0,0,.93)', backdropFilter: 'blur(16px)',
        display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        animation: 'fadeUp .3s ease',
      }}>

        {/* ── Orb ── */}
        <div style={{ position: 'relative', width: 230, height: 230, marginBottom: 38 }}>
          {isActive && [0, .65, 1.3].map(d => (
            <div key={d} style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              border: `1.5px solid ${isRed ? 'rgba(239,68,68,.4)' : 'rgba(130,150,255,.4)'}`,
              animation: `orbRing 2.6s ease-out ${d}s infinite`,
            }} />
          ))}
          <div style={{
            position: 'absolute', inset: 0, borderRadius: '50%',
            transform: `scale(${scale})`, transition: 'transform .05s',
            animation: isActive ? 'orbBreath 2.8s ease-in-out infinite' : 'none',
            background: orbGrad,
            boxShadow: orbShadow,
          }} />
          <div style={{
            position: 'absolute', top: '17%', left: '21%',
            width: '27%', height: '17%', borderRadius: '50%',
            background: 'rgba(255,255,255,.55)', filter: 'blur(6px)', pointerEvents: 'none',
          }} />
        </div>

        {/* ── Status / bars ── */}
        <div style={{ textAlign: 'center', marginBottom: 16, minHeight: 56,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
          {phase === 'recording' && <VoiceBars amp={amp} color="rgba(255,150,150,.9)" />}
          {phase === 'speaking'  && <VoiceBars amp={.18} color="rgba(168,85,247,.9)" />}
          {(phase === 'thinking' || phase === 'transcribing') && (
            <div style={{ width: 22, height: 22, borderRadius: '50%',
              border: '2.5px solid #7c3aed', borderTopColor: 'transparent',
              animation: 'spin .75s linear infinite' }} />
          )}
          <span style={{
            fontSize: 14, letterSpacing: .3, fontWeight: 500,
            color: isActive ? 'rgba(255,255,255,.85)' : 'rgba(255,255,255,.35)',
          }}>
            {PHASE_LABEL[phase]}
          </span>
        </div>

        {/* ── No model warning ── */}
        {!sttReady && (
          <div style={{
            maxWidth: 380, padding: '12px 16px', borderRadius: 10, marginBottom: 18,
            background: 'rgba(245,158,11,.1)', border: '1px solid rgba(245,158,11,.3)',
            color: '#fcd34d', fontSize: 13, textAlign: 'center', lineHeight: 1.55,
          }}>
            ⚠️ No Whisper model downloaded.<br />
            Go to <strong>Models → STT Models</strong> → download <strong>Whisper Base</strong> (~145 MB).
          </div>
        )}

        {/* ── Live text ── */}
        {(transcript || aiText) && (
          <div style={{
            maxWidth: 500, width: '90vw', textAlign: 'center',
            fontSize: 15, lineHeight: 1.7, marginBottom: 24, maxHeight: 120, overflow: 'hidden',
            color: phase === 'speaking' ? 'rgba(200,180,255,.9)' : 'rgba(255,255,255,.88)',
          }}>
            {phase === 'speaking' ? aiText.slice(-280) : transcript}
          </div>
        )}

        {/* ── Controls ── */}
        <div style={{ position: 'fixed', bottom: 38,
          display: 'flex', alignItems: 'center', gap: 16 }}>

          {/* Main mic / stop button */}
          <button
            onClick={handleMicClick}
            disabled={phase === 'thinking' || phase === 'transcribing'}
            title={
              phase === 'recording' ? 'Click to stop early'
              : phase === 'speaking' ? 'Click to stop speaking'
              : 'Click to speak'
            }
            style={{
              width: 68, height: 68, borderRadius: '50%',
              background: micBg,
              border: '2px solid rgba(255,255,255,.18)',
              color: 'white', cursor: (phase === 'thinking' || phase === 'transcribing') ? 'default' : 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: phase === 'recording'
                ? `0 0 ${28 + amp * 60}px rgba(239,68,68,.65)`
                : isActive ? '0 0 22px rgba(124,58,237,.5)' : 'none',
              transition: 'background .18s, box-shadow .05s',
            }}
          >
            {phase === 'recording' ? (
              /* Square = stop */
              <svg width="22" height="22" viewBox="0 0 24 24" fill="white">
                <rect x="4" y="4" width="16" height="16" rx="3"/>
              </svg>
            ) : phase === 'speaking' ? (
              /* Speaker wave */
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                <polygon points="11,5 6,9 2,9 2,15 6,15 11,19 11,5"/>
                <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
                <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
              </svg>
            ) : (
              /* Mic */
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none"
                stroke={sttReady ? 'white' : 'rgba(255,255,255,.4)'} strokeWidth="2">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                <line x1="12" y1="19" x2="12" y2="23"/>
                <line x1="8"  y1="23" x2="16" y2="23"/>
              </svg>
            )}
          </button>

          {/* Close */}
          <button
            onClick={() => {
              stt.cancel(); tts.cancel();
              dispatch({ type: 'SHOW_VOICE', payload: false });
            }}
            title="Close voice mode"
            style={{
              width: 54, height: 54, borderRadius: '50%',
              background: 'rgba(255,255,255,.07)',
              border: '1px solid rgba(255,255,255,.13)',
              color: 'rgba(255,255,255,.65)', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* Hint */}
        <div style={{
          position: 'fixed', bottom: 12, fontSize: 12,
          color: 'rgba(255,255,255,.18)', letterSpacing: .3,
        }}>
          STT: faster-whisper (local) · TTS: female voice (offline)
        </div>
      </div>
    </>
  );
}
