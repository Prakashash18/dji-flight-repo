import { useEffect, useRef, useCallback } from 'react';
import { Platform } from 'react-native';
import { createAudioPlayer, setAudioModeAsync } from 'expo-audio';
import * as Haptics from 'expo-haptics';

const CHIME = require('../assets/litter-alert.wav');

/**
 * Chime + haptic feedback for new litter detections.
 *
 * Returns a `play()` callback. One player instance is created for the lifetime
 * of the hook and rewound on each use — recreating it per alert introduces an
 * audible delay on the first play and leaks native audio sessions.
 */
export default function useLitterAlertSound({ enabled = true } = {}) {
  const playerRef = useRef(null);
  const lastPlayedAt = useRef(0);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        // playsInSilentMode matters on iOS: volunteers work outdoors and very
        // often have the ringer switch off, which would otherwise mute the alert.
        await setAudioModeAsync({
          playsInSilentMode: true,
          shouldPlayInBackground: false,
          interruptionMode: 'mixWithOthers',
        });

        if (cancelled) return;
        playerRef.current = createAudioPlayer(CHIME);
      } catch (e) {
        // Audio is an enhancement, never a hard dependency of the alert.
        console.warn('[LitterAlert] Audio unavailable:', e?.message || e);
      }
    })();

    return () => {
      cancelled = true;
      try {
        playerRef.current?.remove();
      } catch (_) { /* already torn down */ }
      playerRef.current = null;
    };
  }, []);

  const play = useCallback(async () => {
    if (!enabled) return;

    // A burst of detections arriving together should chime once, not fifty times.
    const now = Date.now();
    if (now - lastPlayedAt.current < 1200) return;
    lastPlayedAt.current = now;

    try {
      const player = playerRef.current;
      if (player) {
        // seekTo is asynchronous; without awaiting it, play() resumes from the
        // end of the previous playback and nothing is audible after the first alert.
        await player.seekTo(0);
        player.play();
      }
    } catch (e) {
      console.warn('[LitterAlert] Playback failed:', e?.message || e);
    }

    try {
      if (Platform.OS !== 'web') {
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      }
    } catch (_) { /* haptics are best-effort */ }
  }, [enabled]);

  return play;
}
