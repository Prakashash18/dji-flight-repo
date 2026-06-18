import React, { useState } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ScrollView, ActivityIndicator, Alert, Platform } from 'react-native';
import { supabase } from '../App';

const MONOSPACE_FONT = Platform.OS === 'ios' ? 'Menlo' : 'monospace';

const localAuthTranslations = {
  en: {
    app_title: "🌊 Coastal Patrol",
    app_subtitle: "Beach Patrol System Terminal",
    tab_signin: "SIGN IN",
    tab_signup: "SIGN UP",
    title_signin: "SECURE SYSTEM AUTHORIZATION",
    title_signup: "NEW PATROLLER REGISTRATION",
    desc_signin: "Enter credentials to authorize access to the coastal georeferenced data.",
    desc_signup: "Register your patroller identity in the central directory database.",
    label_name: "FULL NAME",
    label_email: "EMAIL ADDRESS",
    label_password: "PASSWORD",
    label_role: "PATROLLER ROLE LEVEL",
    role_volunteer: "VOLUNTEER",
    role_coordinator: "COORDINATOR",
    btn_signin: "AUTHORIZE SYSTEM ENTRY ➔",
    btn_signup: "CREATE DATABASE PROFILE ➔",
    missing_fields: "Missing Fields",
    missing_fields_desc: "Please enter both email and password.",
    missing_name: "Missing Name",
    missing_name_desc: "Please enter your full name.",
    signin_failed: "Sign In Failed",
    signup_failed: "Sign Up Failed",
    warning: "Warning",
    profile_fail: "Account created, but profile mapping failed: ",
    success_title: "Account Created",
    success_desc: "Your patroller account has been registered successfully! Please log in.",
    err_title: "Auth Error",
    err_desc: "An unexpected error occurred during authentication."
  },
  th: {
    app_title: "🌊 ลาดตระเวนชายฝั่ง",
    app_subtitle: "ศูนย์เชื่อมต่อระบบลาดตระเวนชายหาด",
    tab_signin: "เข้าสู่ระบบ",
    tab_signup: "ลงทะเบียน",
    title_signin: "สิทธิ์การเข้าถึงระบบที่ปลอดภัย",
    title_signup: "ลงทะเบียนเจ้าหน้าที่ลาดตระเวนใหม่",
    desc_signin: "ป้อนข้อมูลประจำตัวเพื่ออนุญาตการเข้าถึงข้อมูลอ้างอิงทางภูมิศาสตร์ชายฝั่ง",
    desc_signup: "ลงทะเบียนบัญชีเจ้าหน้าที่ลาดตระเวนในฐานข้อมูลหลัก",
    label_name: "ชื่อ-นามสกุลจริง",
    label_email: "ที่อยู่อีเมล",
    label_password: "รหัสผ่าน",
    label_role: "ระดับสิทธิ์เจ้าหน้าที่",
    role_volunteer: "อาสาสมัคร",
    role_coordinator: "ผู้ประสานงาน",
    btn_signin: "ยืนยันเข้าใช้งานระบบ ➔",
    btn_signup: "สร้างโปรไฟล์ฐานข้อมูล ➔",
    missing_fields: "ข้อมูลไม่ครบถ้วน",
    missing_fields_desc: "กรุณากรอกทั้งอีเมลและรหัสผ่าน",
    missing_name: "กรุณาระบุชื่อ",
    missing_name_desc: "กรุณากรอกชื่อและนามสกุลจริงของคุณ",
    signin_failed: "เข้าสู่ระบบไม่สำเร็จ",
    signup_failed: "ลงทะเบียนไม่สำเร็จ",
    warning: "คำเตือน",
    profile_fail: "สร้างบัญชีแล้ว แต่ระบบสร้างโปรไฟล์ล้มเหลว: ",
    success_title: "ลงทะเบียนสำเร็จ",
    success_desc: "ลงทะเบียนบัญชีลาดตระเวนของคุณเรียบร้อยแล้ว! กรุณาเข้าสู่ระบบ",
    err_title: "ระบบขัดข้อง",
    err_desc: "เกิดข้อผิดพลาดที่ไม่คาดคิดระหว่างการตรวจสอบสิทธิ์"
  },
  id: {
    app_title: "🌊 Patroli Pantai",
    app_subtitle: "Terminal Sistem Patroli Pantai",
    tab_signin: "MASUK",
    tab_signup: "DAFTAR",
    title_signin: "OTORISASI SISTEM KEAMANAN",
    title_signup: "REGISTRASI PETUGAS BARU",
    desc_signin: "Masukkan kredensial untuk mengakses data georeferensi pantai.",
    desc_signup: "Daftarkan identitas petugas patroli Anda di database direktori pusat.",
    label_name: "NAMA LENGKAP",
    label_email: "ALAMAT EMAIL",
    label_password: "KATA SANDI",
    label_role: "LEVEL AKSES PETUGAS",
    role_volunteer: "RELAWAN",
    role_coordinator: "KOORDINATOR",
    btn_signin: "OTORISASI MASUK SISTEM ➔",
    btn_signup: "BUAT PROFIL DATABASE ➔",
    missing_fields: "Data Kurang",
    missing_fields_desc: "Silakan masukkan email dan kata sandi.",
    missing_name: "Nama Kurang",
    missing_name_desc: "Silakan masukkan nama lengkap Anda.",
    signin_failed: "Gagal Masuk",
    signup_failed: "Gagal Daftar",
    warning: "Peringatan",
    profile_fail: "Akun dibuat, tetapi gagal memetakan profil: ",
    success_title: "Akun Dibuat",
    success_desc: "Akun petugas patroli Anda telah terdaftar! Silakan masuk.",
    err_title: "Error Autentikasi",
    err_desc: "Terjadi kesalahan yang tidak terduga saat autentikasi."
  },
  tl: {
    app_title: "🌊 Patrol sa Baybayin",
    app_subtitle: "Terminal ng Sistema ng Patrol",
    tab_signin: "MAG-LOG IN",
    tab_signup: "MAG-REGISTER",
    title_signin: "SEGURO NA OTORISASYON NG SISTEMA",
    title_signup: "PAGPAPAREHISTRO NG BAGONG PATROLLER",
    desc_signin: "Ipasok ang mga kredensyal upang pahintulutan ang pag-access sa georeferenced data.",
    desc_signup: "Irehistro ang iyong patroller identity sa database ng central directory.",
    label_name: "BUONG PANGALAN",
    label_email: "EMAIL ADDRESS",
    label_password: "PASSWORD",
    label_role: "ANTAS NG PAPEL NG PATROLLER",
    role_volunteer: "BOLUNTARYO",
    role_coordinator: "TAGAPAG-UGNAY",
    btn_signin: "PAHINTULUTAN ANG PAGPASOK ➔",
    btn_signup: "GUMAWA NG DATABASE PROFILE ➔",
    missing_fields: "Kulang na Impormasyon",
    missing_fields_desc: "Mangyaring ilagay ang parehong email at password.",
    missing_name: "Kulang na Pangalan",
    missing_name_desc: "Mangyaring ilagay ang iyong buong pangalan.",
    signin_failed: "Bigo ang Pag-sign In",
    signup_failed: "Bigo ang Pagrehistro",
    warning: "Babala",
    profile_fail: "Gawa na ang account, ngunit bigo sa pagma-map ng profile: ",
    success_title: "Nagawa na ang Account",
    success_desc: "Matagumpay na nairehistro ang iyong patroller account! Mangyaring mag-log in.",
    err_title: "Error sa Auth",
    err_desc: "Isang hindi inaasahang error ang naganap habang nagpapatunay."
  },
  ms: {
    app_title: "🌊 Patroli Pantai",
    app_subtitle: "Terminal Sistem Patroli Pantai",
    tab_signin: "LOG MASUK",
    tab_signup: "DAFTAR",
    title_signin: "KEBENARAN SISTEM KESELAMATAN",
    title_signup: "PENDAFTARAN PETUGAS BARU",
    desc_signin: "Masukkan kredensial untuk membenarkan akses ke data pantai.",
    desc_signup: "Daftar identiti petugas rondaan anda di pangkalan data pusat.",
    label_name: "NAMA PENUH",
    label_email: "ALAMAT EMEL",
    label_password: "KATA LALUAN",
    label_role: "LEVEL AKSES PETUGAS",
    role_volunteer: "SUKARELAWAN",
    role_coordinator: "PENYELARAS",
    btn_signin: "BENARKAN KEMASUKAN SISTEM ➔",
    btn_signup: "BINA PROFIL DATABASE ➔",
    missing_fields: "Maklumat Tidak Lengkap",
    missing_fields_desc: "Sila masukkan emel dan kata laluan.",
    missing_name: "Nama Tidak Lengkap",
    missing_name_desc: "Sila masukkan nama penuh anda.",
    signin_failed: "Gagal Log Masuk",
    signup_failed: "Gagal Mendaftar",
    warning: "Amaran",
    profile_fail: "Akaun dibuat, tetapi gagal memetakan profil: ",
    success_title: "Akaun Dicipta",
    success_desc: "Akaun petugas rondaan anda berjaya didaftarkan! Sila log masuk.",
    err_title: "Ralat Autentikasi",
    err_desc: "Ralat tidak dijangka berlaku semasa autentikasi."
  },
  ta: {
    app_title: "🌊 கடலோரக் காவல்",
    app_subtitle: "கடற்கரை கண்காணிப்பு அமைப்பு முனையம்",
    tab_signin: "உள்நுழை",
    tab_signup: "பதிவு செய்",
    title_signin: "பாதுகாப்பான கணினி அங்கீகாரம்",
    title_signup: "புதிய ரோந்துப் பணியாளர் பதிவு",
    desc_signin: "கடலோர தரவுகளை அணுக உங்கள் உள்நுழைவு விவரங்களை உள்ளிடவும்.",
    desc_signup: "மத்திய கோப்பக தரவுத்தளத்தில் உங்கள் ரோந்துப் பணியாளர் அடையாளத்தை பதிவு செய்யவும்.",
    label_name: "முழு பெயர்",
    label_email: "மின்னஞ்சல் முகவரி",
    label_password: "கடவுச்சொல்",
    label_role: "ரோந்துப் பணியாளர் நிலை",
    role_volunteer: "தொண்டர்",
    role_coordinator: "ஒருங்கிணைப்பாளர்",
    btn_signin: "கணினிக்குள் நுழைய அனுமதி ➔",
    btn_signup: "தரவுத்தள சுயவிவரத்தை உருவாக்கு ➔",
    missing_fields: "விவரங்கள் விடுபட்டுள்ளன",
    missing_fields_desc: "மின்னஞ்சல் மற்றும் கடவுச்சொல் இரண்டையும் உள்ளிடவும்.",
    missing_name: "பெயர் விடுபட்டுள்ளது",
    missing_name_desc: "உங்கள் முழுப் பெயரை உள்ளிடவும்.",
    signin_failed: "உள்நுழைவு தோல்வி",
    signup_failed: "பதிவு தோல்வி",
    warning: "எச்சரிக்கை",
    profile_fail: "கணக்கு உருவாக்கப்பட்டது, சுயவிவர வரைபடம் தோல்வியடைந்தது: ",
    success_title: "கணக்கு உருவாக்கப்பட்டது",
    success_desc: "உங்கள் ரோந்துப் பணியாளர் கணக்கு வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது! தயவுசெய்து உள்நுழையவும்.",
    err_title: "அங்கீகாரப் பிழை",
    err_desc: "அங்கீகாரத்தின் போது எதிர்பாராத பிழை ஏற்பட்டது."
  }
};

const at = (key, lang) => {
  const dict = localAuthTranslations[lang] || localAuthTranslations.en;
  return dict[key] || localAuthTranslations.en[key] || key;
};

export default function AuthScreen({ onAuthSuccess, userLanguage = 'en', setUserLanguage }) {
  const [activeTab, setActiveTab] = useState('signin'); // 'signin' | 'signup'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('volunteer'); // 'volunteer' | 'coordinator'
  const [isLoading, setIsLoading] = useState(false);

  const handleAuth = async () => {
    if (!email || !password) {
      Alert.alert(at('missing_fields', userLanguage), at('missing_fields_desc', userLanguage));
      return;
    }

    if (activeTab === 'signup' && !name) {
      Alert.alert(at('missing_name', userLanguage), at('missing_name_desc', userLanguage));
      return;
    }

    setIsLoading(true);

    try {
      if (activeTab === 'signin') {
        // Sign In
        const { data, error } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password: password,
        });

        if (error) {
          Alert.alert(at('signin_failed', userLanguage), error.message);
        } else if (data.session) {
          onAuthSuccess(data.session);
        }
      } else {
        // Sign Up
        const { data, error } = await supabase.auth.signUp({
          email: email.trim(),
          password: password,
        });

        if (error) {
          Alert.alert(at('signup_failed', userLanguage), error.message);
        } else if (data.user) {
          // Create matching profile with default language
          const { error: profileError } = await supabase
            .from('profiles')
            .insert({
              id: data.user.id,
              name: name.trim(),
              role: role,
              preferred_language: userLanguage
            });

          if (profileError) {
            console.error("Profile creation failed:", profileError);
            Alert.alert(at('warning', userLanguage), at('profile_fail', userLanguage) + profileError.message);
          } else {
            Alert.alert(at('success_title', userLanguage), at('success_desc', userLanguage));
            setActiveTab('signin');
            setPassword('');
          }
        }
      }
    } catch (err) {
      console.error(err);
      Alert.alert(at('err_title', userLanguage), at('err_desc', userLanguage));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} keyboardShouldPersistTaps="handled">
        {/* Language selector row */}
        <View style={styles.langSelectorRow}>
          {['en', 'th', 'id', 'tl', 'ms', 'ta'].map(lang => (
            <TouchableOpacity 
              key={lang} 
              style={[styles.langPill, userLanguage === lang && styles.langPillActive]} 
              onPress={() => setUserLanguage(lang)}
            >
              <Text style={[styles.langPillText, userLanguage === lang && styles.langPillTextActive]}>
                {lang.toUpperCase()}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Terminal Header */}
        <View style={styles.header}>
          <Text style={styles.headerTitle}>{at('app_title', userLanguage)}</Text>
          <Text style={styles.headerSubtitle}>{at('app_subtitle', userLanguage)}</Text>
        </View>

        {/* Tab Segment Switcher */}
        <View style={styles.tabContainer}>
          <TouchableOpacity 
            style={[styles.tab, activeTab === 'signin' && styles.tabActiveSignin]} 
            onPress={() => {
              setActiveTab('signin');
              setPassword('');
            }}
          >
            <Text style={[styles.tabText, activeTab === 'signin' && styles.tabTextActive]}>{at('tab_signin', userLanguage)}</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={[styles.tab, activeTab === 'signup' && styles.tabActiveSignup]} 
            onPress={() => {
              setActiveTab('signup');
              setPassword('');
            }}
          >
            <Text style={[styles.tabText, activeTab === 'signup' && styles.tabTextActive]}>{at('tab_signup', userLanguage)}</Text>
          </TouchableOpacity>
        </View>

        {/* Form Container */}
        <View style={styles.formCard}>
          <Text style={styles.formTitle}>
            {activeTab === 'signin' ? at('title_signin', userLanguage) : at('title_signup', userLanguage)}
          </Text>
          <Text style={styles.formDesc}>
            {activeTab === 'signin' 
              ? at('desc_signin', userLanguage) 
              : at('desc_signup', userLanguage)}
          </Text>

          {/* Full Name (Sign Up only) */}
          {activeTab === 'signup' && (
            <View style={styles.inputGroup}>
              <Text style={styles.label}>{at('label_name', userLanguage)}</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. Nattaporn S."
                placeholderTextColor="rgba(255, 255, 255, 0.3)"
                value={name}
                onChangeText={setName}
                autoCapitalize="words"
              />
            </View>
          )}

          {/* Email Address */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>{at('label_email', userLanguage)}</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. patroller@coastal.org"
              placeholderTextColor="rgba(255, 255, 255, 0.3)"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>

          {/* Password */}
          <View style={styles.inputGroup}>
            <Text style={styles.label}>{at('label_password', userLanguage)}</Text>
            <TextInput
              style={styles.input}
              placeholder="••••••••"
              placeholderTextColor="rgba(255, 255, 255, 0.3)"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>

          {/* Role Picker (Sign Up only) */}
          {activeTab === 'signup' && (
            <View style={styles.inputGroup}>
              <Text style={styles.label}>{at('label_role', userLanguage)}</Text>
              <View style={styles.roleToggle}>
                <TouchableOpacity 
                  style={[styles.roleTab, role === 'volunteer' && styles.roleTabActiveVolunteer]}
                  onPress={() => setRole('volunteer')}
                >
                  <View style={[styles.dot, { backgroundColor: role === 'volunteer' ? '#00fbfb' : '#3a4a49' }]} />
                  <Text style={[styles.roleText, role === 'volunteer' && styles.roleTextActive]}>{at('role_volunteer', userLanguage)}</Text>
                </TouchableOpacity>
                <TouchableOpacity 
                  style={[styles.roleTab, role === 'coordinator' && styles.roleTabActiveCoordinator]}
                  onPress={() => setRole('coordinator')}
                >
                  <View style={[styles.dot, { backgroundColor: role === 'coordinator' ? '#e3b5ff' : '#3a4a49' }]} />
                  <Text style={[styles.roleText, role === 'coordinator' && styles.roleTextActive]}>{at('role_coordinator', userLanguage)}</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}

          {/* Submit Button */}
          <TouchableOpacity 
            style={[styles.submitBtn, activeTab === 'signup' && styles.submitBtnSignup]} 
            onPress={handleAuth}
            disabled={isLoading}
          >
            {isLoading ? (
              <ActivityIndicator color="#050505" size="small" />
            ) : (
              <Text style={styles.submitBtnText}>
                {activeTab === 'signin' ? at('btn_signin', userLanguage) : at('btn_signup', userLanguage)}
              </Text>
            )}
          </TouchableOpacity>
        </View>
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
    padding: 20,
    paddingTop: Platform.OS === 'ios' ? 60 : 30,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 30,
  },
  headerTitle: {
    color: '#ffffff',
    fontSize: 28,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  headerSubtitle: {
    color: '#b9cac9',
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
    marginTop: 4,
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: '#131313',
    borderRadius: 6,
    padding: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    marginBottom: 20,
  },
  tab: {
    flex: 1,
    height: 42,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 4,
  },
  tabActiveSignin: {
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(0, 251, 251, 0.2)',
  },
  tabActiveSignup: {
    backgroundColor: 'rgba(227, 181, 255, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(227, 181, 255, 0.2)',
  },
  tabText: {
    color: '#b9cac9',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  tabTextActive: {
    color: '#ffffff',
  },
  formCard: {
    backgroundColor: '#131313',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    padding: 20,
  },
  formTitle: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 1,
    marginBottom: 6,
  },
  formDesc: {
    color: '#b9cac9',
    fontSize: 10,
    lineHeight: 14,
    marginBottom: 20,
  },
  inputGroup: {
    marginBottom: 16,
  },
  label: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  input: {
    backgroundColor: '#050505',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    color: '#ffffff',
    borderRadius: 4,
    height: 40,
    paddingHorizontal: 12,
    fontSize: 13,
    fontFamily: MONOSPACE_FONT,
  },
  roleToggle: {
    flexDirection: 'row',
    backgroundColor: '#050505',
    borderRadius: 4,
    padding: 3,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  roleTab: {
    flex: 1,
    flexDirection: 'row',
    height: 36,
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
  roleText: {
    color: '#b9cac9',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  roleTextActive: {
    color: '#ffffff',
  },
  submitBtn: {
    backgroundColor: '#00fbfb',
    borderRadius: 4,
    height: 44,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
  },
  submitBtnSignup: {
    backgroundColor: '#e3b5ff',
  },
  submitBtnText: {
    color: '#050505',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  langSelectorRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginBottom: 24,
    alignSelf: 'center',
  },
  langPill: {
    backgroundColor: '#131313',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  langPillActive: {
    borderColor: '#00fbfb',
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
  },
  langPillText: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  langPillTextActive: {
    color: '#00fbfb',
  },
});
