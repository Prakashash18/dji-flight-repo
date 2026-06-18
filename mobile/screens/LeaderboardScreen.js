import React from 'react';
import { StyleSheet, Text, View, FlatList, ScrollView, TouchableOpacity, Share, Platform } from 'react-native';
import { parsePinParams, calculatePatrollerStats, getUnlockedBadges } from '../utils/statsHelper';
import { t } from '../utils/translations';

const mockOnlineVolunteers = [
  { id: '1', name: 'Sorawit P.' },
  { id: '2', name: 'Nattaporn S.' },
  { id: '4', name: 'Kadek W.' },
  { id: '6', name: 'Siti A.' },
];

export default function LeaderboardScreen({ pins = [], missions = [], selectedMissionId = null, setSelectedMissionId, profiles = [], userLanguage = 'en' }) {
  
  const handleShareMission = async (mission) => {
    try {
      const shareUrl = `coastalpatrol://register?missionId=${mission.id}`;
      const inviteMsg = userLanguage === 'en'
        ? `Join our beach cleanup mission: "${mission.title}"! Register here: ${shareUrl}`
        : `${t('share_invite', userLanguage)}: "${mission.title}"! ${shareUrl}`;
      await Share.share({
        message: inviteMsg,
        title: `Mission Invite: ${mission.title}`,
      });
    } catch (error) {
      console.log("Error sharing mission:", error.message);
    }
  };

  // Filter pins based on selected mission
  const filteredPins = pins.filter(p => {
    if (!p) return false;
    if (selectedMissionId !== null) {
      return p.mission_id === selectedMissionId;
    }
    return true;
  });

  // Calculate dynamic stats
  const completedPointsTotal = filteredPins.filter(p => p.status === 'cleaned' && !parsePinParams(p).is_mistake).length;
  const mistakesFlaggedTotal = filteredPins.filter(p => p.status === 'cleaned' && parsePinParams(p).is_mistake).length;
  const missionsCompletedTotal = missions.filter(m => {
    const mPins = pins.filter(p => p && p.mission_id === m.id);
    return mPins.length > 0 && mPins.every(p => p.status === 'cleaned');
  }).length;

  const totalPinsCount = filteredPins.length;

  // Calculate leaderboard statistics dynamically from database pins
  const calculateLeaderboard = () => {
    const statsMap = {};
    
    // Seed with onboarded/mock volunteers
    const volunteersList = profiles.filter(p => p.role === 'volunteer').length > 0
      ? profiles.filter(p => p.role === 'volunteer')
      : mockOnlineVolunteers;
      
    volunteersList.forEach(vol => {
      statsMap[vol.name] = {
        id: vol.id,
        name: vol.name,
        items: 0,
        active: true
      };
    });
    
    // Process pins to count points completed by each volunteer
    pins.forEach(pin => {
      if (pin && pin.status === 'cleaned') {
        const parsed = parsePinParams(pin);
        if (!parsed.is_mistake && parsed.assigned_to) {
          const name = parsed.assigned_to;
          if (!statsMap[name]) {
            statsMap[name] = { id: name, name: name, items: 0, active: false };
          }
          statsMap[name].items += 1;
        }
      }
    });
    
    return Object.values(statsMap).sort((a, b) => b.items - a.items);
  };

  const leaderboardData = calculateLeaderboard();

  const renderRankingItem = ({ item, index }) => {
    const isTopThree = index < 3;
    const rankColors = ['#FFD700', '#C0C0C0', '#CD7F32'];
    const rankColor = isTopThree ? rankColors[index] : '#8DA9C4';

    const volStats = calculatePatrollerStats(pins, missions, item.name);
    const volBadges = getUnlockedBadges(volStats);

    return (
      <View style={styles.rankCard}>
        <View style={styles.rankLeft}>
          <View style={[styles.rankNumberContainer, isTopThree && { borderColor: rankColor }]}>
            <Text style={[styles.rankNumber, { color: rankColor }]}>{index + 1}</Text>
          </View>
          <View style={styles.userInfo}>
            <Text style={styles.userName}>{item.name}</Text>
            <View style={styles.statusRow}>
              <View style={[styles.statusDot, { backgroundColor: item.active ? '#10B981' : '#4B5563' }]} />
              <Text style={styles.statusText}>{item.active ? t('vol_active', userLanguage) : t('vol_offline', userLanguage)}</Text>
            </View>
            {volBadges.length > 0 && (
              <View style={styles.badgeRowMini}>
                {volBadges.map(b => (
                  <Text key={b.id} title={b.title} style={styles.badgeMiniIcon}>{b.icon}</Text>
                ))}
              </View>
            )}
          </View>
        </View>
        
        <View style={styles.rankRight}>
          <Text style={styles.statsValue}>{item.items} <Text style={styles.statsLabel}>{item.items === 1 ? t('stats_point', userLanguage) : t('stats_points', userLanguage)}</Text></Text>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        
        {/* Header Section */}
        <Text style={styles.sectionHeader}>{t('analytics_header', userLanguage)}</Text>
        
        {/* Bento Box Stats Layout */}
        <View style={styles.bentoGrid}>
          {/* Card 1: Completed Points (Cyan Theme) */}
          <View style={[styles.bentoCard, styles.bentoCardPrimary]}>
            <Text style={styles.bentoTitle}>{t('stats_litter_completed', userLanguage)}</Text>
            <Text style={styles.bentoValue}>{completedPointsTotal} <Text style={styles.bentoValueSub}>{completedPointsTotal === 1 ? t('stats_point', userLanguage) : t('stats_points', userLanguage)}</Text></Text>
            <Text style={styles.bentoCaption}>{t('stats_db_sync', userLanguage)}</Text>
          </View>
          
          <View style={styles.bentoRightColumn}>
            {/* Card 2: Mistakes Flagged (Purple Theme) */}
            <View style={[styles.bentoCard, styles.bentoCardSecondary]}>
              <Text style={styles.bentoTitle}>{t('stats_mistakes_flagged', userLanguage)}</Text>
              <Text style={styles.bentoValueSmall}>{mistakesFlaggedTotal} <Text style={{ fontSize: 9 }}>{t('stats_mistakes', userLanguage).toUpperCase()}</Text></Text>
              <Text style={[styles.bentoValueSub, { marginTop: 2, fontSize: 8 }]}>{t('stats_false_audits', userLanguage).toUpperCase()}</Text>
            </View>
            
            {/* Card 3: Missions Completed (Green Theme) */}
            <View style={[styles.bentoCard, styles.bentoCardTertiary]}>
              <Text style={styles.bentoTitle}>{t('stats_missions_completed', userLanguage)}</Text>
              <Text style={styles.bentoValueSmall}>{missionsCompletedTotal} / {missions.length}</Text>
              <Text style={[styles.bentoValueSub, { marginTop: 2, fontSize: 8 }]}>{t('stats_100_runs', userLanguage).toUpperCase()}</Text>
            </View>
          </View>
        </View>

        {/* Missions History Feed */}
        <Text style={styles.sectionHeader}>{t('missions_history', userLanguage)}</Text>
        {missions.length === 0 ? (
          <View style={styles.noMissionsCard}>
            <Text style={styles.noMissionsText}>{t('no_history', userLanguage)}</Text>
          </View>
        ) : (
          <View style={styles.historyContainer}>
            {missions.map(m => {
              const missionPins = pins.filter(p => p && p.mission_id === m.id);
              const total = missionPins.length;
              const cleaned = missionPins.filter(p => p.status === 'cleaned').length;
              const progress = total > 0 ? cleaned / total : 0;
              const mistakes = missionPins.filter(p => p && parsePinParams(p).is_mistake).length;
              const isActive = selectedMissionId === m.id;

              return (
                <TouchableOpacity
                  key={m.id}
                  style={[styles.historyCard, isActive && styles.historyCardActive]}
                  onPress={() => setSelectedMissionId(m.id)}
                >
                  <View style={styles.historyHeader}>
                    <Text style={[styles.historyTitle, isActive && styles.historyTitleActive]} numberOfLines={1}>
                      {m.title}
                    </Text>
                    <View style={styles.headerRightContainer}>
                      <Text style={styles.historyDate}>
                        {new Date(m.mission_date).toLocaleDateString()}
                      </Text>
                      <TouchableOpacity 
                        style={styles.cardShareBtn} 
                        onPress={() => handleShareMission(m)}
                      >
                        <Text style={styles.cardShareBtnText}>🔗 SHARE</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                  <View style={styles.progressBarContainer}>
                    <View style={[styles.progressBar, { width: `${progress * 100}%` }]} />
                  </View>
                  <View style={styles.historyFooter}>
                    <Text style={styles.historyStats}>
                      {cleaned} / {total} {t('history_resolved_pins', userLanguage)}
                    </Text>
                    <Text style={styles.historyBags}>
                      {mistakes} {userLanguage === 'en' ? (mistakes === 1 ? 'mistake' : 'mistakes') : t('stats_mistakes', userLanguage).toLowerCase()}
                    </Text>
                  </View>
                </TouchableOpacity>
              );
            })}
            {selectedMissionId !== null && (
              <TouchableOpacity style={styles.clearFilterBtn} onPress={() => setSelectedMissionId(null)}>
                <Text style={styles.clearFilterBtnText}>{t('clear_filter', userLanguage)}</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Leaderboard Section */}
        <Text style={styles.sectionHeader}>{t('leaderboard_title', userLanguage)}</Text>
        
        {/* Leaderboard List */}
        <FlatList
          data={leaderboardData}
          keyExtractor={(item) => item.id.toString()}
          renderItem={renderRankingItem}
          scrollEnabled={false} // Handled by outer ScrollView
          contentContainerStyle={styles.listContainer}
        />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#050505',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  sectionHeader: {
    color: '#00fbfb',
    fontSize: 10,
    fontWeight: 'bold',
    textTransform: 'uppercase',
    marginBottom: 12,
    marginTop: 14,
    letterSpacing: 0.5,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  bentoGrid: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 12,
  },
  bentoCard: {
    backgroundColor: '#131313',
    borderRadius: 8,
    padding: 16,
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    justifyContent: 'space-between',
  },
  bentoCardPrimary: {
    flex: 1.1,
    height: 160,
    borderColor: '#00fbfb',
  },
  bentoRightColumn: {
    flex: 1,
    gap: 12,
    height: 160,
  },
  bentoCardSecondary: {
    flex: 1,
    paddingVertical: 12,
    borderColor: '#e3b5ff',
  },
  bentoCardTertiary: {
    flex: 1,
    paddingVertical: 12,
    borderColor: '#10B981',
  },
  bentoTitle: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: 'bold',
    textTransform: 'uppercase',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  bentoValue: {
    color: '#00fbfb',
    fontSize: 30,
    fontWeight: '800',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  bentoValueSmall: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    marginTop: 2,
  },
  bentoValueSub: {
    fontSize: 10,
    color: '#b9cac9',
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  bentoCaption: {
    color: '#10B981',
    fontSize: 9,
    fontWeight: '600',
    marginTop: 4,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  listContainer: {
    gap: 10,
  },
  rankCard: {
    backgroundColor: '#131313',
    borderRadius: 6,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  rankLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  rankNumberContainer: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  rankNumber: {
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  userInfo: {
    justifyContent: 'center',
  },
  userName: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 2,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  statusText: {
    color: '#b9cac9',
    fontSize: 8,
    fontWeight: 'bold',
    letterSpacing: 0.5,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  rankRight: {
    alignItems: 'flex-end',
  },
  statsValue: {
    color: '#00fbfb',
    fontSize: 13,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  statsLabel: {
    fontSize: 9,
    color: '#b9cac9',
    fontWeight: 'normal',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  noMissionsCard: {
    backgroundColor: '#131313',
    borderRadius: 6,
    padding: 20,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  noMissionsText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  historyContainer: {
    gap: 10,
    marginBottom: 8,
  },
  historyCard: {
    backgroundColor: '#131313',
    borderRadius: 6,
    padding: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  historyCardActive: {
    borderColor: '#00fbfb',
    backgroundColor: 'rgba(0, 251, 251, 0.06)',
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  historyTitle: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    flex: 1,
    marginRight: 10,
  },
  historyTitleActive: {
    color: '#00fbfb',
  },
  historyDate: {
    color: '#b9cac9',
    fontSize: 9,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  progressBarContainer: {
    height: 5,
    backgroundColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: 3,
    overflow: 'hidden',
    marginVertical: 6,
  },
  progressBar: {
    height: '100%',
    backgroundColor: '#10B981',
  },
  historyFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 2,
  },
  historyStats: {
    color: '#b9cac9',
    fontSize: 9,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  historyBags: {
    color: '#00fbfb',
    fontSize: 9,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    fontWeight: 'bold',
  },
  badgeRowMini: {
    flexDirection: 'row',
    marginTop: 4,
    gap: 4,
  },
  badgeMiniIcon: {
    fontSize: 12,
  },
  clearFilterBtn: {
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    borderWidth: 1,
    borderColor: '#EF4444',
    borderRadius: 8,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 4,
  },
  clearFilterBtnText: {
    color: '#EF4444',
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 0.5,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  headerRightContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  cardShareBtn: {
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(0, 251, 251, 0.25)',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  cardShareBtnText: {
    color: '#00fbfb',
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});
