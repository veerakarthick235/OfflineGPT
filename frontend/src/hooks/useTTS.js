/**
 * useTTS — Text-to-Speech using browser SpeechSynthesis.
 * Always selects a female voice (prefers Microsoft/Google female voices).
 * Strips markdown before speaking.
 */
import { useCallback, useRef } from 'react';

const FEMALE_KEYWORDS = [
  'zira', 'hazel', 'susan', 'heera', 'natasha', 'karen', 'samantha',
  'moira', 'fiona', 'tessa', 'female', 'woman', 'girl',
  'google uk english female', 'google us english',
];

function pickFemaleVoice() {
  const voices = window.speechSynthesis?.getVoices() || [];

  // 1. Exact match for known female voice names
  for (const kw of FEMALE_KEYWORDS) {
    const match = voices.find(v => v.name.toLowerCase().includes(kw));
    if (match) return match;
  }

  // 2. Prefer en-US / en-GB voices
  const enVoice = voices.find(v => v.lang.startsWith('en'));
  if (enVoice) return enVoice;

  // 3. Fallback — first available
  return voices[0] || null;
}

function stripMarkdown(text) {
  return text
    .replace(/```[\s\S]*?```/g, '')   // code blocks
    .replace(/`[^`]+`/g, '')          // inline code
    .replace(/#+\s/g, '')             // headings
    .replace(/[*_]{1,3}([^*_]+)[*_]{1,3}/g, '$1') // bold/italic
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')       // links
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '')           // images
    .replace(/^\s*[-*+]\s/gm, '')     // list bullets
    .replace(/^\s*\d+\.\s/gm, '')     // numbered list
    .replace(/\n{2,}/g, '. ')
    .replace(/\n/g, ' ')
    .trim();
}

export function useTTS() {
  const utterRef = useRef(null);

  const speak = useCallback((text, { onEnd, onStart } = {}) => {
    if (!window.speechSynthesis) { onEnd?.(); return; }

    window.speechSynthesis.cancel();

    const clean = stripMarkdown(text);
    if (!clean) { onEnd?.(); return; }

    // Voices may not be loaded yet — wait if needed
    const _speak = () => {
      const utterance = new SpeechSynthesisUtterance(clean);

      const voice = pickFemaleVoice();
      if (voice) utterance.voice = voice;

      utterance.rate   = 1.0;
      utterance.pitch  = 1.1;   // slightly higher = more feminine
      utterance.volume = 1.0;
      utterance.lang   = voice?.lang || 'en-US';

      utterance.onstart = () => onStart?.();
      utterance.onend   = () => { utterRef.current = null; onEnd?.(); };
      utterance.onerror = () => { utterRef.current = null; onEnd?.(); };

      utterRef.current = utterance;
      window.speechSynthesis.speak(utterance);
    };

    const voices = window.speechSynthesis.getVoices();
    if (voices.length > 0) {
      _speak();
    } else {
      // Wait for voices to load (happens once on first call)
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null;
        _speak();
      };
    }
  }, []);

  const cancel = useCallback(() => {
    window.speechSynthesis?.cancel();
    utterRef.current = null;
  }, []);

  const isSpeaking = () => window.speechSynthesis?.speaking ?? false;

  return { speak, cancel, isSpeaking };
}
