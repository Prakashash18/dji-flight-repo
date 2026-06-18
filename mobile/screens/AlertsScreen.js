import React, { useState } from 'react';
import { StyleSheet, Text, View, FlatList, TextInput, TouchableOpacity, Keyboard, Alert, ScrollView, Platform } from 'react-native';

const MONOSPACE_FONT = Platform.OS === 'ios' ? 'Menlo' : 'monospace';

const localTranslations = {
  th: {
    "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
      "ประกาศทำความสะอาดชายหาด! พบขยะหนาแน่น กรุณาตรวจสอบแผนที่เพื่อดูเขตพื้นที่ที่ได้รับมอบหมาย",
    "New litter detected nearby. Assist if you are in the area.":
      "พบขยะใหม่ในบริเวณใกล้เคียง โปรดช่วยเหลือหากคุณอยู่ในพื้นที่"
  },
  id: {
    "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
      "Peringatan Pembersihan Pantai! Terdeteksi konsentrasi sampah yang tinggi. Harap periksa peta Anda untuk pembagian zona.",
    "New litter detected nearby. Assist if you are in the area.":
      "Sampah baru terdeteksi di dekat Anda. Bantu jika Anda berada di area tersebut."
  },
  tl: {
    "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
      "Babala sa Paglilinis ng Baybayin! Mataas na konsentrasyon ng basura ang natukoy. Pakisuri ang iyong mapa para sa mga nakatalagang zone.",
    "New litter detected nearby. Assist if you are in the area.":
      "May bagong basura na natukoy malapit sa iyo. Tumulong kung ikaw ay nasa lugar."
  },
  ms: {
    "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
      "Amaran Pembersihan Pantai! Sampah sarap dikesan dalam konsentrasi tinggi. Sila semak peta anda untuk tugasan zon.",
    "New litter detected nearby. Assist if you are in the area.":
      "Sampah baru dikesan berhampiran. Sila bantu jika anda berada di kawasan tersebut."
  },
  ta: {
    "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.":
      "கடற்கரை தூய்மைப்படுத்தல் எச்சரிக்கை! அதிக அளவு குப்பை கண்டறியப்பட்டுள்ளது. மண்டல ஒதுக்கீடுகளுக்கு உங்கள் வரைபடத்தை சரிபார்க்கவும்.",
    "New litter detected nearby. Assist if you are in the area.":
      "அருகில் புதிய குப்பை கண்டறியப்பட்டுள்ளது. நீங்கள் இப்பகுதியில் இருந்தால் உதவவும்."
  }
};

const uiTranslations = {
  en: {
    broadcast_header: "📢 Broadcast Coordinator Alert",
    feed_title: "Patrol Alert Feed",
    ack_read: "Acknowledge Read",
    ack_done: "✓ READ & ACKNOWLEDGED",
    placeholder_title: "Alert Title (e.g. Changi Beach Cleanup)",
    placeholder_msg: "Type alert message in English (will be translated via SEA-LION)...",
    btn_broadcast: "⚡ Translate & Broadcast",
    no_alerts: "No alerts posted yet. Check back later!",
    preview_label: "SEA-LION translation preview:",
    preview_placeholder: "Type message above to see preview...",
    tab_feed: "Alert Feed",
    tab_broadcast: "Broadcast Center"
  },
  th: {
    broadcast_header: "📢 ส่งข้อความแจ้งเตือนส่วนกลาง",
    feed_title: "ข่าวสารการแจ้งเตือน",
    ack_read: "รับทราบการแจ้งเตือน",
    ack_done: "✓ รับทราบการแจ้งเตือนแล้ว",
    placeholder_title: "หัวข้อแจ้งเตือน (เช่น แจ้งเตือนคลื่นลมแรง)",
    placeholder_msg: "ป้อนข้อความแจ้งเตือนภาษาอังกฤษ (จะแปลผ่านระบบ SEA-LION)...",
    btn_broadcast: "⚡ แปลและส่งข้อความ",
    no_alerts: "ไม่มีข้อความแจ้งเตือนในขณะนี้",
    preview_label: "ตัวอย่างการแปลโดย SEA-LION:",
    preview_placeholder: "พิมพ์ข้อความด้านบนเพื่อดูตัวอย่าง...",
    tab_feed: "รายการแจ้งเตือน",
    tab_broadcast: "ศูนย์กระจายข่าว"
  },
  id: {
    broadcast_header: "📢 Broadcast Peringatan Koordinator",
    feed_title: "Feed Peringatan Patroli",
    ack_read: "Konfirmasi Peringatan",
    ack_done: "✓ DIBACA & DIKONFIRMASI",
    placeholder_title: "Judul Peringatan (misal: Gelombang Tinggi)",
    placeholder_msg: "Tulis pesan dalam bahasa Inggris (akan diterjemahkan via SEA-LION)...",
    btn_broadcast: "⚡ Terjemahkan & Kirim",
    no_alerts: "Belum ada peringatan saat ini.",
    preview_label: "Pratinjau terjemahan SEA-LION:",
    preview_placeholder: "Tulis pesan di atas untuk melihat pratinjau...",
    tab_feed: "Feed Peringatan",
    tab_broadcast: "Pusat Siaran"
  },
  tl: {
    broadcast_header: "📢 Broadcast Alerto ng Tagapag-ugnay",
    feed_title: "Patrol Alert Feed",
    ack_read: "Acknowledge Read",
    ack_done: "✓ NABASA AT NA-ACKNOWLEDGE",
    placeholder_title: "Pamagat ng Alerto (hal. Babala sa Malalaking Alon)",
    placeholder_msg: "I-type ang mensahe sa Ingles (isasalin gamit ang SEA-LION)...",
    btn_broadcast: "⚡ Isalin at I-broadcast",
    no_alerts: "Walang mga alerto sa kasalukuyan.",
    preview_label: "SEA-LION translation preview:",
    preview_placeholder: "I-type ang mensahe sa itaas para makita ang preview...",
    tab_feed: "Alerto Feed",
    tab_broadcast: "Broadcast Center"
  },
  ms: {
    broadcast_header: "📢 Siarkan Amaran Penyelaras",
    feed_title: "Saluran Amaran Ronda",
    ack_read: "Sahkan Amaran",
    ack_done: "✓ DIBACA & DISAHKAN",
    placeholder_title: "Tajuk Amaran (cth: Gelombang Tinggi)",
    placeholder_msg: "Tulis amaran dalam bahasa Inggeris (akan diterjemahkan via SEA-LION)...",
    btn_broadcast: "⚡ Terjemah & Siar",
    no_alerts: "Tiada amaran aktif sekarang.",
    preview_label: "Pratonton terjemahan SEA-LION:",
    preview_placeholder: "Tulis mesej di atas untuk melihat pratonton...",
    tab_feed: "Saluran Amaran",
    tab_broadcast: "Pusat Siaran"
  },
  ta: {
    broadcast_header: "📢 ஒருங்கிணைப்பாளர் எச்சரிக்கையை பரப்பு",
    feed_title: "ரோந்து எச்சரிக்கை விவரங்கள்",
    ack_read: "எச்சரிக்கையை ஏற்றுக்கொள்",
    ack_done: "✓ வாசிக்கப்பட்டது",
    placeholder_title: "எச்சரிக்கை தலைப்பு (எ.கா. அலை சீற்றம் எச்சரிக்கை)",
    placeholder_msg: "எச்சரிக்கை செய்தியை ஆங்கிலத்தில் தட்டச்சு செய்யவும் (SEA-LION மூலம் மொழிபெயர்க்கப்படும்)...",
    btn_broadcast: "⚡ மொழிபெயர்த்து பரப்பு",
    no_alerts: "தற்போது எச்சரிக்கைகள் ஏதுமில்லை.",
    preview_label: "SEA-LION மொழிபெயர்ப்பு முன்னோட்டம்:",
    preview_placeholder: "முன்னோட்டத்தைக் காண மேலே செய்தியைத் தட்டச்சு செய்யவும்...",
    tab_feed: "எச்சரிக்கை ஊட்டம்",
    tab_broadcast: "பரப்புதல் மையம்"
  }
};

export default function AlertsScreen({ alerts, userLanguage, userRole, backendUrl }) {
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [previewTab, setPreviewTab] = useState('EN'); // 'EN' | 'TH' | 'ID' | 'TL'
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState(new Set());
  const [activeMode, setActiveMode] = useState('FEED'); // 'FEED' | 'BROADCAST'

  const t = (key) => {
    const lang = userLanguage || 'en';
    const dict = uiTranslations[lang] || uiTranslations['en'];
    return dict[key] || uiTranslations['en'][key] || key;
  };

  const getTranslatedMessage = (alertItem) => {
    const lang = userLanguage || 'en';
    if (lang === 'en') {
      return alertItem.message;
    }
    
    let trans = alertItem.translations ? alertItem.translations[lang] : null;
    
    // If the database translation is missing, look up a high-quality local translation
    if (!trans || trans.trim().startsWith('[') || trans.trim().startsWith('(')) {
      const cleanMsg = alertItem.message ? alertItem.message.trim() : '';
      if (localTranslations[lang] && localTranslations[lang][cleanMsg]) {
        return localTranslations[lang][cleanMsg];
      }
    }
    
    return trans || alertItem.message;
  };

  const getMockPreviewTranslation = (msg, lang) => {
    if (!msg) return t('preview_placeholder');
    switch (lang) {
      case 'TH': return `[THAI PREVIEW via SEA-LION]:\nพบขยะใหม่: ${msg}`;
      case 'ID': return `[INDONESIAN PREVIEW via SEA-LION]:\nTerdeteksi sampah baru: ${msg}`;
      case 'TL': return `[TAGALOG PREVIEW via SEA-LION]:\nMay nakitang basura: ${msg}`;
      default: return msg;
    }
  };

  const handleBroadcast = () => {
    if (!title.trim() || !message.trim()) {
      Alert.alert("Missing Fields", "Please enter both title and message before broadcasting.");
      return;
    }

    Alert.alert(
      "Confirm Broadcast Campaign",
      "This alert will be translated into Southeast Asian languages via SEA-LION API and sent in real-time to active volunteers. Proceed?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Translate & Broadcast",
          onPress: async () => {
            try {
              const res = await fetch(`${backendUrl}/api/alerts/broadcast`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, message })
              });
              
              if (!res.ok) {
                throw new Error("Server responded with error status");
              }
              
              Alert.alert("Success", "Alert translated and broadcasted to volunteer dashboard!");
              setTitle('');
              setMessage('');
              setActiveMode('FEED'); // Automatically go back to feed to see the broadcast
              Keyboard.dismiss();
            } catch (err) {
              console.error(err);
              Alert.alert("Broadcast Failed", "Failed to transmit message through server.");
            }
          }
        }
      ]
    );
  };

  const toggleAcknowledge = (id) => {
    setAcknowledgedAlerts(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const getLanguageFlag = (lang) => {
    switch (lang.toLowerCase()) {
      case 'th': return '🇹🇭 TH';
      case 'id': return '🇮🇩 ID';
      case 'tl': return '🇵🇭 TL';
      default: return '🇺🇸 EN';
    }
  };

  return (
    <View style={styles.container}>
      {/* Segmented Top Header Tab bar for Coordinators */}
      {userRole === 'coordinator' && (
        <View style={styles.topTabBar}>
          <TouchableOpacity 
            style={[styles.tabItem, activeMode === 'FEED' && styles.tabItemActive]} 
            onPress={() => setActiveMode('FEED')}
          >
            <Text style={[styles.tabItemText, activeMode === 'FEED' && styles.tabItemTextActive]}>
              {t('tab_feed').toUpperCase()}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.tabItem, activeMode === 'BROADCAST' && styles.tabItemActive]} 
            onPress={() => setActiveMode('BROADCAST')}
          >
            <Text style={[styles.tabItemText, activeMode === 'BROADCAST' && styles.tabItemTextActive]}>
              {t('tab_broadcast').toUpperCase()}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Render Alert Feed (for volunteers, or when in FEED mode) */}
      {(userRole !== 'coordinator' || activeMode === 'FEED') && (
        <View style={styles.feedSection}>
          <Text style={styles.sectionHeader}>{t('feed_title')}</Text>
          
          {alerts.length === 0 ? (
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>{t('no_alerts')}</Text>
            </View>
          ) : (
            <FlatList
              data={alerts}
              keyExtractor={(item) => item.id}
              contentContainerStyle={styles.listContent}
              renderItem={({ item }) => {
                const displayMsg = getTranslatedMessage(item);
                const isTranslated = userLanguage !== 'en' && item.translations && item.translations[userLanguage];
                const isAck = acknowledgedAlerts.has(item.id);
                
                return (
                  <View style={[styles.alertCard, isAck && styles.alertCardAck]}>
                    <View style={styles.cardHeader}>
                      <View style={styles.cardTitleRow}>
                        <Text style={styles.cardIcon}>🚨</Text>
                        <Text style={styles.cardTitle}>{item.title}</Text>
                      </View>
                      <Text style={styles.cardTime}>
                        {new Date(item.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </Text>
                    </View>
                    
                    <Text style={styles.cardBody}>{displayMsg}</Text>
                    
                    <View style={styles.cardFooter}>
                      {isTranslated ? (
                        <View style={styles.translationBadge}>
                          <Text style={styles.translationText}>
                            🦁 {getLanguageFlag(userLanguage)} Translated
                          </Text>
                        </View>
                      ) : (
                        <View style={styles.translationBadgeMock}>
                          <Text style={styles.translationTextMock}>
                            {getLanguageFlag(userLanguage)}
                          </Text>
                        </View>
                      )}

                      {/* Volunteer Read Acknowledgment button */}
                      <TouchableOpacity 
                        style={[styles.ackBtn, isAck && styles.ackBtnActive]} 
                        onPress={() => toggleAcknowledge(item.id)}
                      >
                        <Text style={[styles.ackBtnText, isAck && styles.ackBtnTextActive]}>
                          {isAck ? t('ack_done') : t('ack_read')}
                        </Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                );
              }}
            />
          )}
        </View>
      )}

      {/* Render Broadcast Center (only for coordinators in BROADCAST mode) */}
      {userRole === 'coordinator' && activeMode === 'BROADCAST' && (
        <ScrollView style={styles.broadcastSection} contentContainerStyle={{ paddingBottom: 30 }} showsVerticalScrollIndicator={false}>
          <View style={styles.broadcastForm}>
            <Text style={styles.formTitle}>{t('broadcast_header')}</Text>
            
            <TextInput
              style={styles.input}
              placeholder={t('placeholder_title')}
              placeholderTextColor="rgba(255, 255, 255, 0.3)"
              value={title}
              onChangeText={setTitle}
            />
            
            <TextInput
              style={[styles.input, styles.textArea]}
              placeholder={t('placeholder_msg')}
              placeholderTextColor="rgba(255, 255, 255, 0.3)"
              multiline
              numberOfLines={3}
              value={message}
              onChangeText={setMessage}
            />

            {/* Translation Preview Tabs */}
            <Text style={styles.previewLabel}>{t('preview_label')}</Text>
            <View style={styles.previewTabBar}>
              {['EN', 'TH', 'ID', 'TL'].map(tab => (
                <TouchableOpacity
                  key={tab}
                  style={[styles.previewTabItem, previewTab === tab && styles.previewTabActive]}
                  onPress={() => setPreviewTab(tab)}
                >
                  <Text style={[styles.previewTabText, previewTab === tab && styles.previewTabTextActive]}>
                    {tab}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
            
            <View style={styles.previewBox}>
              <Text style={styles.previewBoxText} numberOfLines={3}>
                {previewTab === 'EN' ? (message || t('preview_placeholder')) : getMockPreviewTranslation(message, previewTab)}
              </Text>
            </View>
            
            <TouchableOpacity style={styles.broadcastBtn} onPress={handleBroadcast}>
              <Text style={styles.broadcastBtnText}>{t('btn_broadcast')}</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#050505',
    padding: 16,
  },
  broadcastForm: {
    backgroundColor: '#131313',
    borderRadius: 8,
    padding: 16,
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    marginBottom: 16,
  },
  formTitle: {
    color: '#00fbfb',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 1,
    marginBottom: 12,
  },
  input: {
    backgroundColor: '#050505',
    color: '#ffffff',
    borderRadius: 4,
    paddingHorizontal: 12,
    height: 38,
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    marginBottom: 10,
  },
  textArea: {
    height: 64,
    paddingTop: 8,
    textAlignVertical: 'top',
  },
  previewLabel: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    marginBottom: 6,
  },
  previewTabBar: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  previewTabItem: {
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 4,
    backgroundColor: '#050505',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  previewTabActive: {
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    borderColor: '#00fbfb',
  },
  previewTabText: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  previewTabTextActive: {
    color: '#00fbfb',
  },
  previewBox: {
    backgroundColor: '#050505',
    borderRadius: 4,
    padding: 10,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.03)',
    marginBottom: 12,
  },
  previewBoxText: {
    color: '#b9cac9',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
    lineHeight: 14,
  },
  broadcastBtn: {
    backgroundColor: '#e3b5ff',
    height: 38,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  broadcastBtnText: {
    color: '#050505',
    fontWeight: 'bold',
    fontSize: 11,
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  feedSection: {
    flex: 1,
  },
  sectionHeader: {
    color: '#00fbfb',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    textTransform: 'uppercase',
    marginBottom: 12,
    letterSpacing: 0.5,
  },
  listContent: {
    paddingBottom: 20,
  },
  alertCard: {
    backgroundColor: '#131313',
    borderRadius: 6,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  alertCardAck: {
    borderColor: '#10B981',
    borderWidth: 1.5,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  cardTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  cardIcon: {
    fontSize: 14,
  },
  cardTitle: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  cardTime: {
    color: '#b9cac9',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
  },
  cardBody: {
    color: '#ffffff',
    fontSize: 12,
    lineHeight: 16,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
    paddingTop: 10,
  },
  translationBadge: {
    backgroundColor: 'rgba(245, 158, 11, 0.08)',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 0.5,
    borderColor: '#F59E0B',
  },
  translationBadgeMock: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 4,
  },
  translationText: {
    color: '#F59E0B',
    fontSize: 9,
    fontWeight: '600',
    fontFamily: MONOSPACE_FONT,
  },
  translationTextMock: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: '600',
    fontFamily: MONOSPACE_FONT,
  },
  ackBtn: {
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    paddingVertical: 5,
    paddingHorizontal: 10,
    borderRadius: 4,
  },
  ackBtnActive: {
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    borderColor: '#10B981',
    borderWidth: 1.5,
  },
  ackBtnText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  ackBtnTextActive: {
    color: '#10B981',
  },
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 11,
    textAlign: 'center',
    fontStyle: 'italic',
  },
  topTabBar: {
    flexDirection: 'row',
    backgroundColor: '#131313',
    borderRadius: 8,
    padding: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    marginBottom: 16,
  },
  tabItem: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 6,
  },
  tabItemActive: {
    backgroundColor: '#1d1d1d',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  tabItemText: {
    color: '#b9cac9',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  tabItemTextActive: {
    color: '#00fbfb',
  },
  broadcastSection: {
    flex: 1,
  },
});
