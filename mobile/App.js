import 'react-native-url-polyfill/auto';
import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, SafeAreaView, StatusBar, Linking, Alert, Platform } from 'react-native';
import { createClient } from '@supabase/supabase-js';

// Import screens
import MapScreen from './screens/MapScreen';
import AlertsScreen from './screens/AlertsScreen';
import LeaderboardScreen from './screens/LeaderboardScreen';
import ControlScreen from './screens/ControlScreen';
import AuthScreen from './screens/AuthScreen';
import { t } from './utils/translations';
import { parsePinParams } from './utils/statsHelper';

// Supabase configuration
const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL || "";
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || "";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

// Backend API configuration (For physical device testing, replace localhost with your Ngrok HTTPS URL)
const BACKEND_URL = "http://localhost:8000";

export default function App() {
  const [session, setSession] = useState(null);
  const [pendingMissionId, setPendingMissionId] = useState(null);
  const [currentTab, setCurrentTab] = useState('Map'); // 'Map' | 'Alerts' | 'Leaderboard' | 'Control'
  const [userRole, setUserRole] = useState('volunteer'); // 'volunteer' | 'coordinator'
  const [userLanguage, setUserLanguage] = useState('en'); // 'en' | 'th' | 'id' | 'tl' | 'ms' | 'ta'
  const [pins, setPins] = useState([]);
  const [hideTabBar, setHideTabBar] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [missions, setMissions] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [selectedMissionId, setSelectedMissionId] = useState(null);
  const [activeVolunteerName, setActiveVolunteerName] = useState('Sorawit P.');
  const [cleanupZones, setCleanupZones] = useState([]);
  const userRoleRef = useRef(userRole);
  useEffect(() => {
    userRoleRef.current = userRole;
  }, [userRole]);

  // Real-time Supabase Subscription
  useEffect(() => {
    // 1. Fetch initial litter pins with pagination to bypass PostgREST 1000-row limit
    const fetchPins = async () => {
      let allPins = [];
      let from = 0;
      const limit = 1000;
      let hasMore = true;
      
      while (hasMore) {
        const { data, error } = await supabase
          .from('litter_pins')
          .select('*')
          .range(from, from + limit - 1);
          
        if (error) {
          console.error("Error fetching pins:", error.message);
          break;
        }
        
        if (data && data.length > 0) {
          allPins = [...allPins, ...data];
          if (data.length < limit) {
            hasMore = false;
          } else {
            from += limit;
          }
        } else {
          hasMore = false;
        }
      }
      
      if (allPins.length > 0) {
        setPins(allPins);
      }
    };

    // 2. Fetch initial alerts
    const fetchAlerts = async () => {
      const { data, error } = await supabase
        .from('alerts')
        .select('*')
        .order('created_at', { ascending: false });
      if (!error && data) setAlerts(data);
    };

    // 2.1 Fetch initial missions
    const fetchMissions = async () => {
      const { data, error } = await supabase
        .from('missions')
        .select('*')
        .order('mission_date', { ascending: false });
      if (!error && data) {
        setMissions(data);
        if (data.length > 0) {
          setSelectedMissionId(data[0].id);
        }
      }
    };

    // 2.2 Fetch initial profiles
    const fetchProfiles = async () => {
      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .order('name');
      if (!error && data) {
        setProfiles(data);
        const volunteers = data.filter(p => p.role === 'volunteer');
        if (volunteers.length > 0) {
          // If Sorawit P. exists, use him as default, else first volunteer
          const sorawit = volunteers.find(v => v.name === 'Sorawit P.');
          if (sorawit) {
            setActiveVolunteerName(sorawit.name);
          } else {
            setActiveVolunteerName(volunteers[0].name);
          }
        }
      }
    };

    // 2.3 Fetch initial cleanup zones
    const fetchCleanupZones = async () => {
      const { data, error } = await supabase
        .from('cleanup_zones')
        .select('*');
      if (!error && data) setCleanupZones(data);
    };

    fetchPins();
    fetchAlerts();
    fetchMissions();
    fetchProfiles();
    fetchCleanupZones();

    // 3. Set up real-time pins listener
    const pinsSubscription = supabase
      .channel('litter-pins-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'litter_pins' }, (payload) => {
        if (payload.eventType === 'INSERT' && payload.new) {
          setPins(prev => [payload.new, ...prev]);
        } else if (payload.eventType === 'UPDATE' && payload.new) {
          setPins(prev => prev.map(pin => (pin && pin.id === payload.new.id) ? payload.new : pin));
          
          // Coordinator Real-time Notification Feedback
          if (payload.new.status === 'cleaned' && payload.old && payload.old.status !== 'cleaned') {
            const parsed = parsePinParams(payload.new);
            const assignee = parsed.assigned_to || "A volunteer";
            const isMistake = parsed.is_mistake;
            
            if (userRoleRef.current === 'coordinator') {
              Alert.alert(
                "🚨 Shoreline Clear Alert",
                `Volunteer "${assignee}" has resolved a ${isMistake ? 'false detection (mistake)' : 'litter detection point'} at Lat: ${payload.new.latitude.toFixed(4)}, Lon: ${payload.new.longitude.toFixed(4)}.`
              );
            }
          }
        } else if (payload.eventType === 'DELETE' && payload.old && payload.old.id) {
          setPins(prev => prev.filter(pin => pin && pin.id !== payload.old.id));
        }
      })
      .subscribe();

    // 4. Set up real-time alerts listener
    const alertsSubscription = supabase
      .channel('alerts-changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'alerts' }, (payload) => {
        if (payload.new) {
          setAlerts(prev => [payload.new, ...prev]);
        }
      })
      .subscribe();

    // 5. Set up real-time missions listener
    const missionsSubscription = supabase
      .channel('missions-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'missions' }, (payload) => {
        if (payload.eventType === 'INSERT' && payload.new) {
          setMissions(prev => [payload.new, ...prev]);
          setSelectedMissionId(payload.new.id); // Auto-focus new mission
        } else if (payload.eventType === 'UPDATE' && payload.new) {
          setMissions(prev => prev.map(m => m.id === payload.new.id ? payload.new : m));
        } else if (payload.eventType === 'DELETE' && payload.old && payload.old.id) {
          setMissions(prev => prev.filter(m => m.id !== payload.old.id));
        }
      })
      .subscribe();

    // 5.1 Set up real-time cleanup zones listener
    const zonesSubscription = supabase
      .channel('cleanup-zones-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'cleanup_zones' }, (payload) => {
        if (payload.eventType === 'INSERT' && payload.new) {
          setCleanupZones(prev => [payload.new, ...prev]);
        } else if (payload.eventType === 'UPDATE' && payload.new) {
          setCleanupZones(prev => prev.map(z => z.id === payload.new.id ? payload.new : z));
        } else if (payload.eventType === 'DELETE' && payload.old && payload.old.id) {
          setCleanupZones(prev => prev.filter(z => z.id !== payload.old.id));
        }
      })
      .subscribe();

    // 6. Set up real-time profiles listener
    const profilesSubscription = supabase
      .channel('profiles-changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'profiles' }, (payload) => {
        if (payload.eventType === 'INSERT' && payload.new) {
          setProfiles(prev => [...prev, payload.new].sort((a, b) => a.name.localeCompare(b.name)));
        } else if (payload.eventType === 'UPDATE' && payload.new) {
          setProfiles(prev => prev.map(p => p.id === payload.new.id ? payload.new : p));
        } else if (payload.eventType === 'DELETE' && payload.old && payload.old.id) {
          setProfiles(prev => prev.filter(p => p.id !== payload.old.id));
        }
      })
      .subscribe();

    // Cleanup subscriptions on unmount
    return () => {
      supabase.removeChannel(pinsSubscription);
      supabase.removeChannel(alertsSubscription);
      supabase.removeChannel(missionsSubscription);
      supabase.removeChannel(profilesSubscription);
      supabase.removeChannel(zonesSubscription);
    };
  }, []);

  const fetchUserProfile = async (userId) => {
    const { data, error } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', userId)
      .single();
    if (!error && data) {
      setUserRole(data.role);
      setActiveVolunteerName(data.name);
      setUserLanguage(data.preferred_language || 'en');
    }
  };

  // Auth state listener
  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      setSession(initialSession);
      if (initialSession?.user) {
        fetchUserProfile(initialSession.user.id);
      }
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, newSession) => {
      setSession(newSession);
      if (newSession?.user) {
        fetchUserProfile(newSession.user.id);
      } else {
        setUserRole('volunteer');
        setActiveVolunteerName('Sorawit P.');
        setCurrentTab('Map');
      }
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  // Deep Link URL parser helper
  const parseIncomingUrl = (url) => {
    if (!url) return;
    console.log("Intercepted incoming link:", url);
    try {
      const regex = /[?&]missionId=([^&#]+)/;
      const match = url.match(regex);
      if (match && match[1]) {
        const mId = decodeURIComponent(match[1]);
        setPendingMissionId(mId);
      }
    } catch (err) {
      console.error("Failed parsing link:", err);
    }
  };

  // Deep Link Listeners
  useEffect(() => {
    Linking.getInitialURL().then(url => {
      if (url) parseIncomingUrl(url);
    });

    const sub = Linking.addEventListener('url', (event) => {
      if (event.url) parseIncomingUrl(event.url);
    });

    return () => {
      sub.remove();
    };
  }, []);

  // Auto-focus mission once loaded
  useEffect(() => {
    if (pendingMissionId && missions.length > 0) {
      const found = missions.find(m => m.id === pendingMissionId);
      if (found) {
        setSelectedMissionId(pendingMissionId);
        Alert.alert(
          "Joined Mission Invite",
          `Focused on shoreline cleanup mission: "${found.title}".`
        );
      }
      setPendingMissionId(null);
    }
  }, [pendingMissionId, missions]);

  const handleLanguageChange = (lang) => {
    setUserLanguage(lang);
    console.log(`Language changed to: ${lang}`);
  };

  if (!session) {
    return (
      <SafeAreaView style={styles.container}>
        <StatusBar barStyle="light-content" backgroundColor="#050505" />
        <AuthScreen 
          onAuthSuccess={(newSession) => setSession(newSession)} 
          userLanguage={userLanguage}
          setUserLanguage={handleLanguageChange}
        />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#131313" />
      
      {/* Premium Dark Command Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.headerTitle}>{t('app_title', userLanguage)}</Text>
          <Text style={styles.headerSubtitle}>{t('app_subtitle', userLanguage)}</Text>
        </View>
        
        {/* Simple Role Indicator Badge */}
        <View style={styles.headerRight}>
          <View style={[styles.roleBadge, userRole === 'coordinator' && styles.roleBadgeCoordinator]}>
            <View style={[styles.statusIndicatorDot, { backgroundColor: userRole === 'coordinator' ? '#e3b5ff' : '#00fbfb' }]} />
            <Text style={styles.roleText}>
              {userRole === 'coordinator' ? t('role_coordinator', userLanguage).toUpperCase() : t('role_volunteer', userLanguage).toUpperCase()}
            </Text>
          </View>
        </View>
      </View>

      <View style={styles.content}>
        {currentTab === 'Map' && (
          <MapScreen 
            pins={pins} 
            userRole={userRole} 
            userLanguage={userLanguage} 
            missions={missions}
            selectedMissionId={selectedMissionId}
            setSelectedMissionId={setSelectedMissionId}
            profiles={profiles}
            activeVolunteerName={activeVolunteerName}
            setActiveVolunteerName={setActiveVolunteerName}
            setHideTabBar={setHideTabBar}
            cleanupZones={cleanupZones}
            t={t}
          />
        )}
        {currentTab === 'Alerts' && (
          <AlertsScreen alerts={alerts} userRole={userRole} userLanguage={userLanguage} backendUrl={BACKEND_URL} />
        )}
        {currentTab === 'Leaderboard' && (
          <LeaderboardScreen 
            pins={pins}
            missions={missions}
            selectedMissionId={selectedMissionId}
            setSelectedMissionId={setSelectedMissionId}
            profiles={profiles}
            userLanguage={userLanguage}
          />
        )}
        {currentTab === 'Control' && (
          <ControlScreen 
            userRole={userRole}
            setUserRole={setUserRole}
            userLanguage={userLanguage}
            handleLanguageChange={handleLanguageChange}
            activeVolunteerName={activeVolunteerName}
            setActiveVolunteerName={setActiveVolunteerName}
            profiles={profiles}
            session={session}
            pins={pins}
            missions={missions}
          />
        )}
      </View>

      {/* Navigation Tab Bar (Glassmorphic dark dashboard style) */}
      {!hideTabBar && (
        <View style={styles.tabBar}>
          <TouchableOpacity 
            style={[styles.tabItem, currentTab === 'Map' && styles.tabItemActive]} 
            onPress={() => setCurrentTab('Map')}
          >
            <Text style={[styles.tabText, currentTab === 'Map' && styles.tabTextActive]}>{t('tab_map', userLanguage)}</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={[styles.tabItem, currentTab === 'Alerts' && styles.tabItemActive]} 
            onPress={() => setCurrentTab('Alerts')}
          >
            <Text style={[styles.tabText, currentTab === 'Alerts' && styles.tabTextActive]}>{t('tab_alerts', userLanguage)}</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={[styles.tabItem, currentTab === 'Leaderboard' && styles.tabItemActive]} 
            onPress={() => setCurrentTab('Leaderboard')}
          >
            <Text style={[styles.tabText, currentTab === 'Leaderboard' && styles.tabTextActive]}>{t('tab_stats', userLanguage)}</Text>
          </TouchableOpacity>

          <TouchableOpacity 
            style={[styles.tabItem, currentTab === 'Control' && styles.tabItemActive]} 
            onPress={() => setCurrentTab('Control')}
          >
            <Text style={[styles.tabText, currentTab === 'Control' && styles.tabTextActive]}>{t('tab_control', userLanguage)}</Text>
          </TouchableOpacity>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#050505',
  },
  header: {
    height: 64,
    backgroundColor: '#131313',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  headerTitle: {
    color: '#ffffff',
    fontSize: 17,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  headerSubtitle: {
    color: '#b9cac9',
    fontSize: 10,
    marginTop: 1,
  },
  headerRight: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  roleBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(0, 251, 251, 0.25)',
    gap: 6,
  },
  roleBadgeCoordinator: {
    backgroundColor: 'rgba(227, 181, 255, 0.08)',
    borderColor: 'rgba(227, 181, 255, 0.25)',
  },
  statusIndicatorDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  roleText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    letterSpacing: 0.5,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  content: {
    flex: 1,
  },
  tabBar: {
    height: 56,
    backgroundColor: '#131313',
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
  },
  tabItem: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabItemActive: {
    borderBottomColor: '#00fbfb',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
  },
  tabText: {
    color: '#b9cac9',
    fontSize: 12,
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#00fbfb',
    fontWeight: 'bold',
  },
});
