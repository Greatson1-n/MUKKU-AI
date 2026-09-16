import { useState, useEffect, useRef, useCallback } from 'react';

export function useSpeech() {
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [recognitionSupported, setRecognitionSupported] = useState(false);

  const recognitionRef = useRef(null);
  const synthRef = useRef(null);

  useEffect(() => {
    // Check Speech Synthesis
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      synthRef.current = window.speechSynthesis;
      setSpeechSupported(true);
    }

    // Check Speech Recognition
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setRecognitionSupported(true);
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
    }
  }, []);

  const startListening = useCallback(
    (onResult) => {
      if (!recognitionRef.current) return;
      try {
        recognitionRef.current.onresult = (event) => {
          const transcript = Array.from(event.results)
            .map((result) => result[0].transcript)
            .join('');
          if (onResult) onResult(transcript);
        };
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.error('Speech recognition error:', err);
        setIsListening(false);
      }
    },
    []
  );

  const stopListening = useCallback(() => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    }
  }, [isListening]);

  const speak = useCallback((text) => {
    if (!synthRef.current || !text) return;

    synthRef.current.cancel(); // Stop any ongoing speech

    // Clean markdown code blocks from speech for natural audio flow
    const cleanText = text
      .replace(/```[\s\S]*?```/g, ' [Code Block] ')
      .replace(/`([^`]+)`/g, '$1')
      .replace(/[#*_~]/g, '');

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    synthRef.current.speak(utterance);
  }, []);

  const stopSpeaking = useCallback(() => {
    if (synthRef.current) {
      synthRef.current.cancel();
      setIsSpeaking(false);
    }
  }, []);

  return {
    speechSupported,
    recognitionSupported,
    isListening,
    startListening,
    stopListening,
    isSpeaking,
    speak,
    stopSpeaking,
  };
}
