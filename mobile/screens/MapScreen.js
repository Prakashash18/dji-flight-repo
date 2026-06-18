import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, Image, TouchableOpacity, Alert, TextInput, ScrollView, Linking, Platform, Share, SafeAreaView, StatusBar } from 'react-native';
import MapView, { Marker, UrlTile, Polygon, Polyline } from 'react-native-maps';
import { supabase } from '../App';
import { parsePinParams, buildPinImageUrl, calculatePatrollerStats, getUnlockedBadges } from '../utils/statsHelper';
import { t } from '../utils/translations';

const mockOnlineVolunteers = [
  { id: '1', name: 'Sorawit P.' },
  { id: '2', name: 'Nattaporn S.' },
  { id: '4', name: 'Kadek W.' },
  { id: '6', name: 'Siti A.' },
];

const MONOSPACE_FONT = Platform.OS === 'ios' ? 'Menlo' : 'monospace';

const localMapTranslations = {
  en: {
    btn_back_missions: "◀ MISSIONS",
    patrol_assignment_details: "Patrol Assignment Details",
    select_online_patroller: "Select an online patroller to assign to this litter signature.",
    no_volunteers_online: "No registered volunteers online.",
    btn_assign: "ASSIGN ➔",
    hub_sectors_title: "Shore Sectoring Hub",
    hub_sectors_desc: "List of drawn shoreline sectors. Assign multiple volunteers or delete obsolete zones.",
    hub_draw_btn: "📐 DRAW NEW SECTOR",
    hub_assign_btn: "👤 ASSIGN VOLUNTEERS",
    hub_delete_btn: "🗑️ DELETE",
    hub_assign_modal_title: "ASSIGN VOLUNTEERS",
    hub_assign_modal_desc: "Select multiple volunteer patrollers for this sector:",
    hub_save_assignment_btn: "✓ SAVE ASSIGNMENTS",
    hub_no_sectors: "No sectors drawn yet. Click Draw New Sector to begin.",
    hub_status_pending: "Pending",
    hub_status_in_progress: "In Progress",
    hub_status_completed: "Completed",
    hub_deleted_success: "Sector deleted successfully!",
    hub_saved_success: "Assignments saved successfully!"
  },
  th: {
    btn_back_missions: "◀ รายการภารกิจ",
    patrol_assignment_details: "รายละเอียดการมอบหมายงาน",
    select_online_patroller: "เลือกเจ้าหน้าที่ลาดตระเวนออนไลน์เพื่อมอบหมายงาน",
    no_volunteers_online: "ไม่มีอาสาสมัครออนไลน์ในขณะนี้",
    btn_assign: "มอบหมาย ➔",
    hub_sectors_title: "ศูนย์บริหารจัดการพิกัดชายฝั่ง",
    hub_sectors_desc: "รายการเขตพื้นที่ที่วาดไว้ มอบหมายงานให้อาสาสมัครหลายคนหรือลบเขตพื้นที่ที่เลิกใช้งานแล้ว",
    hub_draw_btn: "📐 วาดพื้นที่ใหม่",
    hub_assign_btn: "👤 มอบหมายอาสาสมัคร",
    hub_delete_btn: "🗑️ ลบพื้นที่",
    hub_assign_modal_title: "มอบหมายอาสาสมัคร",
    hub_assign_modal_desc: "เลือกอาสาสมัครลาดตระเวนหลายคนสำหรับพื้นที่นี้:",
    hub_save_assignment_btn: "✓ บันทึกการมอบหมาย",
    hub_no_sectors: "ยังไม่มีการวาดพื้นที่ คลิกวาดพื้นที่ใหม่เพื่อเริ่มต้น",
    hub_status_pending: "รอดำเนินการ",
    hub_status_in_progress: "กำลังดำเนินการ",
    hub_status_completed: "เสร็จสมบูรณ์",
    hub_deleted_success: "ลบพื้นที่สำเร็จแล้ว!",
    hub_saved_success: "บันทึกการมอบหมายงานสำเร็จแล้ว!"
  },
  id: {
    btn_back_missions: "◀ DAFTAR MISI",
    patrol_assignment_details: "Detail Tugas Patroli",
    select_online_patroller: "Pilih petugas patroli online untuk tugas ini.",
    no_volunteers_online: "Tidak ada sukarelawan online.",
    btn_assign: "TUGASKAN ➔",
    hub_sectors_title: "Pusat Sektor Shoreline",
    hub_sectors_desc: "Daftar sektor garis pantai yang digambar. Tugaskan beberapa sukarelawan atau hapus zona.",
    hub_draw_btn: "📐 GAMBAR SEKTOR BARU",
    hub_assign_btn: "👤 TUGASKAN RELAWAN",
    hub_delete_btn: "🗑️ HAPUS",
    hub_assign_modal_title: "TUGASKAN RELAWAN",
    hub_assign_modal_desc: "Pilih beberapa petugas patroli sukarela untuk sektor ini:",
    hub_save_assignment_btn: "✓ SIMPAN TUGASAN",
    hub_no_sectors: "Belum ada sektor yang digambar. Klik Gambar Sektor Baru untuk memulai.",
    hub_status_pending: "Tertunda",
    hub_status_in_progress: "Dalam Proses",
    hub_status_completed: "Selesai",
    hub_deleted_success: "Sektor berhasil dihapus!",
    hub_saved_success: "Tugasan berhasil disimpan!"
  },
  tl: {
    btn_back_missions: "◀ MGA MISYON",
    patrol_assignment_details: "Mga Detalye ng Pagtatalaga",
    select_online_patroller: "Pumili ng online patroller para italaga sa basurang ito.",
    no_volunteers_online: "Walang online na boluntaryo.",
    btn_assign: "ITALAGA ➔",
    hub_sectors_title: "Shore Sectoring Hub",
    hub_sectors_desc: "Listahan ng mga iginuhit na shoreline sector. Magtalaga ng boluntaryo o magbura ng zone.",
    hub_draw_btn: "📐 GUMUHIT NG BAGONG SEKTOR",
    hub_assign_btn: "👤 ITALAGA ANG MGA BOLUNTARYO",
    hub_delete_btn: "🗑️ BURAHIN",
    hub_assign_modal_title: "ITALAGA ANG MGA BOLUNTARYO",
    hub_assign_modal_desc: "Pumili ng mga boluntaryong patroller para sa sektor na ito:",
    hub_save_assignment_btn: "✓ I-SAVE ANG TALAGA",
    hub_no_sectors: "Wala pang iginuhit na sektor. I-click ang Gumuhit ng Bagong Sektor.",
    hub_status_pending: "Nakabinbin",
    hub_status_in_progress: "Kasalukuyang Ginagawa",
    hub_status_completed: "Tapos na",
    hub_deleted_success: "Matagumpay na nabura ang sektor!",
    hub_saved_success: "Matagumpay na nai-save ang mga talaga!"
  },
  ms: {
    btn_back_missions: "◀ REKOD MISI",
    patrol_assignment_details: "Butiran Tugasan Rondaan",
    select_online_patroller: "Pilih petugas rondaan online untuk tugasan ini.",
    no_volunteers_online: "Tiada sukarelawan online.",
    btn_assign: "TUGASKAN ➔",
    hub_sectors_title: "Pusat Sektor Pantai",
    hub_sectors_desc: "Senarai sektor garis pantai. Tugaskan sukarelawan atau padam zon.",
    hub_draw_btn: "📐 GAMBAR SEKTOR BARU",
    hub_assign_btn: "👤 TUGASKAN SUKARELAWAN",
    hub_delete_btn: "🗑️ PADAM",
    hub_assign_modal_title: "TUGASKAN SUKARELAWAN",
    hub_assign_modal_desc: "Pilih sukarelawan rondaan untuk sektor ini:",
    hub_save_assignment_btn: "✓ SIMPAN TUGASAN",
    hub_no_sectors: "Tiada sektor digambar lagi. Klik Gambar Sektor Baru.",
    hub_status_pending: "Belum Mula",
    hub_status_in_progress: "Sedang Berjalan",
    hub_status_completed: "Selesai",
    hub_deleted_success: "Sektor berjaya dipadam!",
    hub_saved_success: "Tugasan berjaya disimpan!"
  },
  ta: {
    btn_back_missions: "◀ பணிகள்",
    patrol_assignment_details: "ரோந்து பணி ஒதுக்கீடு விவரங்கள்",
    select_online_patroller: "குப்பை கண்டறிதல் புள்ளிக்கு ரோந்து அதிகாரியை நியமிக்கவும்.",
    no_volunteers_online: "தொண்டர்கள் யாரும் ஆன்லைனில் இல்லை.",
    btn_assign: "ஒதுக்கு ➔",
    hub_sectors_title: "ரோந்து பகுதி மேலாண்மை",
    hub_sectors_desc: "வரைபடத்தில் உள்ள ரோந்து பகுதிகள். தொண்டர்களை நியமிக்கலாம் அல்லது நீக்கலாம்.",
    hub_draw_btn: "📐 புதிய பகுதி வரை",
    hub_assign_btn: "👤 தொண்டர்களை நியமி",
    hub_delete_btn: "🗑️ நீக்கு",
    hub_assign_modal_title: "தொண்டர்களை நியமி",
    hub_assign_modal_desc: "இப்பகுதிக்கு ஒன்றுக்கும் மேற்பட்ட தொண்டர்களைத் தேர்ந்தெடுக்கவும்:",
    hub_save_assignment_btn: "✓ ஒதுக்கீட்டைச் சேமி",
    hub_no_sectors: "ரோந்து பகுதிகள் ஏதுமில்லை. புதிய பகுதி வரை என்பதைத் தேர்ந்தெடுக்கவும்.",
    hub_status_pending: "நிலுவையில் உள்ளது",
    hub_status_in_progress: "செயல்பாட்டில் உள்ளது",
    hub_status_completed: "முடிந்தது",
    hub_deleted_success: "ரோந்து பகுதி வெற்றிகரமாக நீக்கப்பட்டது!",
    hub_saved_success: "ஒதுக்கீடு வெற்றிகரமாகச் சேமிக்கப்பட்டது!"
  }
};

const lt = (key, lang) => {
  const dict = localMapTranslations[lang] || localMapTranslations.en;
  return dict[key] || localMapTranslations.en[key] || key;
};

const STATUS_ORDER = {
  'detected': 1,
  'cleaning': 2,
  'cleaned': 3
};

const isPinInZone = (pin, zone) => {
  if (!pin || !zone || !zone.boundary_geojson || zone.boundary_geojson.type !== 'Polygon') {
    return false;
  }
  const coordinates = zone.boundary_geojson.coordinates;
  if (!coordinates || coordinates.length === 0) return false;
  
  const x = pin.longitude;
  const y = pin.latitude;
  const polygon = coordinates[0]; // outer ring
  
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0];
    const yi = polygon[i][1];
    const xj = polygon[j][0];
    const yj = polygon[j][1];
    
    const intersect = ((yi > y) !== (yj > y))
        && (x < (xj - xi) * (y - yi) / (yj - yi + 0.000000001) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
};

export default function MapScreen({ 
  pins, 
  userRole, 
  userLanguage, 
  missions = [], 
  selectedMissionId = null, 
  setSelectedMissionId, 
  profiles = [],
  activeVolunteerName,
  setActiveVolunteerName,
  setHideTabBar,
  cleanupZones = []
}) {
  const [selectedPin, setSelectedPin] = useState(null);
  const [screenMode, setScreenMode] = useState('MISSION_LIST');
  
  // Track local step for volunteer wizard: 1 (Accept) | 2 (Navigate) | 3 (Resolve) | 4 (Done)
  const [localStep, setLocalStep] = useState(1);
  const [arrivedPins, setArrivedPins] = useState({}); // Keep track of pins where volunteer has arrived
  
  // Volunteer cleaning checklist state
  const [checklistBags, setChecklistBags] = useState(1);

  // Sector assignment multi-volunteer state
  const [assigningZone, setAssigningZone] = useState(null);
  const [selectedVolunteersList, setSelectedVolunteersList] = useState([]);
  const [showMultiAssignModal, setShowMultiAssignModal] = useState(false);

  // Sync tab bar visibility based on screenMode
  useEffect(() => {
    if (setHideTabBar) {
      setHideTabBar(screenMode === 'TASK_RUN');
    }
    return () => {
      if (setHideTabBar) {
        setHideTabBar(false);
      }
    };
  }, [screenMode, setHideTabBar]);

  // Sync selectedMissionId changes to screenMode and clean up state when leaving a mission
  useEffect(() => {
    if (selectedMissionId !== null) {
      setScreenMode('TACTICAL_MAP');
    } else {
      setScreenMode('MISSION_LIST');
      setSelectedPin(null);
      setIsDrawingZone(false);
      setDrawingCoordinates([]);
    }
  }, [selectedMissionId]);

  const notifiedZonesRef = useRef(new Set());

  // Real-time local alert notification when active volunteer is assigned to a sector/cleanup zone
  useEffect(() => {
    if (!cleanupZones || cleanupZones.length === 0 || userRole === 'coordinator') return;

    cleanupZones.forEach(zone => {
      const assignedVols = zone.boundary_geojson?.properties?.assigned_volunteers || [];
      const isAssignedToMe = assignedVols.some(v => v.name === activeVolunteerName);
      
      if (isAssignedToMe && zone.status === 'in_progress') {
        if (!notifiedZonesRef.current.has(zone.id)) {
          notifiedZonesRef.current.add(zone.id);
          
          Alert.alert(
            "📋 " + (userLanguage === 'th' ? "ได้รับมอบหมายพื้นที่ใหม่" : "New Sector Assigned"),
            (userLanguage === 'th' 
              ? `คุณได้รับมอบหมายพื้นที่เก็บขยะ: "${zone.name}" พิกัดทั้งหมดในพื้นที่นี้ได้รับการเปิดใช้งานแล้ว!`
              : `You have been assigned to Shoreline Sector: "${zone.name}". All target locations inside this sector are now active for cleaning!`),
            [{ text: "OK" }]
          );
        }
      }
    });
  }, [cleanupZones, activeVolunteerName, userRole, userLanguage]);
  
  // Coordinator task assignment state
  const [selectedVolunteer, setSelectedVolunteer] = useState(null); // Selected Volunteer ID
  const [showAssignModal, setShowAssignModal] = useState(false);
  const [showTelemetry, setShowTelemetry] = useState(false);

  // Coordinator shoreline zone state
  const [isDrawingZone, setIsDrawingZone] = useState(false);
  const [drawingCoordinates, setDrawingCoordinates] = useState([]);
  const [showZoneNameModal, setShowZoneNameModal] = useState(false);
  const [newZoneName, setNewZoneName] = useState('');

  const mapRef = useRef(null);
  const hasCentered = useRef(false);

  const onlineVolunteers = profiles && profiles.filter(p => p.role === 'volunteer').length > 0
    ? profiles.filter(p => p.role === 'volunteer')
    : mockOnlineVolunteers;

  const filteredPins = pins.filter(p => {
    if (!p) return false;
    if (selectedMissionId !== null) {
      return p.mission_id === selectedMissionId;
    }
    return true;
  });

  // Keep selectedPin in sync with database updates from pins prop
  useEffect(() => {
    if (selectedPin) {
      const updated = pins.find(p => p.id === selectedPin.id);
      if (updated) {
        const currentOrder = STATUS_ORDER[selectedPin.status] || 0;
        const updatedOrder = STATUS_ORDER[updated.status] || 0;
        // Only update if it doesn't downgrade the status to prevent race conditions during updates
        if (updatedOrder >= currentOrder) {
          setSelectedPin(updated);
        }
      }
    }
  }, [pins]);

  // Set the wizard step based on the pin's current state
  useEffect(() => {
    if (selectedPin) {
      const parsed = parsePinParams(selectedPin);
      if (selectedPin.status === 'detected') {
        setLocalStep(1);
      } else if (selectedPin.status === 'cleaning') {
        if (arrivedPins[selectedPin.id]) {
          setLocalStep(3);
        } else {
          setLocalStep(2);
        }
      } else if (selectedPin.status === 'cleaned') {
        setLocalStep(4);
        if (parsed.bags_used !== null) setChecklistBags(parsed.bags_used);
      }
    }
  }, [selectedPin, arrivedPins]);

  const focusMapOnPins = (animate = true) => {
    if (filteredPins && filteredPins.length > 0 && mapRef.current) {
      let targetPins = filteredPins.filter(p => p && p.status !== 'cleaned');
      if (targetPins.length === 0) {
        targetPins = filteredPins;
      }
      const validPins = targetPins.filter(p => p && typeof p.latitude === 'number' && typeof p.longitude === 'number');
      if (validPins.length > 0) {
        const lats = validPins.map(p => p.latitude);
        const lons = validPins.map(p => p.longitude);
        const minLat = Math.min(...lats);
        const maxLat = Math.max(...lats);
        const minLon = Math.min(...lons);
        const maxLon = Math.max(...lons);
        
        const centerLat = (minLat + maxLat) / 2;
        const centerLon = (minLon + maxLon) / 2;
        
        const latDelta = Math.max(0.003, (maxLat - minLat) * 1.3);
        const lonDelta = Math.max(0.003, (maxLon - minLon) * 1.3);
        
        mapRef.current.animateToRegion({
          latitude: centerLat,
          longitude: centerLon,
          latitudeDelta: latDelta,
          longitudeDelta: lonDelta,
        }, animate ? 1000 : 0);
      }
    }
  };

  useEffect(() => {
    if (pins && pins.length > 0 && !hasCentered.current) {
      hasCentered.current = true;
      const timer = setTimeout(() => {
        focusMapOnPins(false);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [pins]);

  useEffect(() => {
    if (filteredPins && filteredPins.length > 0) {
      focusMapOnPins(true);
    }
  }, [selectedMissionId]);

  const getStatusColor = (status) => {
    switch (status) {
      case 'cleaned': return '#10B981';  // Emerald Green
      case 'cleaning': return '#F59E0B'; // Amber Orange
      default: return '#EF4444';         // Red
    }
  };

  const getConfidenceBadgeColor = (conf) => {
    if (conf >= 0.8) return '#10B981';
    if (conf >= 0.6) return '#F59E0B';
    return '#EF4444';
  };

  const handlePinPress = (pin) => {
    setSelectedPin(pin);
    setSelectedVolunteer(null);
  };

  const handleStartCleaning = async () => {
    if (!selectedPin) return;
    const newImageUrl = buildPinImageUrl(selectedPin.image_url, { assigned_to: activeVolunteerName });
    
    // Optimistically update local state to prevent lag or status reset by sync effects
    const originalPin = selectedPin;
    setSelectedPin(prev => ({
      ...prev,
      status: 'cleaning',
      image_url: newImageUrl
    }));
    setLocalStep(2);

    const { error } = await supabase
      .from('litter_pins')
      .update({
        status: 'cleaning',
        image_url: newImageUrl
      })
      .eq('id', selectedPin.id);

    if (error) {
      Alert.alert("Error", "Failed to update mission: " + error.message);
      setSelectedPin(originalPin);
      setLocalStep(1);
    }
  };

  const handleArrived = () => {
    if (!selectedPin) return;
    setArrivedPins(prev => ({ ...prev, [selectedPin.id]: true }));
    setLocalStep(3);
  };

  const handleOpenNavigation = () => {
    if (!selectedPin) return;
    const lat = selectedPin.latitude;
    const lon = selectedPin.longitude;
    const url = `maps:0,0?q=${lat},${lon}`;
    Linking.openURL(url).catch(() => {
      Linking.openURL(`https://www.google.com/maps/search/?api=1&query=${lat},${lon}`);
    });
  };

  const handleReportMistake = () => {
    if (!selectedPin) return;
    Alert.alert(
      "Report False Detection",
      "Are you sure this target is a mistake (not actual beach litter)?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Report Mistake",
          style: "destructive",
          onPress: async () => {
            const parsed = parsePinParams(selectedPin);
            const newImageUrl = buildPinImageUrl(selectedPin.image_url, {
              assigned_to: parsed.assigned_to || activeVolunteerName,
              is_mistake: true
            });

            // Optimistically update local state
            const originalPin = selectedPin;
            setSelectedPin(prev => ({
              ...prev,
              status: 'cleaned',
              image_url: newImageUrl,
              cleaned_at: new Date().toISOString()
            }));
            setLocalStep(4);

            const { error } = await supabase
              .from('litter_pins')
              .update({
                status: 'cleaned',
                image_url: newImageUrl,
                cleaned_at: new Date().toISOString()
              })
              .eq('id', selectedPin.id);

            if (error) {
              Alert.alert("Error", "Failed to report mistake: " + error.message);
              setSelectedPin(originalPin);
              setLocalStep(originalPin.status === 'cleaning' ? (arrivedPins[originalPin.id] ? 3 : 2) : 1);
            }
          }
        }
      ]
    );
  };

  const handleCompleteChecklist = async () => {
    if (!selectedPin) return;
    
    const parsed = parsePinParams(selectedPin);
    const newImageUrl = buildPinImageUrl(selectedPin.image_url, {
      assigned_to: parsed.assigned_to || activeVolunteerName,
      is_mistake: false
    });

    // Optimistically update local state
    const originalPin = selectedPin;
    setSelectedPin(prev => ({
      ...prev,
      status: 'cleaned',
      image_url: newImageUrl,
      cleaned_at: new Date().toISOString()
    }));
    setLocalStep(4);

    const { error } = await supabase
      .from('litter_pins')
      .update({
        status: 'cleaned',
        image_url: newImageUrl,
        cleaned_at: new Date().toISOString()
      })
      .eq('id', selectedPin.id);

    if (error) {
      Alert.alert("Error", "Failed to resolve pin: " + error.message);
      setSelectedPin(originalPin);
      setLocalStep(3);
    }
  };

  const handleAssignTask = async (volunteerName) => {
    if (!selectedPin) return;
    const newImageUrl = buildPinImageUrl(selectedPin.image_url, { assigned_to: volunteerName });

    const { error } = await supabase
      .from('litter_pins')
      .update({
        status: 'cleaning',
        image_url: newImageUrl
      })
      .eq('id', selectedPin.id);

    if (error) {
      Alert.alert("Error", "Failed to assign task: " + error.message);
    } else {
      Alert.alert("Task Dispatched", `Mission assigned to ${volunteerName}!`);
      setSelectedVolunteer(null);
    }
  };



  const handleReassign = async () => {
    if (!selectedPin) return;
    const { error } = await supabase
      .from('litter_pins')
      .update({
        status: 'detected',
        image_url: selectedPin.image_url ? selectedPin.image_url.split('#')[0] : null
      })
      .eq('id', selectedPin.id);

    if (error) {
      Alert.alert("Error", "Failed to reset task: " + error.message);
    } else {
      setSelectedVolunteer(null);
    }
  };

  const handleAssignZone = () => {
    setIsDrawingZone(true);
    setDrawingCoordinates([]);
  };

  const handleCancelDrawing = () => {
    setIsDrawingZone(false);
    setDrawingCoordinates([]);
    setScreenMode('SECTORS_HUB'); // Go back to Sectors Hub
  };

  const handleUndoLastPoint = () => {
    setDrawingCoordinates(prev => prev.slice(0, -1));
  };

  const handleSaveZone = () => {
    if (drawingCoordinates.length < 3) {
      Alert.alert(
        t('prompt_sector_name', userLanguage),
        t('sector_draw_min_points', userLanguage)
      );
      return;
    }
    setNewZoneName('');
    setShowZoneNameModal(true);
  };

  const submitNewZone = async () => {
    if (!newZoneName || newZoneName.trim() === '') {
      Alert.alert("Error", "Zone name cannot be empty.");
      return;
    }
    
    try {
      // Close the polygon by repeating the first coordinate
      const closedCoords = [...drawingCoordinates, drawingCoordinates[0]];
      
      // Convert to GeoJSON coordinates format: [longitude, latitude]
      const geojsonCoords = closedCoords.map(coord => [coord.longitude, coord.latitude]);
      
      const boundaryGeojson = {
        type: "Polygon",
        coordinates: [geojsonCoords]
      };

      // Get current session user id if available
      const { data: { session } } = await supabase.auth.getSession();
      const createdBy = session?.user?.id || null;

      const { error } = await supabase
        .from('cleanup_zones')
        .insert({
          name: newZoneName.trim(),
          boundary_geojson: boundaryGeojson,
          status: 'pending',
          created_by: createdBy
        });

      if (error) {
        Alert.alert("Error", "Failed to save zone: " + error.message);
      } else {
        Alert.alert(
          t('sector_saved_title', userLanguage),
          t('sector_saved_desc', userLanguage)
        );
        setShowZoneNameModal(false);
        setIsDrawingZone(false);
        setDrawingCoordinates([]);
        setScreenMode('SECTORS_HUB'); // Return to Sectors Hub
      }
    } catch (err) {
      Alert.alert("Error", err.message);
    }
  };

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

  // Render step-by-step progress wizard for volunteers
  const renderStepIndicator = () => {
    const steps = [
      userLanguage === 'th' ? 'นำทาง' : (userLanguage === 'id' ? 'GPS' : (userLanguage === 'tl' ? 'GPS' : (userLanguage === 'ms' ? 'GPS' : (userLanguage === 'ta' ? 'வழிசெலுத்துதல்' : 'Navigate')))),
      userLanguage === 'th' ? 'ดำเนินการ' : (userLanguage === 'id' ? 'Eksekusi' : (userLanguage === 'tl' ? 'Resolusyon' : (userLanguage === 'ms' ? 'Eksekusi' : (userLanguage === 'ta' ? 'தீர்வு' : 'Resolve')))),
      userLanguage === 'th' ? 'เสร็จสิ้น' : (userLanguage === 'id' ? 'Selesai' : (userLanguage === 'tl' ? 'Tapos na' : (userLanguage === 'ms' ? 'Selesai' : (userLanguage === 'ta' ? 'முடிந்தது' : 'Done'))))
    ];
    // Offset localStep to fit 3-step visualization
    const visualStep = localStep === 4 ? 3 : (localStep === 3 ? 2 : 1);
    
    return (
      <View style={styles.stepContainer}>
        {steps.map((step, idx) => {
          const stepNum = idx + 1;
          const isActive = visualStep === stepNum;
          const isCompleted = visualStep > stepNum;
          return (
            <React.Fragment key={step}>
              <View style={styles.stepWrapper}>
                <View style={[
                  styles.stepDot,
                  isActive && styles.stepDotActive,
                  isCompleted && styles.stepDotCompleted
                ]}>
                  {isCompleted ? (
                    <Text style={styles.stepDotText}>✓</Text>
                  ) : (
                    <Text style={[styles.stepDotText, isActive && styles.stepDotTextActive]}>{stepNum}</Text>
                  )}
                </View>
                <Text style={[
                  styles.stepLabel,
                  isActive && styles.stepLabelActive,
                  isCompleted && styles.stepLabelCompleted
                ]}>
                  {step}
                </Text>
              </View>
              {idx < steps.length - 1 && (
                <View style={[
                  styles.stepLine,
                  visualStep > stepNum && styles.stepLineCompleted
                ]} />
              )}
            </React.Fragment>
          );
        })}
      </View>
    );
  };

  const getTranslatedStatus = (status) => {
    switch (status) {
      case 'cleaned': return t('status_cleaned', userLanguage);
      case 'cleaning': return t('status_active', userLanguage);
      default: return t('status_new', userLanguage);
    }
  };

  const handleOpenAssignZoneModal = (zone) => {
    setAssigningZone(zone);
    const existingProps = zone.boundary_geojson?.properties || {};
    const existingVols = existingProps.assigned_volunteers || [];
    setSelectedVolunteersList(existingVols);
    setShowMultiAssignModal(true);
  };

  const handleSaveMultiAssignment = async () => {
    if (!assigningZone) return;

    try {
      const updatedGeojson = {
        ...assigningZone.boundary_geojson,
        properties: {
          ...(assigningZone.boundary_geojson?.properties || {}),
          assigned_volunteers: selectedVolunteersList
        }
      };

      // Set assigned_to to first selected volunteer's UUID or null for backwards compatibility
      const firstVolId = selectedVolunteersList.length > 0 ? selectedVolunteersList[0].id : null;
      const isRealProfile = profiles && profiles.some(p => p.id === firstVolId);
      const dbAssignedTo = isRealProfile ? firstVolId : null;

      const { error } = await supabase
        .from('cleanup_zones')
        .update({
          boundary_geojson: updatedGeojson,
          assigned_to: dbAssignedTo,
          status: selectedVolunteersList.length > 0 ? 'in_progress' : 'pending'
        })
        .eq('id', assigningZone.id);

      if (error) {
        Alert.alert("Error", "Failed to update assignments: " + error.message);
      } else {
        // Automatically activate pins within this zone if volunteers are assigned
        if (selectedVolunteersList.length > 0) {
          const pinsInZone = pins.filter(p => p && p.status === 'detected' && isPinInZone(p, assigningZone));
          if (pinsInZone.length > 0) {
            const primaryVolName = selectedVolunteersList[0].name;
            await Promise.all(pinsInZone.map(async (p) => {
              const newImageUrl = buildPinImageUrl(p.image_url, { assigned_to: primaryVolName });
              await supabase
                .from('litter_pins')
                .update({
                  status: 'cleaning',
                  image_url: newImageUrl
                })
                .eq('id', p.id);
            }));
          }
        }

        Alert.alert("Success", lt('hub_saved_success', userLanguage));
        setShowMultiAssignModal(false);
        setAssigningZone(null);
      }
    } catch (err) {
      Alert.alert("Error", err.message);
    }
  };

  const handleDeleteZone = (zoneId) => {
    Alert.alert(
      userLanguage === 'ta' ? "ஒதுக்கீட்டை நீக்கு" : (userLanguage === 'th' ? "ลบพื้นที่" : "Delete Sector"),
      userLanguage === 'ta' ? "இந்த ரோந்து பகுதியை நீக்கவா?" : (userLanguage === 'th' ? "คุณแน่ใจหรือไม่ว่าต้องการลบพื้นที่นี้?" : "Are you sure you want to delete this sector? This cannot be undone."),
      [
        { text: userLanguage === 'th' ? "ยกเลิก" : "Cancel", style: "cancel" },
        {
          text: userLanguage === 'th' ? "ลบ" : "Delete",
          style: "destructive",
          onPress: async () => {
            const { error } = await supabase
              .from('cleanup_zones')
              .delete()
              .eq('id', zoneId);

            if (error) {
              Alert.alert("Error", "Failed to delete sector: " + error.message);
            } else {
              Alert.alert("Success", lt('hub_deleted_success', userLanguage));
            }
          }
        }
      ]
    );
  };

  const renderSectorsHubMode = () => {
    return (
      <View style={styles.sectorsHubContainer}>
        {/* Header Bar */}
        <View style={styles.mapHeaderBar}>
          <TouchableOpacity 
            style={styles.backButton} 
            onPress={() => {
              setScreenMode('TACTICAL_MAP');
            }}
          >
            <Text style={styles.backButtonText}>◀ {t('btn_back_map', userLanguage)}</Text>
          </TouchableOpacity>
          <Text style={styles.mapHeaderTitle} numberOfLines={1}>
            {lt('hub_sectors_title', userLanguage).toUpperCase()}
          </Text>
          <View style={{ width: 60 }} />
        </View>

        <View style={styles.hubHeaderBlock}>
          <Text style={styles.hubDescText}>{lt('hub_sectors_desc', userLanguage)}</Text>
          <TouchableOpacity 
            style={styles.hubDrawBtn}
            onPress={() => {
              setScreenMode('TACTICAL_MAP');
              setIsDrawingZone(true);
              setDrawingCoordinates([]);
            }}
          >
            <Text style={styles.hubDrawBtnText}>{lt('hub_draw_btn', userLanguage)}</Text>
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.sectorsListScroll} showsVerticalScrollIndicator={false}>
          {cleanupZones.length === 0 ? (
            <View style={styles.hubEmptyBox}>
              <Text style={styles.hubEmptyText}>{lt('hub_no_sectors', userLanguage)}</Text>
            </View>
          ) : (
            cleanupZones.map(zone => {
              const assignedVols = zone.boundary_geojson?.properties?.assigned_volunteers || [];
              
              return (
                <View key={zone.id} style={styles.sectorCard}>
                  <View style={styles.sectorCardHeader}>
                    <Text style={styles.sectorCardName}>{zone.name}</Text>
                    <View style={[styles.sectorStatusBadge, zone.status === 'completed' ? styles.statusCompleted : styles.statusPending]}>
                      <Text style={styles.sectorStatusText}>
                        {zone.status === 'completed' 
                          ? lt('hub_status_completed', userLanguage).toUpperCase() 
                          : (zone.status === 'in_progress' 
                              ? lt('hub_status_in_progress', userLanguage).toUpperCase() 
                              : lt('hub_status_pending', userLanguage).toUpperCase())}
                      </Text>
                    </View>
                  </View>

                  <View style={styles.assignedSection}>
                    <Text style={styles.assignedLabel}>ASSIGNED PATROLLERS:</Text>
                    {assignedVols.length === 0 ? (
                      <Text style={styles.assignedEmptyText}>⚠️ No volunteers assigned</Text>
                    ) : (
                      <View style={styles.volPillContainer}>
                        {assignedVols.map((v, i) => (
                          <View key={v.id || i} style={styles.volPill}>
                            <Text style={styles.volPillText}>👤 {v.name}</Text>
                          </View>
                        ))}
                      </View>
                    )}
                  </View>

                  <View style={styles.sectorCardActions}>
                    <TouchableOpacity 
                      style={styles.sectorAssignBtn}
                      onPress={() => handleOpenAssignZoneModal(zone)}
                    >
                      <Text style={styles.sectorActionBtnText}>{lt('hub_assign_btn', userLanguage)}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity 
                      style={styles.sectorDeleteBtn}
                      onPress={() => handleDeleteZone(zone.id)}
                    >
                      <Text style={styles.sectorActionBtnText}>{lt('hub_delete_btn', userLanguage)}</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })
          )}
        </ScrollView>

        {/* Multi-volunteer Assignment Modal */}
        {showMultiAssignModal && assigningZone && (
          <View style={styles.assignOverlay}>
            <View style={styles.assignModal}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalTitle}>{lt('hub_assign_modal_title', userLanguage)}</Text>
                <TouchableOpacity 
                  style={styles.modalCloseBtn} 
                  onPress={() => {
                    setShowMultiAssignModal(false);
                    setAssigningZone(null);
                  }}
                >
                  <Text style={styles.modalCloseText}>✕</Text>
                </TouchableOpacity>
              </View>
              <Text style={styles.modalSubtitle}>{lt('hub_assign_modal_desc', userLanguage)}</Text>
              
              {onlineVolunteers.length === 0 ? (
                <View style={{ paddingVertical: 30, alignItems: 'center' }}>
                  <Text style={styles.emptyText}>{lt('no_volunteers_online', userLanguage)}</Text>
                </View>
              ) : (
                <ScrollView style={styles.modalScroll} showsVerticalScrollIndicator={false}>
                  {onlineVolunteers.map(vol => {
                    const isSelected = selectedVolunteersList.some(v => v.id === vol.id || v.name === vol.name);
                    return (
                      <TouchableOpacity
                        key={vol.id}
                        style={[styles.modalVolCard, isSelected && styles.modalVolCardSelected]}
                        onPress={() => {
                          setSelectedVolunteersList(prev => {
                            const exists = prev.some(v => v.id === vol.id || v.name === vol.name);
                            if (exists) {
                              return prev.filter(v => v.id !== vol.id && v.name !== vol.name);
                            } else {
                              return [...prev, { id: vol.id, name: vol.name }];
                            }
                          });
                        }}
                      >
                        <View style={styles.modalVolAvatar}>
                          <Text style={styles.modalVolAvatarText}>
                            {vol.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()}
                          </Text>
                        </View>
                        <View style={{ flex: 1 }}>
                          <Text style={styles.modalVolName}>{vol.name}</Text>
                          <Text style={styles.modalVolStatus}>
                            {isSelected ? '🟢 ' + t('role_volunteer', userLanguage) : '⚪ ' + t('role_volunteer', userLanguage)}
                          </Text>
                        </View>
                        <View style={[styles.checkbox, isSelected && styles.checkboxChecked]}>
                          {isSelected && <Text style={styles.checkboxTick}>✓</Text>}
                        </View>
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              )}

              <TouchableOpacity 
                style={[styles.modalBtn, styles.modalBtnConfirm, { marginTop: 15 }]} 
                onPress={handleSaveMultiAssignment}
              >
                <Text style={styles.modalBtnConfirmText}>{lt('hub_save_assignment_btn', userLanguage)}</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </View>
    );
  };

  const renderMissionListMode = () => {
    return (
      <View style={styles.missionListContainer}>
        <Text style={styles.mainHeader}>{t('missions_header', userLanguage)}</Text>
        <Text style={styles.mainSubheader}>{t('missions_subheader', userLanguage)}</Text>
        
        <ScrollView style={styles.missionScroll} showsVerticalScrollIndicator={false}>
          {missions.length === 0 ? (
            <View style={styles.emptyFeedBox}>
              <Text style={styles.emptyFeedText}>{t('no_missions', userLanguage)}</Text>
            </View>
          ) : (
            missions.map(m => {
              const missionPins = pins.filter(p => p && p.mission_id === m.id);
              const total = missionPins.length;
              const cleaned = missionPins.filter(p => p.status === 'cleaned').length;
              const isFinished = total > 0 && cleaned === total;
              
              return (
                <View key={m.id} style={[styles.missionCard, isFinished && styles.missionCardCompleted]}>
                  <View style={styles.missionCardHeader}>
                    <View style={styles.titleCol}>
                      <Text style={styles.missionCardTitle} numberOfLines={1}>{m.title}</Text>
                      <Text style={styles.missionCardDate}>{new Date(m.mission_date).toLocaleDateString()}</Text>
                    </View>
                    <View style={[styles.tagBadge, isFinished ? styles.tagCompleted : styles.tagActive]}>
                      <Text style={styles.tagBadgeText}>
                        {isFinished ? t('completed_run', userLanguage).toUpperCase() : t('active_run', userLanguage).toUpperCase()}
                      </Text>
                    </View>
                  </View>
                  
                  {m.description ? <Text style={styles.missionCardDesc}>{m.description}</Text> : null}
                  
                  <View style={styles.missionProgressRow}>
                    <View style={styles.progressLabelCol}>
                      <Text style={styles.progressLabelText}>{t('resolved_marks', userLanguage)}</Text>
                      <Text style={styles.progressValText}>{cleaned} / {total}</Text>
                    </View>
                    <View style={styles.progressTrack}>
                      <View style={[styles.progressIndicatorFill, { width: total > 0 ? `${(cleaned / total) * 100}%` : '0%' }]} />
                    </View>
                  </View>

                  <View style={styles.missionCardActions}>
                    <TouchableOpacity 
                      style={[styles.launchBtn, isFinished && styles.launchBtnCompleted]}
                      onPress={() => setSelectedMissionId(m.id)}
                    >
                      <Text style={styles.launchBtnText}>
                        {isFinished ? t('view_results', userLanguage) : t('enter_workspace', userLanguage)}
                      </Text>
                    </TouchableOpacity>
                    <TouchableOpacity 
                      style={styles.shareBtnPill}
                      onPress={() => handleShareMission(m)}
                    >
                      <Text style={styles.shareBtnPillText}>{t('share_invite', userLanguage)}</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })
          )}
        </ScrollView>
      </View>
    );
  };

  const renderTaskRunMode = () => {
    const parsed = parsePinParams(selectedPin);
    const isMistake = parsed.is_mistake;
    const visualStep = localStep === 4 ? 3 : (localStep === 3 ? 2 : 1);
    
    return (
      <SafeAreaView style={styles.taskTerminalContainer}>
        <StatusBar barStyle="light-content" />
        
        {/* Terminal Header */}
        <View style={styles.terminalHeader}>
          <TouchableOpacity 
            style={styles.backButtonTerminal} 
            onPress={() => {
              setScreenMode('TACTICAL_MAP');
            }}
          >
            <Text style={styles.backButtonTextTerminal}>{t('exit_patrol', userLanguage)}</Text>
          </TouchableOpacity>
          <Text style={styles.terminalTitleText}>{t('task_control', userLanguage)}</Text>
        </View>

        <ScrollView style={styles.terminalScroll} contentContainerStyle={{ paddingBottom: 100 }} showsVerticalScrollIndicator={false}>
          {/* Stepper Wizard for Volunteer role */}
          {renderStepIndicator()}

          {/* Evidence Card */}
          <View style={styles.terminalImageCard}>
            <View style={styles.terminalImageHeader}>
              <Text style={styles.terminalPanelLabel}>{t('yolo_crop', userLanguage)}</Text>
              <Text style={styles.terminalPanelVal}>CONF: {((selectedPin.confidence || 0) * 100).toFixed(0)}%</Text>
            </View>
            <View style={styles.terminalImageContainer}>
              <Image 
                source={parsed.clean_image_url ? { uri: parsed.clean_image_url } : null} 
                style={styles.terminalEvidenceImage}
              />
              <View style={styles.scanLine} />
              <View style={styles.targetCornerTL} />
              <View style={styles.targetCornerTR} />
              <View style={styles.targetCornerBL} />
              <View style={styles.targetCornerBR} />
            </View>
          </View>

          {/* Telemetry Panel */}
          <View style={styles.terminalTelemetryCard}>
            <Text style={styles.terminalPanelLabel}>{t('coordinate_telemetry', userLanguage)}</Text>
            <View style={styles.telemetryRow}>
              <Text style={styles.telemetryKey}>LATITUDE:</Text>
              <Text style={styles.telemetryValueText}>{selectedPin.latitude.toFixed(6)}</Text>
            </View>
            <View style={styles.telemetryRow}>
              <Text style={styles.telemetryKey}>LONGITUDE:</Text>
              <Text style={styles.telemetryValueText}>{selectedPin.longitude.toFixed(6)}</Text>
            </View>
            <View style={styles.telemetryRow}>
              <Text style={styles.telemetryKey}>{t('assignee', userLanguage).toUpperCase()}:</Text>
              <Text style={styles.telemetryValueText}>{parsed.assigned_to || activeVolunteerName}</Text>
            </View>
            <View style={styles.telemetryRow}>
              <Text style={styles.telemetryKey}>{t('status', userLanguage).toUpperCase()}:</Text>
              <Text style={[styles.telemetryValueText, { color: getStatusColor(selectedPin.status) }]}>
                {getTranslatedStatus(selectedPin.status).toUpperCase()}
              </Text>
            </View>
          </View>

          {/* Stepper Steps / Terminal Actions */}
          {selectedPin.status === 'cleaned' ? (
            <View style={[styles.successContainer, isMistake && styles.successContainerMistake]}>
              <View style={[styles.successIconCircle, isMistake && styles.successIconCircleMistake]}>
                <Text style={[styles.successIconText, isMistake && styles.successIconTextMistake]}>
                  {isMistake ? '✕' : '✓'}
                </Text>
              </View>
              <Text style={[styles.successTitle, isMistake && styles.successTitleMistake]}>
                {isMistake ? t('done_title_mistake', userLanguage) : t('done_title', userLanguage)}
              </Text>
              <Text style={styles.successSubtitle}>
                {isMistake 
                  ? t('done_desc_mistake', userLanguage)
                  : t('done_desc', userLanguage)}
              </Text>
              <TouchableOpacity style={[styles.actionBtn, styles.closeBtnFull, { marginTop: 15 }]} onPress={() => {
                setSelectedPin(null);
                setScreenMode('TACTICAL_MAP');
              }}>
                <Text style={styles.closeBtnFullText}>{t('btn_back_map', userLanguage)}</Text>
              </TouchableOpacity>
            </View>
          ) : (
            <View style={styles.wizardPanel}>
              {/* Step 1: Navigating */}
              {visualStep === 1 && (
                <View style={styles.wizardStepCard}>
                  <Text style={styles.stepNumLabel}>{t('step_nav', userLanguage)}</Text>
                  <Text style={styles.stepDesc}>{t('step_nav_desc', userLanguage)}</Text>
                  <TouchableOpacity style={[styles.actionBtn, styles.secondaryBtn, { marginBottom: 8 }]} onPress={handleOpenNavigation}>
                    <Text style={styles.secondaryBtnText}>{t('btn_launch_route', userLanguage)}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.actionBtn, styles.primaryBtn]} onPress={handleArrived}>
                    <Text style={styles.actionBtnText}>{t('btn_log_arrival', userLanguage)}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.mistakeLink} onPress={handleReportMistake}>
                    <Text style={styles.mistakeLinkText}>{t('btn_mark_false', userLanguage)}</Text>
                  </TouchableOpacity>
                </View>
              )}

              {/* Step 2: Resolution */}
              {visualStep === 2 && (
                <View style={styles.wizardStepCard}>
                  <Text style={styles.stepNumLabel}>{t('step_resolve', userLanguage)}</Text>
                  <Text style={styles.stepDesc}>{t('step_resolve_desc', userLanguage)}</Text>
                  
                  <View style={styles.resolutionActionsRow}>
                    <TouchableOpacity style={styles.mistakeBtnTerminal} onPress={handleReportMistake}>
                      <Text style={styles.mistakeBtnTerminalText}>{t('btn_report_mistake', userLanguage)}</Text>
                    </TouchableOpacity>
                    <TouchableOpacity style={styles.completeBtnTerminal} onPress={handleCompleteChecklist}>
                      <Text style={styles.completeBtnTerminalText}>{t('btn_mark_resolved', userLanguage)}</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}
            </View>
          )}
        </ScrollView>
      </SafeAreaView>
    );
  };

  const renderTacticalMapMode = () => {
    const parsedPin = parsePinParams(selectedPin);
    
    return (
      <View style={styles.container}>
        {/* Map Header bar */}
        <View style={styles.mapHeaderBar}>
          <TouchableOpacity 
            style={styles.backButton} 
            onPress={() => {
              setSelectedMissionId(null);
            }}
          >
            <Text style={styles.backButtonText}>{lt('btn_back_missions', userLanguage)}</Text>
          </TouchableOpacity>
          <Text style={styles.mapHeaderTitle} numberOfLines={1}>
            {missions.find(m => m.id === selectedMissionId)?.title.toUpperCase() || 'TACTICAL MAP'}
          </Text>
          {selectedMissionId && (
            <TouchableOpacity 
              style={styles.shareMissionBtn} 
              onPress={() => {
                const mObj = missions.find(m => m.id === selectedMissionId);
                if (mObj) handleShareMission(mObj);
              }}
            >
              <Text style={styles.shareMissionBtnText}>🔗 SHARE</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* 1. Map View (Dark Command Style) */}
        <View style={styles.mapContainer}>
          <MapView
            ref={mapRef}
            style={styles.map}
            initialRegion={{
              latitude: 1.2830,
              longitude: 103.8580,
              latitudeDelta: 0.03,
              longitudeDelta: 0.03,
            }}
            mapType="none"
            onPress={(e) => {
              if (isDrawingZone) {
                const { latitude, longitude } = e.nativeEvent.coordinate;
                setDrawingCoordinates(prev => [...prev, { latitude, longitude }]);
              }
            }}
          >
            <UrlTile
              urlTemplate="https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
              maximumZ={19}
              flipY={false}
            />
            
            {/* Render existing cleanup zones */}
            {!isDrawingZone && cleanupZones && cleanupZones.map((zone) => {
              if (!zone || !zone.boundary_geojson || zone.boundary_geojson.type !== 'Polygon') {
                return null;
              }
              const geojsonCoords = zone.boundary_geojson.coordinates[0];
              if (!geojsonCoords || geojsonCoords.length === 0) return null;
              
              const mapCoords = geojsonCoords.map(coord => ({
                latitude: coord[1],
                longitude: coord[0]
              }));

              const lats = mapCoords.map(c => c.latitude);
              const lons = mapCoords.map(c => c.longitude);
              const avgLat = lats.reduce((sum, val) => sum + val, 0) / lats.length;
              const avgLon = lons.reduce((sum, val) => sum + val, 0) / lons.length;

              // Check if zone is assigned to active volunteer
              const assignedVols = zone.boundary_geojson.properties?.assigned_volunteers || [];
              const isAssignedToMe = assignedVols.some(v => v.name === activeVolunteerName);
              
              const strokeColor = isAssignedToMe ? '#00fbfb' : '#e3b5ff';
              const fillColor = isAssignedToMe ? 'rgba(0, 251, 251, 0.16)' : 'rgba(227, 181, 255, 0.12)';
              const strokeWidth = isAssignedToMe ? 3.0 : 1.5;

              return (
                <React.Fragment key={zone.id}>
                  <Polygon
                    coordinates={mapCoords}
                    strokeColor={strokeColor}
                    fillColor={fillColor}
                    strokeWidth={strokeWidth}
                  />
                  <Marker
                    coordinate={{ latitude: avgLat, longitude: avgLon }}
                    anchor={{ x: 0.5, y: 0.5 }}
                  >
                    <View style={[styles.zoneLabelContainer, isAssignedToMe && styles.zoneLabelContainerActive]}>
                      <Text style={[styles.zoneLabelText, isAssignedToMe && styles.zoneLabelTextActive]}>
                        {isAssignedToMe ? `📍 ${zone.name}` : zone.name}
                      </Text>
                    </View>
                  </Marker>
                </React.Fragment>
              );
            })}

            {/* Render active drawn zone coordinates */}
            {isDrawingZone && drawingCoordinates.length > 0 && (
              <>
                {drawingCoordinates.length === 2 && (
                  <Polyline
                    coordinates={drawingCoordinates}
                    strokeColor="#00fbfb"
                    strokeWidth={2}
                  />
                )}
                {drawingCoordinates.length >= 3 && (
                  <Polygon
                    coordinates={drawingCoordinates}
                    strokeColor="#00fbfb"
                    fillColor="rgba(0, 251, 251, 0.25)"
                    strokeWidth={2.5}
                  />
                )}
                {drawingCoordinates.map((coord, idx) => (
                  <Marker
                    key={`draw-point-${idx}`}
                    coordinate={coord}
                    anchor={{ x: 0.5, y: 0.5 }}
                  >
                    <View style={styles.drawingDot}>
                      <Text style={styles.drawingDotText}>{idx + 1}</Text>
                    </View>
                  </Marker>
                ))}
              </>
            )}

            {/* Render pins */}
            {filteredPins.map((pin) => {
              if (!pin || typeof pin.latitude !== 'number' || typeof pin.longitude !== 'number') {
                return null;
              }

              // Check if pin is inside any zone assigned to active volunteer
              const isPinInMyAssignedZone = cleanupZones && cleanupZones.some(zone => {
                const assignedVols = zone.boundary_geojson?.properties?.assigned_volunteers || [];
                const isAssignedToMe = assignedVols.some(v => v.name === activeVolunteerName);
                return isAssignedToMe && isPinInZone(pin, zone);
              });

              return (
                <Marker
                  key={pin.id}
                  coordinate={{ latitude: pin.latitude, longitude: pin.longitude }}
                  onPress={() => handlePinPress(pin)}
                >
                  <View style={[
                    styles.annotationContainer, 
                    { borderColor: getStatusColor(pin.status) },
                    isPinInMyAssignedZone && styles.annotationContainerMyZone
                  ]}>
                    <View style={[
                      styles.annotationFill, 
                      { backgroundColor: isPinInMyAssignedZone && pin.status !== 'cleaned' ? '#00fbfb' : getStatusColor(pin.status) }
                    ]} />
                  </View>
                </Marker>
              );
            })}
          </MapView>
          
          {/* Top Banners */}
          {isDrawingZone ? (
            <View style={styles.drawingBanner}>
              <Text style={styles.drawingBannerText}>
                {t('draw_mode', userLanguage)} ({drawingCoordinates.length})
              </Text>
              <View style={styles.drawingActionsRow}>
                <TouchableOpacity style={styles.drawingBtnCancel} onPress={handleCancelDrawing}>
                  <Text style={styles.drawingBtnText}>{t('btn_draw_cancel', userLanguage)}</Text>
                </TouchableOpacity>
                <TouchableOpacity 
                  style={[styles.drawingBtnUndo, drawingCoordinates.length === 0 && styles.drawingBtnDisabled]} 
                  onPress={handleUndoLastPoint}
                  disabled={drawingCoordinates.length === 0}
                >
                  <Text style={styles.drawingBtnText}>{t('btn_draw_undo', userLanguage)}</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.drawingBtnSave} onPress={handleSaveZone}>
                  <Text style={styles.drawingBtnText}>{t('btn_draw_save', userLanguage)}</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : (
            <View style={styles.metricsContainer}>
              <View style={styles.metricsRow}>
                <Text style={[styles.metricItem, { color: '#EF4444' }]}>🔴 {filteredPins.filter(p => p.status === 'detected').length} {t('status_new', userLanguage)}</Text>
                <Text style={[styles.metricItem, { color: '#F59E0B' }]}>🟠 {filteredPins.filter(p => p.status === 'cleaning').length} {t('status_active', userLanguage)}</Text>
                <Text style={[styles.metricItem, { color: '#10B981' }]}>🟢 {filteredPins.filter(p => p.status === 'cleaned').length} {t('status_cleaned', userLanguage)}</Text>
              </View>
            </View>
          )}
          
          {/* Floating Focus Button */}
          {filteredPins && filteredPins.length > 0 && (
            <TouchableOpacity style={styles.focusFab} onPress={() => focusMapOnPins(true)}>
              <Text style={styles.focusFabText}>{t('focus_patrol', userLanguage)}</Text>
            </TouchableOpacity>
          )}

          {/* Floating Coordinator Sectors Hub button */}
          {userRole === 'coordinator' && !isDrawingZone && (
            <TouchableOpacity style={styles.zoneFab} onPress={() => setScreenMode('SECTORS_HUB')}>
              <Text style={styles.zoneFabText}>📁 {t('sec_sectoring', userLanguage).toUpperCase()}</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* 2. Glassmorphic Details slide-up Bottom Sheet */}
        {selectedPin ? (
          <View style={styles.detailPanel}>
            <View style={styles.panelHeader}>
              <View>
                <Text style={styles.panelTitle}>{t('overview_title', userLanguage)}</Text>
                <Text style={styles.panelSubtitle}>{t('signature_id', userLanguage)}: {(selectedPin.id || '').toString().substring(0, 8).toUpperCase()}</Text>
              </View>
              <TouchableOpacity style={styles.closeBtn} onPress={() => {
                setSelectedPin(null);
                setShowTelemetry(false);
              }}>
                <Text style={styles.closeBtnText}>✕</Text>
              </TouchableOpacity>
            </View>

            <ScrollView style={styles.panelScroll} contentContainerStyle={{ paddingBottom: 40 }} showsVerticalScrollIndicator={false}>
              {userRole === 'coordinator' ? (
                // COORDINATOR WORKFLOW
                <View style={styles.coordinatorLayout}>
                  <View style={styles.infoSplit}>
                    <View style={styles.imageContainer}>
                      <Image 
                        source={parsedPin.clean_image_url ? { uri: parsedPin.clean_image_url } : null} 
                        style={styles.evidenceImage}
                      />
                      <View style={styles.scanLine} />
                      <View style={styles.targetCornerTL} />
                      <View style={styles.targetCornerTR} />
                      <View style={styles.targetCornerBL} />
                      <View style={styles.targetCornerBR} />
                    </View>
                    
                    <View style={styles.telemetrySection}>
                      <TouchableOpacity style={styles.telemetryToggleInline} onPress={() => setShowTelemetry(!showTelemetry)}>
                        <Text style={styles.telemetryToggleTextInline}>
                          {showTelemetry ? t('hide_coords', userLanguage) : t('show_coords', userLanguage)}
                        </Text>
                      </TouchableOpacity>
                      
                      {showTelemetry ? (
                        <View style={styles.telemetryMiniBox}>
                          <Text style={styles.telemetryMono}>{t('accuracy', userLanguage)}: {((selectedPin.confidence || 0) * 100).toFixed(0)}% Conf</Text>
                          <Text style={styles.telemetryMono}>LAT: {typeof selectedPin.latitude === 'number' ? selectedPin.latitude.toFixed(6) : selectedPin.latitude}</Text>
                          <Text style={styles.telemetryMono}>LON: {typeof selectedPin.longitude === 'number' ? selectedPin.longitude.toFixed(6) : selectedPin.longitude}</Text>
                        </View>
                      ) : (
                        <View style={styles.telemetryMiniBoxPlaceholder}>
                          <Text style={styles.telemetryPlaceholderText}>{t('telemetry_hidden', userLanguage)}</Text>
                        </View>
                      )}
                    </View>
                  </View>

                  {/* Assignment Status/Action Section */}
                  {selectedPin.status === 'detected' ? (
                    <View style={styles.assignmentSection}>
                      <TouchableOpacity 
                        style={[styles.actionBtn, styles.primaryBtn]} 
                        onPress={() => setShowAssignModal(true)}
                      >
                        <Text style={styles.actionBtnText}>{t('delegate_officer', userLanguage)}</Text>
                      </TouchableOpacity>
                    </View>
                  ) : (
                    <View style={styles.assignmentStatusCard}>
                      <Text style={styles.label}>{lt('patrol_assignment_details', userLanguage)}</Text>
                      <View style={styles.assignDetailRow}>
                        <Text style={styles.assignDetailLabel}>{t('assignee', userLanguage)}:</Text>
                        <Text style={styles.assignDetailValue}>{parsedPin.assigned_to || t('unassigned', userLanguage)}</Text>
                      </View>
                      <View style={styles.assignDetailRow}>
                        <Text style={styles.assignDetailLabel}>{t('status', userLanguage)}:</Text>
                        <Text style={[styles.statusText, { color: getStatusColor(selectedPin.status) }]}>
                          {getTranslatedStatus(selectedPin.status).toUpperCase()}
                        </Text>
                      </View>
                      {selectedPin.status === 'cleaned' && parsedPin.is_mistake && (
                        <View style={styles.mistakeBanner}>
                          <Text style={styles.mistakeBannerText}>{t('mistake_flagged', userLanguage)}</Text>
                        </View>
                      )}
                      {selectedPin.status === 'cleaning' && (
                        <TouchableOpacity style={styles.reassignBtn} onPress={handleReassign}>
                          <Text style={styles.reassignBtnText}>{t('reset_task', userLanguage)}</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  )}
                </View>
              ) : (
                // VOLUNTEER WORKFLOW
                <View style={styles.volunteerLayout}>
                  <View style={styles.infoSplit}>
                    <View style={styles.imageContainer}>
                      <Image 
                        source={parsedPin.clean_image_url ? { uri: parsedPin.clean_image_url } : null} 
                        style={styles.evidenceImage}
                      />
                      <View style={styles.scanLine} />
                      <View style={styles.targetCornerTL} />
                      <View style={styles.targetCornerTR} />
                      <View style={styles.targetCornerBL} />
                      <View style={styles.targetCornerBR} />
                    </View>
                  </View>
                  
                  {selectedPin.status === 'cleaned' ? (
                    <View style={styles.cleanedBadgePanel}>
                      <Text style={[styles.cleanedBadgeText, { color: getStatusColor('cleaned') }]}>
                        {parsedPin.is_mistake ? t('mistake_flagged', userLanguage) : t('shoreline_clear', userLanguage)}
                      </Text>
                      <Text style={styles.cleanedBadgeSub}>
                        {parsedPin.is_mistake 
                          ? t('mistake_resolved_sub', userLanguage)
                          : `${t('shoreline_clear_sub', userLanguage)} ${parsedPin.assigned_to || 'Unknown'}`}
                      </Text>
                    </View>
                  ) : (
                    <View style={styles.volunteerActionBlock}>
                      <TouchableOpacity 
                        style={[styles.actionBtn, styles.primaryBtn]} 
                        onPress={async () => {
                          if (selectedPin.status === 'detected') {
                            await handleStartCleaning();
                          }
                          setScreenMode('TASK_RUN');
                        }}
                      >
                        <Text style={styles.actionBtnText}>
                          {selectedPin.status === 'detected' ? t('accept_patrol', userLanguage) : t('resume_patrol', userLanguage)}
                        </Text>
                      </TouchableOpacity>
                    </View>
                  )}
                </View>
              )}
            </ScrollView>
          </View>
        ) : (
          <View style={styles.welcomePanel}>
            <Text style={styles.welcomeTitle}>{t('tactical_title', userLanguage)}</Text>
            <Text style={styles.welcomeSubtitle}>
              {userRole === 'coordinator' 
                ? t('tactical_subtitle_coord', userLanguage)
                : t('tactical_subtitle_vol', userLanguage)}
            </Text>
            
            {/* Litter Detections List at the bottom of Map when no pin is selected */}
            <Text style={styles.litterListHeader}>{t('detections_header', userLanguage)}</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.horizontalLitterList}>
              {filteredPins.filter(p => p.status !== 'cleaned').length === 0 ? (
                <View style={styles.emptyLitterBox}>
                  <Text style={styles.emptyLitterText}>{t('all_secured', userLanguage)}</Text>
                </View>
              ) : (
                filteredPins.filter(p => p.status !== 'cleaned').map(pin => {
                  const pParsed = parsePinParams(pin);
                  return (
                    <TouchableOpacity 
                      key={pin.id} 
                      style={styles.litterListItemCard}
                      onPress={() => handlePinPress(pin)}
                    >
                      <Image 
                        source={pParsed.clean_image_url ? { uri: pParsed.clean_image_url } : null} 
                        style={styles.litterListImage}
                      />
                      <View style={styles.litterListInfo}>
                        <Text style={styles.litterListConf}>{((pin.confidence || 0) * 100).toFixed(0)}% Conf</Text>
                        <Text style={[styles.litterListStatus, { color: getStatusColor(pin.status) }]}>
                          {getTranslatedStatus(pin.status).toUpperCase()}
                        </Text>
                      </View>
                    </TouchableOpacity>
                  );
                })
              )}
            </ScrollView>
          </View>
        )}
      </View>
    );
  };

  const parsedPin = parsePinParams(selectedPin);

  // Screen Routing Render Tree
  if (screenMode === 'MISSION_LIST' || selectedMissionId === null) {
    return renderMissionListMode();
  }

  if (screenMode === 'TASK_RUN' && selectedPin) {
    return renderTaskRunMode();
  }

  if (screenMode === 'SECTORS_HUB') {
    return renderSectorsHubMode();
  }

  return (
    <View style={{ flex: 1 }}>
      {renderTacticalMapMode()}

      {/* 3. Absolute Overlay Modal for Coordinator to Delegate Task */}
      {showAssignModal && (
        <View style={styles.assignOverlay}>
          <View style={styles.assignModal}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{t('delegate_officer', userLanguage).toUpperCase()}</Text>
              <TouchableOpacity style={styles.modalCloseBtn} onPress={() => setShowAssignModal(false)}>
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.modalSubtitle}>{lt('select_online_patroller', userLanguage)}</Text>
            
            {onlineVolunteers.length === 0 ? (
              <View style={{ paddingVertical: 30, alignItems: 'center' }}>
                <Text style={styles.emptyText}>{lt('no_volunteers_online', userLanguage)}</Text>
              </View>
            ) : (
              <ScrollView style={styles.modalScroll} showsVerticalScrollIndicator={false}>
                {onlineVolunteers.map(vol => (
                  <TouchableOpacity
                    key={vol.id}
                    style={styles.modalVolCard}
                    onPress={() => {
                      handleAssignTask(vol.name);
                      setShowAssignModal(false);
                    }}
                  >
                    <View style={styles.modalVolAvatar}>
                      <Text style={styles.modalVolAvatarText}>
                        {vol.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase()}
                      </Text>
                    </View>
                    <View style={{ flex: 1 }}>
                      <Text style={styles.modalVolName}>{vol.name}</Text>
                      <Text style={styles.modalVolStatus}>🟢 {t('vol_active', userLanguage)}</Text>
                    </View>
                    <Text style={styles.modalSelectText}>{lt('btn_assign', userLanguage)}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            )}
          </View>
        </View>
      )}

      {/* 4. Custom Overlay Modal for naming the drawn sector zone */}
      {showZoneNameModal && (
        <View style={styles.assignOverlay}>
          <View style={styles.assignModal}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{t('prompt_sector_name', userLanguage).toUpperCase()}</Text>
              <TouchableOpacity style={styles.modalCloseBtn} onPress={() => setShowZoneNameModal(false)}>
                <Text style={styles.modalCloseText}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.modalSubtitle}>{t('prompt_sector_desc', userLanguage)}</Text>
            
            <TextInput
              style={styles.modalTextInput}
              placeholder="e.g. Bang Saen Beach South"
              placeholderTextColor="rgba(255,255,255,0.3)"
              value={newZoneName}
              onChangeText={setNewZoneName}
              autoFocus
            />

            <View style={styles.modalActionsRow}>
              <TouchableOpacity 
                style={[styles.modalBtn, styles.modalBtnCancel]} 
                onPress={() => setShowZoneNameModal(false)}
              >
                <Text style={styles.modalBtnText}>{t('btn_draw_cancel', userLanguage)}</Text>
              </TouchableOpacity>
              <TouchableOpacity 
                style={[styles.modalBtn, styles.modalBtnConfirm]} 
                onPress={submitNewZone}
              >
                <Text style={styles.modalBtnConfirmText}>{t('prompt_confirm', userLanguage)}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#050505',
  },
  mapContainer: {
    flex: 1,
    position: 'relative',
  },
  map: {
    flex: 1,
  },
  annotationContainer: {
    width: 18,
    height: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#050505',
    borderRadius: 9,
    borderWidth: 2.5,
  },
  annotationFill: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  metricsContainer: {
    position: 'absolute',
    top: 16,
    left: 16,
    right: 16,
    backgroundColor: 'rgba(20, 20, 20, 0.92)',
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  metricsTitle: {
    color: '#e5e2e1',
    fontSize: 10,
    fontWeight: 'bold',
    marginBottom: 4,
    textTransform: 'uppercase',
    fontFamily: MONOSPACE_FONT,
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  metricItem: {
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  zoneFab: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    backgroundColor: '#131313',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#e3b5ff',
  },
  zoneFabText: {
    color: '#e3b5ff',
    fontWeight: 'bold',
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
  },
  detailPanel: {
    backgroundColor: '#131313',
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    paddingHorizontal: 16,
    paddingTop: 16,
    borderTopWidth: 1.5,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
    maxHeight: '62%',
  },
  panelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  panelTitle: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: 'bold',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  panelSubtitle: {
    color: '#b9cac9',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
  },
  closeBtn: {
    width: 28,
    height: 28,
    borderRadius: 4,
    backgroundColor: '#201f1f',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  closeBtnText: {
    color: '#e5e2e1',
    fontSize: 12,
    fontWeight: 'bold',
  },
  panelScroll: {
    marginBottom: 16,
  },
  coordinatorLayout: {
    flexDirection: 'column',
    gap: 14,
  },
  volunteerLayout: {
    flexDirection: 'column',
  },
  stepContent: {
    flexDirection: 'column',
    gap: 14,
  },
  infoSplit: {
    flexDirection: 'row',
    gap: 14,
  },
  imageContainer: {
    position: 'relative',
    width: 120,
    height: 120,
    borderRadius: 4,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  evidenceImage: {
    width: '100%',
    height: '100%',
    backgroundColor: '#050505',
  },
  scanLine: {
    position: 'absolute',
    width: '100%',
    height: 2,
    backgroundColor: '#00fbfb',
    top: '40%',
    opacity: 0.5,
  },
  targetCornerTL: {
    position: 'absolute',
    top: 4,
    left: 4,
    width: 8,
    height: 8,
    borderTopWidth: 2,
    borderLeftWidth: 2,
    borderColor: '#00fbfb',
  },
  targetCornerTR: {
    position: 'absolute',
    top: 4,
    right: 4,
    width: 8,
    height: 8,
    borderTopWidth: 2,
    borderRightWidth: 2,
    borderColor: '#00fbfb',
  },
  targetCornerBL: {
    position: 'absolute',
    bottom: 4,
    left: 4,
    width: 8,
    height: 8,
    borderBottomWidth: 2,
    borderLeftWidth: 2,
    borderColor: '#00fbfb',
  },
  targetCornerBR: {
    position: 'absolute',
    bottom: 4,
    right: 4,
    width: 8,
    height: 8,
    borderBottomWidth: 2,
    borderRightWidth: 2,
    borderColor: '#00fbfb',
  },
  telemetrySection: {
    flex: 1,
    justifyContent: 'space-between',
  },
  detailsRow: {
    marginBottom: 4,
  },
  label: {
    color: '#b9cac9',
    fontSize: 9,
    textTransform: 'uppercase',
    fontWeight: '700',
    marginBottom: 2,
    fontFamily: MONOSPACE_FONT,
  },
  badge: {
    paddingVertical: 2,
    paddingHorizontal: 6,
    borderRadius: 2,
    alignSelf: 'flex-start',
  },
  badgeText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  statusText: {
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  coordText: {
    fontFamily: MONOSPACE_FONT,
    color: '#ffffff',
    fontSize: 11,
  },
  actionBtn: {
    height: 40,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryBtn: {
    backgroundColor: '#00fbfb',
  },
  secondaryBtn: {
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  successBtn: {
    backgroundColor: '#10B981',
  },
  actionBtnText: {
    color: '#050505',
    fontWeight: 'bold',
    fontSize: 12,
    letterSpacing: 0.5,
    fontFamily: MONOSPACE_FONT,
  },
  secondaryBtnText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 12,
    letterSpacing: 0.5,
    fontFamily: MONOSPACE_FONT,
  },
  sectionHeader: {
    color: '#00fbfb',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 1,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  assignmentSection: {
    marginTop: 6,
  },
  volunteerCarousel: {
    flexDirection: 'row',
    marginBottom: 14,
    gap: 8,
  },
  volunteerCard: {
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 4,
    padding: 10,
    alignItems: 'center',
    width: 90,
    marginRight: 8,
  },
  volunteerCardSelected: {
    borderColor: '#00fbfb',
    backgroundColor: 'rgba(0, 251, 251, 0.05)',
  },
  avatarCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#353534',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 6,
  },
  avatarCircleSelected: {
    backgroundColor: '#00fbfb',
  },
  avatarInitials: {
    color: '#e5e2e1',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  avatarInitialsSelected: {
    color: '#050505',
  },
  volunteerCardName: {
    color: '#e5e2e1',
    fontSize: 10,
    fontWeight: '600',
    marginBottom: 2,
  },
  volunteerCardNameSelected: {
    color: '#00fbfb',
    fontWeight: 'bold',
  },
  volunteerCardStatus: {
    color: '#b9cac9',
    fontSize: 8,
    fontFamily: MONOSPACE_FONT,
  },
  assignBtnEnabled: {
    backgroundColor: '#00fbfb',
    width: '100%',
  },
  assignBtnDisabled: {
    backgroundColor: '#201f1f',
    width: '100%',
    opacity: 0.5,
  },
  assignBtnText: {
    color: '#050505',
    fontWeight: 'bold',
    fontSize: 11,
    fontFamily: MONOSPACE_FONT,
  },
  assignmentStatusCard: {
    backgroundColor: '#201f1f',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    padding: 12,
  },
  assignDetailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  assignDetailLabel: {
    color: '#b9cac9',
    fontSize: 11,
    fontFamily: MONOSPACE_FONT,
  },
  assignDetailValue: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  reassignBtn: {
    marginTop: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: '#EF4444',
    borderRadius: 4,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  reassignBtnText: {
    color: '#EF4444',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  navDetailCard: {
    backgroundColor: '#201f1f',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    padding: 12,
    marginBottom: 6,
  },
  navDetailText: {
    color: '#b9cac9',
    fontSize: 11,
    lineHeight: 16,
    marginBottom: 10,
  },
  navCoordsBox: {
    backgroundColor: '#050505',
    borderRadius: 2,
    padding: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  navCoordMono: {
    color: '#00fbfb',
    fontFamily: MONOSPACE_FONT,
    fontSize: 12,
    fontWeight: 'bold',
  },
  checklistCard: {
    backgroundColor: '#201f1f',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    padding: 12,
  },
  checklistFormGroup: {
    marginBottom: 12,
  },
  checklistFormLabel: {
    color: '#b9cac9',
    fontSize: 10,
    fontWeight: '700',
    marginBottom: 6,
    textTransform: 'uppercase',
    fontFamily: MONOSPACE_FONT,
  },
  checklistInput: {
    backgroundColor: '#050505',
    color: '#ffffff',
    borderRadius: 2,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    paddingHorizontal: 10,
    paddingVertical: 6,
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
  },
  bagsCounterContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
  },
  counterBtn: {
    width: 28,
    height: 28,
    backgroundColor: '#050505',
    borderRadius: 2,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  counterBtnText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: 'bold',
  },
  bagsCountValue: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  successContainer: {
    alignItems: 'center',
    backgroundColor: '#201f1f',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#10B981',
    padding: 16,
  },
  successContainerMistake: {
    borderColor: '#EF4444',
  },
  successIconCircle: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1.5,
    borderColor: '#10B981',
    marginBottom: 10,
  },
  successIconCircleMistake: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderColor: '#EF4444',
  },
  successIconText: {
    color: '#10B981',
    fontSize: 18,
    fontWeight: 'bold',
  },
  successIconTextMistake: {
    color: '#EF4444',
  },
  successTitle: {
    color: '#10B981',
    fontSize: 13,
    fontWeight: 'bold',
    letterSpacing: 0.5,
    fontFamily: MONOSPACE_FONT,
    marginBottom: 6,
  },
  successTitleMistake: {
    color: '#EF4444',
  },
  successSubtitle: {
    color: '#b9cac9',
    fontSize: 10,
    textAlign: 'center',
    lineHeight: 14,
    marginBottom: 12,
  },
  successStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
    borderTopWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    paddingTop: 10,
  },
  successStatItem: {
    alignItems: 'center',
  },
  successStatLabel: {
    color: '#b9cac9',
    fontSize: 8,
    fontFamily: MONOSPACE_FONT,
    marginBottom: 2,
  },
  successStatValue: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  successStatDivider: {
    width: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    height: '100%',
  },
  closeBtnFull: {
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    height: 40,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
    width: '100%',
  },
  closeBtnFullText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
  },
  welcomePanel: {
    backgroundColor: '#131313',
    padding: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    borderTopWidth: 1.5,
    borderTopColor: 'rgba(255, 255, 255, 0.1)',
  },
  welcomeTitle: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 6,
    textTransform: 'uppercase',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  welcomeSubtitle: {
    color: '#b9cac9',
    fontSize: 10,
    textAlign: 'center',
    lineHeight: 14,
  },
  focusFab: {
    position: 'absolute',
    bottom: 20,
    left: 20,
    backgroundColor: '#131313',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 4,
    borderWidth: 1.5,
    borderColor: '#00fbfb',
  },
  focusFabText: {
    color: '#00fbfb',
    fontWeight: 'bold',
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
  },
  // Step indicator styles
  stepContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 16,
    paddingHorizontal: 4,
  },
  stepWrapper: {
    alignItems: 'center',
  },
  stepDot: {
    width: 22,
    height: 22,
    borderRadius: 11,
    borderWidth: 1,
    borderColor: '#b9cac9',
    backgroundColor: '#050505',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepDotActive: {
    borderColor: '#00fbfb',
    backgroundColor: '#00fbfb',
  },
  stepDotCompleted: {
    borderColor: '#10B981',
    backgroundColor: '#10B981',
  },
  stepDotText: {
    color: '#b9cac9',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  stepDotTextActive: {
    color: '#050505',
  },
  stepLabel: {
    fontSize: 8,
    color: '#b9cac9',
    marginTop: 4,
    fontFamily: MONOSPACE_FONT,
  },
  stepLabelActive: {
    color: '#00fbfb',
    fontWeight: 'bold',
  },
  stepLabelCompleted: {
    color: '#10B981',
  },
  stepLine: {
    flex: 1,
    height: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    marginHorizontal: 4,
    alignSelf: 'center',
    top: -6,
  },
  stepLineCompleted: {
    backgroundColor: '#10B981',
  },
  // Action Row layouts
  step1ActionRow: {
    flexDirection: 'row',
    gap: 8,
    width: '100%',
  },
  step2ActionRow: {
    flexDirection: 'row',
    gap: 8,
    width: '100%',
  },
  resolveActionRow: {
    flexDirection: 'row',
    gap: 8,
    width: '100%',
    marginTop: 10,
  },
  mistakeBtn: {
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: '#EF4444',
    borderRadius: 4,
    flex: 1,
  },
  mistakeBtnText: {
    color: '#EF4444',
    fontWeight: 'bold',
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
  },
  mistakeBanner: {
    marginTop: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderWidth: 1,
    borderColor: '#EF4444',
    borderRadius: 4,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  mistakeBannerText: {
    color: '#EF4444',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  missionSelectorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
    gap: 8,
  },
  missionLabel: {
    color: '#00fbfb',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  missionList: {
    gap: 6,
    paddingRight: 10,
    alignItems: 'center',
  },
  missionPill: {
    backgroundColor: '#201f1f',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  missionPillActive: {
    borderColor: '#00fbfb',
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
  },
  missionPillText: {
    color: '#b9cac9',
    fontSize: 8,
    fontFamily: MONOSPACE_FONT,
  },
  missionPillTextActive: {
    color: '#00fbfb',
    fontWeight: 'bold',
  },
  metricsDivider: {
    height: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    marginVertical: 6,
  },
  // Refactored UI Decluttered Styles
  telemetryToggleInline: {
    backgroundColor: '#201f1f',
    paddingVertical: 5,
    paddingHorizontal: 8,
    borderRadius: 3,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    alignSelf: 'flex-start',
    marginBottom: 6,
  },
  telemetryToggleTextInline: {
    color: '#00fbfb',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  telemetryMiniBox: {
    backgroundColor: '#050505',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 4,
    padding: 8,
    gap: 4,
  },
  telemetryMiniBoxPlaceholder: {
    paddingVertical: 8,
  },
  telemetryPlaceholderText: {
    color: 'rgba(255, 255, 255, 0.3)',
    fontSize: 9,
    fontStyle: 'italic',
    fontFamily: MONOSPACE_FONT,
  },
  telemetryMono: {
    color: '#b9cac9',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
  },
  volunteerActionBlock: {
    flexDirection: 'column',
    marginTop: 6,
    alignItems: 'stretch',
  },
  mistakeLink: {
    alignItems: 'center',
    paddingVertical: 8,
    marginTop: 6,
  },
  mistakeLinkText: {
    color: '#EF4444',
    fontSize: 10,
    fontWeight: 'bold',
    textDecorationLine: 'underline',
    fontFamily: MONOSPACE_FONT,
  },
  quickResolveLink: {
    alignItems: 'center',
    paddingVertical: 8,
    marginTop: 6,
  },
  quickResolveLinkText: {
    color: '#00fbfb',
    fontSize: 10,
    fontWeight: 'bold',
    textDecorationLine: 'underline',
    fontFamily: MONOSPACE_FONT,
  },
  assignOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.85)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
    zIndex: 9999,
  },
  assignModal: {
    backgroundColor: '#131313',
    width: '100%',
    maxHeight: '80%',
    borderRadius: 8,
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    padding: 16,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  modalTitle: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  modalCloseBtn: {
    width: 26,
    height: 26,
    backgroundColor: '#201f1f',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  modalCloseText: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold',
  },
  modalSubtitle: {
    color: '#b9cac9',
    fontSize: 10,
    lineHeight: 14,
    marginBottom: 16,
  },
  modalScroll: {
    flexDirection: 'column',
  },
  modalVolCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#050505',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    padding: 12,
    marginBottom: 10,
    gap: 12,
  },
  modalVolAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#201f1f',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  modalVolAvatarText: {
    color: '#b9cac9',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  modalVolName: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: 'bold',
  },
  modalVolStatus: {
    color: '#00fbfb',
    fontSize: 8,
    fontFamily: MONOSPACE_FONT,
    marginTop: 2,
  },
  modalSelectText: {
    color: '#e3b5ff',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  emptyText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 11,
    fontStyle: 'italic',
  },
  shareMissionBtn: {
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(0, 251, 251, 0.25)',
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    marginLeft: 6,
    alignSelf: 'center',
  },
  shareMissionBtnText: {
    color: '#00fbfb',
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  // Mission Feed / List Dashboard Feed styles
  missionListContainer: {
    flex: 1,
    backgroundColor: '#050505',
    padding: 16,
  },
  mainHeader: {
    color: '#00fbfb',
    fontSize: 14,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    marginBottom: 6,
    marginTop: 10,
    textTransform: 'uppercase',
  },
  mainSubheader: {
    color: '#b9cac9',
    fontSize: 10,
    lineHeight: 14,
    fontFamily: MONOSPACE_FONT,
    marginBottom: 20,
  },
  missionScroll: {
    flex: 1,
  },
  emptyFeedBox: {
    backgroundColor: '#131313',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 6,
    padding: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 20,
  },
  emptyFeedText: {
    color: 'rgba(255, 255, 255, 0.4)',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
    textAlign: 'center',
  },
  missionCard: {
    backgroundColor: '#131313',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 8,
    padding: 16,
    marginBottom: 14,
  },
  missionCardCompleted: {
    borderColor: '#10B981',
  },
  missionCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  titleCol: {
    flex: 1,
    marginRight: 10,
  },
  missionCardTitle: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  missionCardDate: {
    color: '#b9cac9',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
    marginTop: 2,
  },
  tagBadge: {
    paddingVertical: 3,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
  },
  tagActive: {
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    borderColor: '#00fbfb',
  },
  tagCompleted: {
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    borderColor: '#10B981',
  },
  tagBadgeText: {
    color: '#ffffff',
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  missionCardDesc: {
    color: '#b9cac9',
    fontSize: 10,
    lineHeight: 14,
    marginBottom: 12,
  },
  missionProgressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#050505',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.03)',
    borderRadius: 4,
    padding: 10,
    marginBottom: 12,
  },
  progressLabelCol: {
    flexDirection: 'column',
    width: 110,
  },
  progressLabelText: {
    color: '#b9cac9',
    fontSize: 8,
    fontFamily: MONOSPACE_FONT,
  },
  progressValText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    marginTop: 2,
  },
  progressTrack: {
    flex: 1,
    height: 6,
    backgroundColor: '#201f1f',
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressIndicatorFill: {
    height: '100%',
    backgroundColor: '#10B981',
    borderRadius: 3,
  },
  missionCardActions: {
    flexDirection: 'row',
    gap: 8,
  },
  launchBtn: {
    flex: 1.5,
    height: 36,
    backgroundColor: '#00fbfb',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  launchBtnCompleted: {
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: '#10B981',
  },
  launchBtnText: {
    color: '#050505',
    fontWeight: 'bold',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },
  shareBtnPill: {
    flex: 1,
    height: 36,
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shareBtnPillText: {
    color: '#ffffff',
    fontWeight: 'bold',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
  },

  // Map Screen Header Styles
  mapHeaderBar: {
    flexDirection: 'row',
    height: 56,
    backgroundColor: '#131313',
    borderBottomWidth: 1.5,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
  },
  mapHeaderTitle: {
    color: '#ffffff',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    flex: 1,
    textAlign: 'center',
    marginHorizontal: 10,
  },
  backButton: {
    height: 32,
    paddingHorizontal: 12,
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backButtonText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },

  // Task Terminal styles
  taskTerminalContainer: {
    flex: 1,
    backgroundColor: '#050505',
  },
  terminalHeader: {
    flexDirection: 'row',
    height: 56,
    backgroundColor: '#131313',
    borderBottomWidth: 1.5,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
  },
  backButtonTerminal: {
    height: 32,
    paddingHorizontal: 12,
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  backButtonTextTerminal: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  terminalTitleText: {
    color: '#00fbfb',
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    flex: 1,
    textAlign: 'right',
  },
  terminalScroll: {
    flex: 1,
    padding: 16,
  },
  terminalImageCard: {
    backgroundColor: '#131313',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 6,
    padding: 12,
    marginBottom: 14,
  },
  terminalImageHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  terminalPanelLabel: {
    color: '#00fbfb',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  terminalPanelVal: {
    color: '#ffffff',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
  },
  terminalImageContainer: {
    position: 'relative',
    width: '100%',
    height: 220,
    borderRadius: 4,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  terminalEvidenceImage: {
    width: '100%',
    height: '100%',
    backgroundColor: '#050505',
    resizeMode: 'cover',
  },
  terminalTelemetryCard: {
    backgroundColor: '#131313',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 6,
    padding: 12,
    marginBottom: 14,
  },
  terminalActionBtnOutline: {
    height: 38,
    borderWidth: 1.5,
    borderColor: '#00fbfb',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    marginTop: 8,
  },
  terminalActionBtnOutlineText: {
    color: '#00fbfb',
    fontWeight: 'bold',
    fontSize: 11,
    fontFamily: MONOSPACE_FONT,
  },
  wizardPanel: {
    marginBottom: 20,
  },
  wizardStepCard: {
    backgroundColor: '#131313',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 6,
    padding: 16,
  },
  stepNumLabel: {
    color: '#e3b5ff',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    marginBottom: 6,
  },
  stepDesc: {
    color: '#b9cac9',
    fontSize: 11,
    lineHeight: 15,
    marginBottom: 14,
  },
  resolutionActionsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  mistakeBtnTerminal: {
    flex: 1,
    height: 38,
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    borderWidth: 1.5,
    borderColor: '#EF4444',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  mistakeBtnTerminalText: {
    color: '#EF4444',
    fontWeight: 'bold',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
  },
  completeBtnTerminal: {
    flex: 1.2,
    height: 38,
    backgroundColor: '#10B981',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  completeBtnTerminalText: {
    color: '#050505',
    fontWeight: 'bold',
    fontSize: 10,
    fontFamily: MONOSPACE_FONT,
  },
  cleanedBadgePanel: {
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    borderWidth: 1.5,
    borderColor: '#10B981',
    borderRadius: 6,
    padding: 16,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  cleanedBadgeText: {
    fontSize: 11,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  cleanedBadgeSub: {
    color: '#b9cac9',
    fontSize: 9,
    textAlign: 'center',
    lineHeight: 13,
    marginTop: 6,
  },

  // Litter list styles
  litterListHeader: {
    color: '#00fbfb',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    letterSpacing: 0.5,
    marginTop: 16,
    marginBottom: 10,
    textTransform: 'uppercase',
  },
  horizontalLitterList: {
    flexDirection: 'row',
    marginBottom: 10,
  },
  emptyLitterBox: {
    backgroundColor: '#050505',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 4,
    paddingVertical: 14,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    width: 280,
  },
  emptyLitterText: {
    color: 'rgba(255, 255, 255, 0.3)',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
    textAlign: 'center',
  },
  litterListItemCard: {
    backgroundColor: '#050505',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    borderRadius: 4,
    padding: 8,
    marginRight: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    width: 140,
  },
  litterListImage: {
    width: 32,
    height: 32,
    borderRadius: 2,
    backgroundColor: '#050505',
  },
  litterListInfo: {
    flex: 1,
  },
  litterListConf: {
    color: '#ffffff',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
  },
  litterListStatus: {
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    marginTop: 2,
  },

  // Telemetry styles
  telemetryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.03)',
  },
  telemetryKey: {
    color: '#b9cac9',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
  },
  telemetryValueText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  // Drawing banner styles
  drawingBanner: {
    position: 'absolute',
    top: 16,
    left: 16,
    right: 16,
    backgroundColor: 'rgba(20, 20, 20, 0.95)',
    borderRadius: 8,
    padding: 12,
    borderWidth: 1.5,
    borderColor: '#00fbfb',
    shadowColor: '#00fbfb',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 6,
  },
  drawingBannerText: {
    color: '#00fbfb',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    textAlign: 'center',
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  drawingActionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 8,
  },
  drawingBtnCancel: {
    flex: 1,
    height: 32,
    backgroundColor: 'rgba(239, 68, 68, 0.12)',
    borderWidth: 1,
    borderColor: '#EF4444',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  drawingBtnUndo: {
    flex: 1,
    height: 32,
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  drawingBtnSave: {
    flex: 1.2,
    height: 32,
    backgroundColor: '#00fbfb',
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  drawingBtnDisabled: {
    opacity: 0.35,
  },
  drawingBtnText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  drawingDot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: '#00fbfb',
    borderWidth: 1.5,
    borderColor: '#050505',
    alignItems: 'center',
    justifyContent: 'center',
  },
  drawingDotText: {
    color: '#050505',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  zoneLabelContainer: {
    backgroundColor: 'rgba(19, 19, 19, 0.9)',
    paddingVertical: 3,
    paddingHorizontal: 6,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(227, 181, 255, 0.35)',
  },
  zoneLabelText: {
    color: '#e3b5ff',
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    textTransform: 'uppercase',
  },
  zoneLabelContainerActive: {
    borderColor: '#00fbfb',
  },
  zoneLabelTextActive: {
    color: '#00fbfb',
  },
  modalTextInput: {
    backgroundColor: '#050505',
    color: '#ffffff',
    borderRadius: 4,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.15)',
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 12,
    fontFamily: MONOSPACE_FONT,
    marginBottom: 16,
  },
  modalActionsRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 6,
  },
  modalBtn: {
    height: 36,
    paddingHorizontal: 16,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalBtnCancel: {
    backgroundColor: '#201f1f',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  modalBtnConfirm: {
    backgroundColor: '#e3b5ff',
  },
  modalBtnText: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  modalBtnConfirmText: {
    color: '#050505',
    fontSize: 10,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  // Sectors Hub styles
  sectorsHubContainer: {
    flex: 1,
    backgroundColor: '#050505',
    padding: 16,
  },
  hubHeaderBlock: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#131313',
    borderRadius: 6,
    padding: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    marginBottom: 16,
    marginTop: 8,
  },
  hubDescText: {
    color: '#b9cac9',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
    flex: 1,
    marginRight: 12,
    lineHeight: 13,
  },
  hubDrawBtn: {
    backgroundColor: '#00fbfb',
    borderRadius: 4,
    paddingVertical: 6,
    paddingHorizontal: 12,
  },
  hubDrawBtnText: {
    color: '#050505',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  sectorsListScroll: {
    flex: 1,
  },
  hubEmptyBox: {
    backgroundColor: '#131313',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
    paddingVertical: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  hubEmptyText: {
    color: 'rgba(255, 255, 255, 0.35)',
    fontSize: 10,
    fontStyle: 'italic',
    fontFamily: MONOSPACE_FONT,
  },
  sectorCard: {
    backgroundColor: '#131313',
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 14,
    marginBottom: 12,
  },
  sectorCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  sectorCardName: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  sectorStatusBadge: {
    paddingVertical: 2,
    paddingHorizontal: 6,
    borderRadius: 4,
    borderWidth: 1,
  },
  statusCompleted: {
    backgroundColor: 'rgba(16, 185, 129, 0.08)',
    borderColor: '#10B981',
  },
  statusPending: {
    backgroundColor: 'rgba(245, 158, 11, 0.08)',
    borderColor: '#F59E0B',
  },
  sectorStatusText: {
    fontSize: 8,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
    color: '#ffffff',
  },
  assignedSection: {
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
    paddingTop: 8,
    marginBottom: 12,
  },
  assignedLabel: {
    color: '#b9cac9',
    fontSize: 8,
    fontFamily: MONOSPACE_FONT,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  assignedEmptyText: {
    color: '#EF4444',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
  },
  volPillContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  volPill: {
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 12,
    paddingVertical: 3,
    paddingHorizontal: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  volPillText: {
    color: '#ffffff',
    fontSize: 9,
    fontFamily: MONOSPACE_FONT,
  },
  sectorCardActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
  },
  sectorAssignBtn: {
    backgroundColor: 'rgba(0, 251, 251, 0.08)',
    borderWidth: 1,
    borderColor: '#00fbfb',
    borderRadius: 4,
    paddingVertical: 5,
    paddingHorizontal: 12,
  },
  sectorDeleteBtn: {
    backgroundColor: 'rgba(239, 68, 68, 0.08)',
    borderWidth: 1,
    borderColor: '#EF4444',
    borderRadius: 4,
    paddingVertical: 5,
    paddingHorizontal: 12,
  },
  sectorActionBtnText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: 'bold',
    fontFamily: MONOSPACE_FONT,
  },
  modalVolCardSelected: {
    borderColor: '#00fbfb',
    backgroundColor: 'rgba(0, 251, 251, 0.05)',
  },
  checkbox: {
    width: 16,
    height: 16,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.3)',
    borderRadius: 3,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#050505',
  },
  checkboxChecked: {
    borderColor: '#00fbfb',
    backgroundColor: '#00fbfb',
  },
  checkboxTick: {
    color: '#050505',
    fontSize: 10,
    fontWeight: 'bold',
  },
  annotationContainerMyZone: {
    borderColor: '#00fbfb',
    borderWidth: 2.5,
    shadowColor: '#00fbfb',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 5,
    elevation: 5,
  },
});
