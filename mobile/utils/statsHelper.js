// Shared Stats & Badges helper for Coastal Patrol app

export const parsePinParams = (pin) => {
  if (!pin) return {};
  const data = {
    ...pin,
    assigned_to: null,
    weight_collected: null,
    bags_used: null,
    is_mistake: false,
    clean_image_url: pin.image_url,
  };
  if (pin.image_url && pin.image_url.includes('#')) {
    const parts = pin.image_url.split('#');
    data.clean_image_url = parts[0];
    const query = parts[1];
    query.split('&').forEach(pair => {
      const [k, v] = pair.split('=');
      if (k === 'assigned_to') data.assigned_to = decodeURIComponent(v);
      if (k === 'weight') data.weight_collected = parseFloat(v);
      if (k === 'bags') data.bags_used = parseInt(v);
      if (k === 'is_mistake') data.is_mistake = v === 'true';
    });
  }
  return data;
};

// Helper to serialize pin params into an image URL fragment
export const buildPinImageUrl = (url, params) => {
  const baseurl = url ? url.split('#')[0] : 'https://mock-storage.local/placeholder.jpg';
  const queryParts = [];
  if (params.assigned_to) queryParts.push(`assigned_to=${encodeURIComponent(params.assigned_to)}`);
  if (params.weight !== undefined && params.weight !== null) queryParts.push(`weight=${params.weight}`);
  if (params.bags !== undefined && params.bags !== null) queryParts.push(`bags=${params.bags}`);
  if (params.is_mistake) queryParts.push(`is_mistake=true`);
  return queryParts.length > 0 ? `${baseurl}#${queryParts.join('&')}` : baseurl;
};

export const calculatePatrollerStats = (pins, missions, volunteerName) => {
  let completedPoints = 0;
  let mistakesFlagged = 0;
  
  pins.forEach(pin => {
    if (pin && pin.status === 'cleaned') {
      const parsed = parsePinParams(pin);
      if (parsed.assigned_to === volunteerName) {
        if (parsed.is_mistake) {
          mistakesFlagged += 1;
        } else {
          completedPoints += 1;
        }
      }
    }
  });

  // Calculate completed missions (where all pins in that mission are resolved/cleaned)
  let missionsDone = 0;
  missions.forEach(mission => {
    const missionPins = pins.filter(p => p && p.mission_id === mission.id);
    if (missionPins.length > 0) {
      const allCleaned = missionPins.every(p => p.status === 'cleaned');
      const participated = missionPins.some(p => {
        const parsed = parsePinParams(p);
        return parsed.assigned_to === volunteerName;
      });
      if (allCleaned && participated) {
        missionsDone += 1;
      }
    }
  });

  return { completedPoints, mistakesFlagged, missionsDone };
};

export const BADGE_DEFS = [
  { id: 'litter_scout', title: 'Litter Scout', desc: 'Resolved first litter detection point', icon: '🔍', color: '#00fbfb' },
  { id: 'ocean_sentinel', title: 'Ocean Sentinel', desc: 'Resolved 5+ litter detection points', icon: '🛡️', color: '#00dddd' },
  { id: 'abyssal_vanguard', title: 'Abyssal Vanguard', desc: 'Resolved 10+ litter detection points', icon: '🔱', color: '#007070' },
  
  { id: 'sharp_eye', title: 'Sharp Eye', desc: 'Reported first false detection (mistake)', icon: '👁️', color: '#e3b5ff' },
  { id: 'yolo_auditor', title: 'YOLO Auditor', desc: 'Reported 3+ false detections', icon: '🤖', color: '#6e00ab' },
  
  { id: 'initiate_patroller', title: 'Initiate Patroller', desc: 'Completed first beach cleanup mission', icon: '🎖️', color: '#10B981' },
  { id: 'mission_commander', title: 'Mission Commander', desc: 'Completed 3+ beach cleanup missions', icon: '👑', color: '#053900' }
];

export const getUnlockedBadges = (stats) => {
  const unlocked = [];
  const { completedPoints, mistakesFlagged, missionsDone } = stats;

  if (completedPoints >= 1) unlocked.push('litter_scout');
  if (completedPoints >= 5) unlocked.push('ocean_sentinel');
  if (completedPoints >= 10) unlocked.push('abyssal_vanguard');

  if (mistakesFlagged >= 1) unlocked.push('sharp_eye');
  if (mistakesFlagged >= 3) unlocked.push('yolo_auditor');

  if (missionsDone >= 1) unlocked.push('initiate_patroller');
  if (missionsDone >= 3) unlocked.push('mission_commander');

  return BADGE_DEFS.filter(b => unlocked.includes(b.id));
};
