import React, { useState } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, TextInput, ScrollView, Platform, Alert } from 'react-native';
import { supabase } from '../App';
import { calculatePatrollerStats, getUnlockedBadges } from '../utils/statsHelper';
import { t } from '../utils/translations';

const MONOSPACE_FONT = Platform.OS === 'ios' ? 'Menlo' : 'monospace';

const languages = [
  { code: 'en', flag: '🇺🇸', name: 'English' },
  { code: 'th', flag: '🇹🇭', name: 'ไทย' },
  { code: 'id', flag: '🇮🇩', name: 'Bahasa' },
  { code: 'tl', flag: '🇵🇭', name: 'Tagalog' },
  { code: 'ms', flag: '🇲🇾', name: 'Melayu' },
  { code: 'ta', flag: '🇮🇳', name: 'தமிழ்' }
];

const localControlTranslations = {
  en: {
    success: "Success",
    error: "Error",
    update_failed: "Update Failed",
    role_updated: "Profile updated to",
    invalid_name: "Invalid Name",
    enter_valid_name: "Please enter a valid patroller name.",
    onboard_failed: "Onboarding Failed",
    onboard_success: "Volunteer onboarded successfully!",
    unexpected_error: "An unexpected error occurred."
  },
  th: {
    success: "สำเร็จ",
    error: "ข้อผิดพลาด",
    update_failed: "อัปเดตไม่สำเร็จ",
    role_updated: "อัปเดตบทบาทผู้ใช้งานเป็น",
    invalid_name: "ชื่อไม่ถูกต้อง",
    enter_valid_name: "กรุณากรอกชื่อและนามสกุลจริงของเจ้าหน้าที่",
    onboard_failed: "ลงทะเบียนไม่สำเร็จ",
    onboard_success: "ลงทะเบียนอาสาสมัครเรียบร้อยแล้ว!",
    unexpected_error: "เกิดข้อผิดพลาดที่ไม่คาดคิด"
  },
  id: {
    success: "Sukses",
    error: "Error",
    update_failed: "Gagal Mengupdate",
    role_updated: "Profil diperbarui menjadi",
    invalid_name: "Nama Tidak Valid",
    enter_valid_name: "Silakan masukkan nama petugas patroli yang valid.",
    onboard_failed: "Gagal Mendaftarkan",
    onboard_success: "Relawan berhasil didaftarkan!",
    unexpected_error: "Terjadi kesalahan yang tidak terduga."
  },
  tl: {
    success: "Tagumpay",
    error: "Error",
    update_failed: "Bigo ang Pag-update",
    role_updated: "Na-update ang profile sa",
    invalid_name: "Di-wastong Pangalan",
    enter_valid_name: "Mangyaring maglagay ng wastong pangalan ng patroller.",
    onboard_failed: "Bigo ang Pagrehistro",
    onboard_success: "Matagumpay na nairehistro ang boluntaryo!",
    unexpected_error: "Isang hindi inaasahang error ang naganap."
  },
  ms: {
    success: "Sukses",
    error: "Ralat",
    update_failed: "Kemas Kini Gagal",
    role_updated: "Profil dikemas kini kepada",
    invalid_name: "Nama Tidak Sah",
    enter_valid_name: "Sila masukkan nama petugas yang sah.",
    onboard_failed: "Pendaftaran Gagal",
    onboard_success: "Sukarelawan berjaya didaftarkan!",
    unexpected_error: "Ralat tidak dijangka berlaku."
  },
  ta: {
    success: "வெற்றி",
    error: "பிழை",
    update_failed: "சுயவிவர இடுகை தோல்வி",
    role_updated: "சுயவிவரம் மாற்றப்பட்டது:",
    invalid_name: "தவறான பெயர்",
    enter_valid_name: "தயவுசெய்து சரியான பெயரை உள்ளிடவும்.",
    onboard_failed: "பதிவு தோல்வியடைந்தது",
    onboard_success: "தொண்டர் வெற்றிகரமாக பதிவு செய்யப்பட்டார்!",
    unexpected_error: "எதிர்பாராத பிழை ஏற்பட்டது."
  }
};

const ct = (key, lang) => {
  const dict = localControlTranslations[lang] || localControlTranslations.en;
  return dict[key] || localControlTranslations.en[key] || key;
};

export default function ControlScreen({
  userRole,
  setUserRole,
  userLanguage,
  handleLanguageChange,
  activeVolunteerName,
  setActiveVolunteerName,
  profiles = [],
  session,
  pins = [],
  missions = []
}) {
  const [newOnboardName, setNewOnboardName] = useState('');
  const [isOnboarding, setIsOnboarding] = useState(false);

  const handleRoleSwitch = async (newRole) => {
    if (session?.user) {
      const { error } = await supabase
        .from('profiles')
        .update({ role: newRole })
        .eq('id', session.user.id);
      
      if (error) {
        Alert.alert(ct('update_failed', userLanguage), error.message);
      } else {
        setUserRole(newRole);
        Alert.alert(ct('success', userLanguage), `${ct('role_updated', userLanguage)} ${newRole.toUpperCase()}!`);
      }
    } else {
      setUserRole(newRole);
    }
  };

  const handleSignOut = async () => {
    try {
      const { error } = await supabase.auth.signOut();
      if (error) {
        Alert.alert(ct('error', userLanguage), error.message);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleOnboardVolunteer = async () => {
    if (!newOnboardName || newOnboardName.trim() === '') {
      Alert.alert(ct('invalid_name', userLanguage), ct('enter_valid_name', userLanguage));
      return;
    }
    const name = newOnboardName.trim();
    setIsOnboarding(true);
    
    try {
      const { error } = await supabase
        .from('profiles')
        .insert({
          name: name,
          role: 'volunteer',
          preferred_language: userLanguage
        });

      if (error) {
        Alert.alert(ct('onboard_failed', userLanguage), error.message);
      } else {
        Alert.alert(ct('success', userLanguage), `"${name}" ${ct('onboard_success', userLanguage)}`);
        setNewOnboardName('');
      }
    } catch (err) {
      console.error(err);
      Alert.alert(ct('error', userLanguage), ct('unexpected_error', userLanguage));
    } finally {
      setIsOnboarding(false);
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        <Text style={styles.sectionHeader}>{t('system_config', userLanguage)}</Text>

        {/* 1. ROLE SWITCHER */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('profile_title', userLanguage)}</Text>
          <Text style={styles.cardDesc}>{t('profile_desc', userLanguage)}</Text>
          <View style={styles.roleToggleContainer}>
            <TouchableOpacity 
              style={[styles.roleTab, userRole === 'volunteer' && styles.roleTabActiveVolunteer]}
              onPress={() => handleRoleSwitch('volunteer')}
            >
              <View style={[styles.dot, { backgroundColor: userRole === 'volunteer' ? '#00fbfb' : '#3a4a49' }]} />
              <Text style={[styles.roleTabText, userRole === 'volunteer' && styles.roleTabTextActive]}>
                {t('role_volunteer_tab', userLanguage)}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity 
              style={[styles.roleTab, userRole === 'coordinator' && styles.roleTabActiveCoordinator]}
              onPress={() => handleRoleSwitch('coordinator')}
            >
              <View style={[styles.dot, { backgroundColor: userRole === 'coordinator' ? '#e3b5ff' : '#3a4a49' }]} />
              <Text style={[styles.roleTabText, userRole === 'coordinator' && styles.roleTabTextActive]}>
                {t('role_coordinator_tab', userLanguage)}
              </Text>
            </TouchableOpacity>
          </View>
        </View>

        {/* 2. LANGUAGE TRANSLATION GRID */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('trans_title', userLanguage)}</Text>
          <Text style={styles.cardDesc}>{t('trans_desc', userLanguage)}</Text>
          <View style={styles.langGrid}>
            {languages.map(lang => {
              const isActive = userLanguage === lang.code;
              return (
                <TouchableOpacity
                  key={lang.code}
                  style={[styles.langCell, isActive && styles.langCellActive]}
                  onPress={() => handleLanguageChange(lang.code)}
                >
                  <Text style={styles.langFlag}>{lang.flag}</Text>
                  <Text style={[styles.langName, isActive && styles.langNameActive]}>{lang.name}</Text>
                  <Text style={styles.langCode}>{lang.code.toUpperCase()}</Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>

        {/* 3. AUTHENTICATED IDENTITY DETAILS */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('identity_title', userLanguage)}</Text>
          <Text style={styles.cardDesc}>{t('identity_desc', userLanguage)}</Text>
          <View style={styles.identityRow}>
            <Text style={styles.identityLabel}>{t('identity_name', userLanguage)}</Text>
            <Text style={styles.identityValue}>{activeVolunteerName}</Text>
          </View>
          <View style={styles.identityRow}>
            <Text style={styles.identityLabel}>{t('identity_email', userLanguage)}</Text>
            <Text style={styles.identityValue}>{session?.user?.email}</Text>
          </View>
          <View style={styles.identityRow}>
            <Text style={styles.identityLabel}>{t('identity_userid', userLanguage)}</Text>
            <Text style={styles.identityValueMono} numberOfLines={1}>{session?.user?.id}</Text>
          </View>
        </View>

        {/* Achievements / Milestones Card */}
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{t('milestones_title', userLanguage)}</Text>
          <Text style={styles.cardDesc}>{t('milestones_desc', userLanguage)}</Text>
          
          <View style={styles.achievementsRow}>
            <View style={styles.statBox}>
              <Text style={styles.statBoxVal}>{calculatePatrollerStats(pins, missions, activeVolunteerName).completedPoints}</Text>
              <Text style={styles.statBoxLbl}>{t('milestone_points', userLanguage)}</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statBoxVal}>{calculatePatrollerStats(pins, missions, activeVolunteerName).mistakesFlagged}</Text>
              <Text style={styles.statBoxLbl}>{t('milestone_mistakes', userLanguage)}</Text>
            </View>
            <View style={styles.statBox}>
              <Text style={styles.statBoxVal}>{calculatePatrollerStats(pins, missions, activeVolunteerName).missionsDone}</Text>
              <Text style={styles.statBoxLbl}>{t('milestone_missions', userLanguage)}</Text>
            </View>
          </View>

          <Text style={[styles.cardTitle, { marginTop: 16, fontSize: 10, letterSpacing: 0.5 }]}>{t('system_badges', userLanguage)}</Text>
          {getUnlockedBadges(calculatePatrollerStats(pins, missions, activeVolunteerName)).length === 0 ? (
            <Text style={styles.noBadgesText}>{t('no_badges', userLanguage)}</Text>
          ) : (
            <View style={styles.badgesGrid}>
              {getUnlockedBadges(calculatePatrollerStats(pins, missions, activeVolunteerName)).map(badge => (
                <View key={badge.id} style={[styles.badgeItem, { borderColor: badge.color }]}>
                  <Text style={styles.badgeIcon}>{badge.icon}</Text>
                  <View style={styles.badgeInfo}>
                    <Text style={styles.badgeTitle}>{badge.title}</Text>
                    <Text style={styles.badgeDesc}>{badge.desc}</Text>
                  </View>
                </View>
              ))}
            </View>
          )}
        </View>

        {/* 4. COORDINATOR ACTIONS (Coordinator only) */}
        {userRole === 'coordinator' && (
          <View style={styles.card}>
            <Text style={styles.cardTitle}>{t('onboard_title', userLanguage)}</Text>
            <Text style={styles.cardDesc}>{t('onboard_desc', userLanguage)}</Text>
            
            <View style={styles.onboardForm}>
              <TextInput
                style={styles.onboardInput}
                placeholder={t('onboard_placeholder', userLanguage)}
                placeholderTextColor="rgba(255, 255, 255, 0.3)"
                value={newOnboardName}
                onChangeText={setNewOnboardName}
              />
              <TouchableOpacity 
                style={[styles.onboardBtn, isOnboarding && styles.onboardBtnDisabled]} 
                onPress={handleOnboardVolunteer}
                disabled={isOnboarding}
              >
                <Text style={styles.onboardBtnText}>
                  {isOnboarding ? t('onboard_btn_loading', userLanguage) : t('onboard_btn', userLanguage)}
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        )}

        {/* 5. LOG OUT ACTION */}
        <TouchableOpacity style={styles.signOutBtn} onPress={handleSignOut}>
          <Text style={styles.signOutBtnText}>{t('logout_btn', userLanguage)}</Text>
        </TouchableOpacity>
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
    color: '#ffffff',
    fontSize: 16,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    marginBottom: 16,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  card: {
    backgroundColor: '#131313',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    padding: 16,
    marginBottom: 16,
  },
  cardTitle: {
    color: '#00fbfb',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 1,
    marginBottom: 4,
  },
  cardDesc: {
    color: '#b9cac9',
    fontSize: 10,
    lineHeight: 14,
    marginBottom: 14,
  },
  roleToggleContainer: {
    flexDirection: 'row',
    backgroundColor: '#050505',
    borderRadius: 4,
    padding: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  roleTab: {
    flex: 1,
    flexDirection: 'row',
    height: 38,
    borderRadius: 3,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  roleTabActiveVolunteer: {
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(0, 251, 251, 0.2)',
  },
  roleTabActiveCoordinator: {
    backgroundColor: 'rgba(227, 181, 255, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(227, 181, 255, 0.2)',
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  roleTabText: {
    color: '#b9cac9',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  roleTabTextActive: {
    color: '#ffffff',
  },
  langGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  langCell: {
    width: '48%',
    backgroundColor: '#050505',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    padding: 10,
    alignItems: 'center',
    flexDirection: 'row',
    gap: 10,
  },
  langCellActive: {
    borderColor: '#00fbfb',
    backgroundColor: 'rgba(0, 251, 251, 0.05)',
  },
  langFlag: {
    fontSize: 16,
  },
  langName: {
    color: '#b9cac9',
    fontSize: 12,
    flex: 1,
  },
  langNameActive: {
    color: '#ffffff',
    fontWeight: 'bold',
  },
  langCode: {
    color: 'rgba(255, 255, 255, 0.3)',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
  },
  emptyText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 11,
    textAlign: 'center',
    marginVertical: 10,
    fontStyle: 'italic',
  },
  patrollerList: {
    flexDirection: 'column',
    gap: 8,
  },
  patrollerItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#050505',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    padding: 10,
    gap: 12,
  },
  patrollerItemActive: {
    borderColor: '#e3b5ff',
    backgroundColor: 'rgba(227, 181, 255, 0.05)',
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#201f1f',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  avatarActive: {
    backgroundColor: '#e3b5ff',
    borderColor: '#e3b5ff',
  },
  avatarText: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  avatarTextActive: {
    color: '#050505',
    fontWeight: '800',
  },
  patrollerName: {
    color: '#b9cac9',
    fontSize: 12,
    flex: 1,
  },
  patrollerNameActive: {
    color: '#ffffff',
    fontWeight: 'bold',
  },
  activeLabel: {
    color: '#e3b5ff',
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  onboardForm: {
    flexDirection: 'column',
    gap: 10,
  },
  onboardInput: {
    backgroundColor: '#050505',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    color: '#ffffff',
    borderRadius: 4,
    paddingHorizontal: 12,
    height: 38,
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
  },
  onboardBtn: {
    backgroundColor: '#e3b5ff',
    borderRadius: 4,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
  },
  onboardBtnDisabled: {
    opacity: 0.5,
  },
  onboardBtnText: {
    color: '#050505',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  identityRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  identityLabel: {
    color: '#b9cac9',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
  },
  identityValue: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold',
  },
  identityValueMono: {
    color: '#00fbfb',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
  },
  signOutBtn: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1.5,
    borderColor: '#EF4444',
    borderRadius: 4,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
    marginBottom: 16,
  },
  signOutBtnText: {
    color: '#EF4444',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  achievementsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  statBox: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: '#0c0c0c',
    paddingVertical: 10,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    marginHorizontal: 4,
  },
  statBoxVal: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#00fbfb',
    fontFamily: MONOSPACE_FONT,
  },
  statBoxLbl: {
    fontSize: 8,
    color: '#b9cac9',
    marginTop: 4,
    fontWeight: 'bold',
    textAlign: 'center',
  },
  noBadgesText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 10,
    textAlign: 'center',
    paddingVertical: 12,
    fontFamily: MONOSPACE_FONT,
  },
  badgesGrid: {
    flexDirection: 'column',
    gap: 8,
    marginTop: 8,
  },
  badgeItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.02)',
    borderWidth: 1,
    borderRadius: 4,
    padding: 8,
  },
  badgeIcon: {
    fontSize: 20,
    marginRight: 10,
  },
  badgeInfo: {
    flex: 1,
  },
  badgeTitle: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold',
  },
  badgeDesc: {
    color: '#b9cac9',
    fontSize: 9,
    marginTop: 2,
  },
});
