import React, { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet } from 'react-native';

/**
 * Expanding radar ring drawn behind a freshly detected litter marker.
 *
 * Sits absolutely inside the marker view so it radiates from the pin's centre
 * without affecting layout. Purely decorative — rendered only for pins that
 * arrived during this session, and removed once they stop being "new".
 */
export default function NewPinPulse({ color = '#00fbfb', size = 22 }) {
  const pulse = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.timing(pulse, {
        toValue: 1,
        duration: 1600,
        easing: Easing.out(Easing.ease),
        useNativeDriver: true,
      })
    );
    loop.start();
    return () => loop.stop();
  }, [pulse]);

  const scale = pulse.interpolate({ inputRange: [0, 1], outputRange: [0.6, 2.8] });
  const opacity = pulse.interpolate({ inputRange: [0, 0.15, 1], outputRange: [0, 0.6, 0] });

  return (
    <Animated.View
      style={[
        styles.ring,
        {
          width: size,
          height: size,
          borderRadius: size / 2,
          backgroundColor: color,
          transform: [{ scale }],
          opacity,
          pointerEvents: 'none',
        },
      ]}
    />
  );
}

const styles = StyleSheet.create({
  ring: {
    position: 'absolute',
    alignSelf: 'center',
    top: '50%',
    marginTop: -11,
  },
});
