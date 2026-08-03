/**
 * useSpeechRecognition — Web Speech API wrapper.
 * Works in Chrome/Edge offline (no server needed).
 */
import { useState, useRef, useCallback, useEffect } from 'react';

export function useSpeechRecognition({ onInterim, onFinal, onEnd } = {}) {
  const [listening, setListening]   = useState(false);
  const [supported, setSupported]   = useState(false);
  const recRef   = useRef(null);
  const stoppedRef = useRef(false);

  useEffect(() => {
    setSupported(!!(window.SpeechRecognition || window.webkitSpeechRecognition));
  }, []);

  const start = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return;
    stoppedRef.current = false;

    const rec = new SR();
    rec.continuous      = true;
    rec.interimResults  = true;
    rec.lang            = 'en-US';
    rec.maxAlternatives = 1;

    rec.onresult = (e) => {
      let interim = '';
      let finalT  = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalT += t;
        else interim += t;
      }
      if (finalT)  onFinal?.(finalT);
      if (interim) onInterim?.(interim);
    };

    rec.onerror = (e) => {
      if (e.error !== 'no-speech') console.warn('[STT]', e.error);
    };

    rec.onend = () => {
      if (!stoppedRef.current) {
        // auto-restart if we didn't explicitly stop
        try { rec.start(); } catch (_) {}
        return;
      }
      setListening(false);
      onEnd?.();
    };

    rec.start();
    recRef.current = rec;
    setListening(true);
  }, [onInterim, onFinal, onEnd]);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    recRef.current?.stop();
    setListening(false);
    onEnd?.();
  }, [onEnd]);

  return { listening, supported, start, stop };
}
