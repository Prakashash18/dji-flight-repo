import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, Animated, Easing, TouchableOpacity, Platform } from 'react-native';

/**
 * Animated banner announcing newly detected litter.
 *
 * Drops in from above the safe area, pulses a radar ring while visible, then
 * retracts on its own. Tapping it hands the pin back to the parent so the map
 * can fly to the location.
 *
 * Rendering is driven entirely by the `alert` prop: pass a new object to show a
 * banner, pass null to hide it. The parent owns the queue.
 */
export default function LitterAlertBanner({ alert, onPress, onDismiss, topInset = 0, autoHideMs = 5200 }) {
  // -60 keeps the card fully above the screen edge before it drops in.
  const slide = useRef(new Animated.Value(-160)).current;
  const pulse = useRef(new Animated.Value(0)).current;
  const hideTimer = useRef(null);
  const pulseLoop = useRef(null);

  useEffect(() => {
    if (!alert) return;

    // Reset position so a banner arriving while one is showing replays the drop.
    slide.setValue(-160);

    Animated.spring(slide, {
      toValue: 0,
      useNativeDriver: true,
      friction: 7,
      tension: 55,
    }).start();

    pulseLoop.current = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, {
          toValue: 1, duration: 1100, easing: Easing.out(Easing.ease), useNativeDriver: true,
        }),
        Animated.timing(pulse, { toValue: 0, duration: 0, useNativeDriver: true }),
      ])
    );
    pulseLoop.current.start();

    hideTimer.current = setTimeout(dismiss, autoHideMs);

    return () => {
      if (hideTimer.current) clearTimeout(hideTimer.current);
      if (pulseLoop.current) pulseLoop.current.stop();
    };
    // A new alert object (even with the same content) should replay the entrance.
  }, [alert]);

  const dismiss = () => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    Animated.timing(slide, {
      toValue: -160,
      duration: 260,
      easing: Easing.in(Easing.cubic),
      useNativeDriver: true,
    }).start(({ finished }) => {
      // Only clear the alert if this retraction actually ran to completion. A new
      // alert arriving mid-retraction stops this animation, and firing onDismiss
      // then would immediately wipe the banner that just replaced it — exactly the
      // burst-of-detections case this component exists for.
      if (finished && onDismiss) onDismiss();
    });
  };

  if (!alert) return null;

  const ringScale = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.7, 2.3] });
  const ringOpacity = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.55, 0] });

  const count = alert.count || 1;
  const title = count > 1 ? `${count} new litter detections` : 'New litter detected';
  // 4dp is ~11m at the equator — plenty to identify a pin, and short enough that
  // the subtitle does not truncate on a narrow phone.
  const confidence = alert.confidence != null ? `${Math.round(alert.confidence * 100)}% conf.` : null;
  const coords = (alert.latitude != null && alert.longitude != null)
    ? `${Number(alert.latitude).toFixed(4)}, ${Number(alert.longitude).toFixed(4)}`
    : null;

  return (
    <Animated.View
      style={[styles.wrap, { top: topInset + 8, transform: [{ translateY: slide }], pointerEvents: 'box-none' }]}
    >
      <TouchableOpacity
        activeOpacity={0.9}
        onPress={() => { onPress && onPress(alert); dismiss(); }}
        style={styles.card}
        accessibilityRole="alert"
        accessibilityLabel={`${title}. ${coords || ''}`}
      >
        <View style={styles.iconCol}>
          <Animated.View
            style={[styles.ring, { transform: [{ scale: ringScale }], opacity: ringOpacity, pointerEvents: 'none' }]}
          />
          <View style={styles.iconCircle}>
            <Text style={styles.iconGlyph}>🗑️</Text>
          </View>
        </View>

        <View style={styles.textCol}>
          <Text style={styles.title} numberOfLines={1}>{title}</Text>
          <Text style={styles.subtitle} numberOfLines={1}>
            {[coords, confidence].filter(Boolean).join('  ·  ') || 'Tap to view on map'}
          </Text>
        </View>

        <View style={styles.cta}>
          <Text style={styles.ctaText}>VIEW</Text>
        </View>
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    position: 'absolute',
    left: 12,
    right: 12,
    zIndex: 9999,
    elevation: 24,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0F2530',
    borderRadius: 16,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: 'rgba(0, 242, 255, 0.35)',
    ...Platform.select({
      ios: {
        shadowColor: '#00F2FF',
        shadowOpacity: 0.35,
        shadowRadius: 14,
        shadowOffset: { width: 0, height: 6 },
      },
      android: { elevation: 12 },
    }),
  },
  iconCol: {
    width: 42,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  // Expanding radar ring behind the icon.
  ring: {
    position: 'absolute',
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: 'rgba(0, 242, 255, 0.28)',
  },
  iconCircle: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: 'rgba(0, 242, 255, 0.14)',
    borderWidth: 1.5,
    borderColor: '#00F2FF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconGlyph: { fontSize: 19 },
  textCol: { flex: 1 },
  title: {
    color: '#EEF4F8',
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.2,
  },
  subtitle: {
    color: '#8DA9C4',
    fontSize: 11.5,
    marginTop: 2,
  },
  cta: {
    marginLeft: 10,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: 'rgba(0, 242, 255, 0.16)',
    borderWidth: 1,
    borderColor: 'rgba(0, 242, 255, 0.45)',
  },
  ctaText: {
    color: '#00F2FF',
    fontSize: 10.5,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
});
