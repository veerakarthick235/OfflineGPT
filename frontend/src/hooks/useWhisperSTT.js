/**
 * useWhisperSTT — Offline STT with automatic silence detection.
 *
 * UX: Click once → speak → silence for 1.5s → auto-stops → transcribes
 * No holding required.
 */
import { useState, useRef, useCallback } from 'react';

const TRANSCRIBE_URL = '/api/stt/transcribe';
const SILENCE_THRESHOLD = 0.015;   // RMS below this = silence
const SILENCE_DURATION_MS = 1500;  // stop after 1.5s of silence

export function useWhisperSTT({ onTranscript } = {}) {
  const [recording,    setRecording]    = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [amplitude,    setAmplitude]    = useState(0);
  const [error,        setError]        = useState(null);

  const mediaRef      = useRef(null);
  const chunksRef     = useRef([]);
  const streamRef     = useRef(null);
  const audioCtxRef   = useRef(null);
  const analyserRef   = useRef(null);
  const silenceTimerRef = useRef(null);
  const rafRef        = useRef(null);
  const stoppedRef    = useRef(false);

  /* ── internal stop + transcribe ───────────────────────── */
  const _doStop = useCallback(async () => {
    if (stoppedRef.current) return;
    stoppedRef.current = true;

    // stop VAD loop
    cancelAnimationFrame(rafRef.current);
    clearTimeout(silenceTimerRef.current);

    // close AudioContext
    try { audioCtxRef.current?.close(); } catch (_) {}
    audioCtxRef.current = null;

    const rec = mediaRef.current;
    if (!rec || rec.state === 'inactive') {
      setRecording(false);
      return;
    }

    return new Promise((resolve) => {
      rec.onstop = async () => {
        streamRef.current?.getTracks().forEach(t => t.stop());

        const mimeType = rec.mimeType || 'audio/webm';
        const blob = new Blob(chunksRef.current, { type: mimeType });
        chunksRef.current = [];
        setRecording(false);

        if (blob.size < 500) { resolve(null); return; }

        setTranscribing(true);
        setError(null);

        try {
          const ext = mimeType.includes('ogg') ? 'ogg'
                    : mimeType.includes('mp4') ? 'mp4' : 'webm';
          const form = new FormData();
          form.append('audio', blob, `rec.${ext}`);

          const resp = await fetch(TRANSCRIBE_URL, { method: 'POST', body: form });
          if (!resp.ok) {
            const e = await resp.json().catch(() => ({ detail: 'Failed' }));
            throw new Error(e.detail || `HTTP ${resp.status}`);
          }
          const data = await resp.json();
          const text = (data.text || '').trim();
          if (text && onTranscript) onTranscript(text);
          resolve(text);
        } catch (err) {
          setError(err.message);
          resolve(null);
        } finally {
          setTranscribing(false);
        }
      };
      rec.stop();
    });
  }, [onTranscript]);

  /* ── VAD loop: measure amplitude, detect silence ────────── */
  const _startVAD = useCallback((stream) => {
    const ctx      = new AudioContext();
    const src      = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    src.connect(analyser);
    audioCtxRef.current  = ctx;
    analyserRef.current  = analyser;

    const buf = new Uint8Array(analyser.frequencyBinCount);
    let   silenceStart = null;

    const tick = () => {
      if (stoppedRef.current) return;
      analyser.getByteFrequencyData(buf);
      const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length) / 255;
      setAmplitude(rms);

      if (rms < SILENCE_THRESHOLD) {
        if (!silenceStart) silenceStart = Date.now();
        else if (Date.now() - silenceStart > SILENCE_DURATION_MS) {
          // Silence detected long enough → auto-stop
          _doStop();
          return;
        }
      } else {
        silenceStart = null; // reset on speech
      }

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
  }, [_doStop]);

  /* ── Public: start recording ─────────────────────────────── */
  const startRecording = useCallback(async () => {
    setError(null);
    chunksRef.current = [];
    stoppedRef.current = false;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/ogg',
        'audio/mp4',
      ].find(m => MediaRecorder.isTypeSupported(m)) || '';

      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : {});
      mediaRef.current = rec;
      rec.ondataavailable = (e) => {
        if (e.data?.size > 0) chunksRef.current.push(e.data);
      };
      rec.start(100);
      setRecording(true);
      _startVAD(stream);
    } catch (err) {
      setError('Microphone access denied');
      throw err;
    }
  }, [_startVAD]);

  /* ── Public: manual stop (e.g. user clicks mic again) ─────── */
  const stopRecording = useCallback(() => _doStop(), [_doStop]);

  /* ── Public: cancel without transcribing ────────────────── */
  const cancel = useCallback(() => {
    stoppedRef.current = true;
    cancelAnimationFrame(rafRef.current);
    clearTimeout(silenceTimerRef.current);
    try { audioCtxRef.current?.close(); } catch (_) {}
    audioCtxRef.current = null;
    if (mediaRef.current?.state !== 'inactive') mediaRef.current?.stop();
    streamRef.current?.getTracks().forEach(t => t.stop());
    chunksRef.current = [];
    setRecording(false);
    setTranscribing(false);
    setAmplitude(0);
  }, []);

  return {
    recording,
    transcribing,
    amplitude,
    error,
    startRecording,
    stopRecording,
    cancel,
  };
}
