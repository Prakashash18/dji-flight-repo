import httpx
from config import settings

class SeaLionClient:
    """
    Client for interacting with the SEA-LION Large Language Model API
    to translate beach cleanup alerts into various Southeast Asian languages.
    """
    def __init__(self):
        self.api_key = settings.SEA_LION_API_KEY
        self.api_url = settings.SEA_LION_API_URL
        
        # Local mock translation table for fallback when API key is missing/invalid
        self._mock_translations = {
            "th": {
                "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
                    "ประกาศทำความสะอาดชายหาด! พบขยะหนาแน่น กรุณาตรวจสอบแผนที่เพื่อดูเขตพื้นที่ที่ได้รับมอบหมาย",
                "New litter detected nearby. Assist if you are in the area.":
                    "พบขยะใหม่ในบริเวณใกล้เคียง โปรดช่วยเหลือหากคุณอยู่ในพื้นที่"
            },
            "id": {
                "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
                    "Peringatan Pembersihan Pantai! Terdeteksi konsentrasi sampah yang tinggi. Harap periksa peta Anda untuk pembagian zona.",
                "New litter detected nearby. Assist if you are in the area.":
                    "Sampah baru terdeteksi di dekat Anda. Bantu jika Anda berada di area tersebut."
            },
            "tl": {
                "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
                    "Babala sa Paglilinis ng Baybayin! Mataas na konsentrasyon ng basura ang natukoy. Pakisuri ang iyong mapa para sa mga nakatalagang zone.",
                "New litter detected nearby. Assist if you are in the area.":
                    "May bagong basura na natukoy malapit sa iyo. Tumulong kung ikaw ay nasa lugar."
            },
            "ms": {
                "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.": 
                    "Amaran Pembersihan Pantai! Sampah sarap dikesan dalam konsentrasi tinggi. Sila semak peta anda untuk tugasan zon.",
                "New litter detected nearby. Assist if you are in the area.":
                    "Sampah baru dikesan berhampiran. Sila bantu jika anda berada di kawasan tersebut."
            },
            "ta": {
                "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments.":
                    "கடற்கரை தூய்மைப்படுத்தல் எச்சரிக்கை! அதிக அளவு குப்பை கண்டறியப்பட்டுள்ளது. மண்டல ஒதுக்கீடுகளுக்கு உங்கள் வரைபடத்தை சரிபார்க்கவும்.",
                "New litter detected nearby. Assist if you are in the area.":
                    "அருகில் புதிய குப்பை கண்டறியப்பட்டுள்ளது. நீங்கள் இப்பகுதியில் இருந்தால் உதவவும்."
            }
        }

    async def translate_text(self, text: str, target_lang: str) -> str:
        """
        Translates text into the target language using SEA-LION.
        Falls back to static mock translations if no API key is set.
        """
        target_lang = target_lang.lower().strip()
        if target_lang == "en":
            return text
            
        if not self.api_key:
            return self._get_mock_translation(text, target_lang)
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # SEA-LION LLM Prompt instructing exact translation
        prompt = (
            f"You are a professional translator. Translate the following English text into the language with code '{target_lang}'. "
            f"Respond ONLY with the direct translation. Do not include quotes, explanations, or introductory text.\n\n"
            f"English text: \"{text}\"\n"
            f"Translation:"
        )
        
        payload = {
            "model": "aisingapore/Gemma-SEA-LION-v4-27B-IT",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 200
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=12.0
                )
                
                if response.status_code == 200:
                    res_json = response.json()
                    translation = res_json['choices'][0]['message']['content'].strip()
                    # Clean up enclosing quotes if LLM returned them
                    if translation.startswith('"') and translation.endswith('"'):
                        translation = translation[1:-1]
                    return translation
                else:
                    print(f"⚠️ SEA-LION API error (Status {response.status_code}): {response.text}")
                    return self._get_mock_translation(text, target_lang)
                    
        except Exception as e:
            print(f"⚠️ SEA-LION request exception: {e}")
            return self._get_mock_translation(text, target_lang)

    def _get_mock_translation(self, text: str, lang: str) -> str:
        """
        Helper method to retrieve mock translations.
        """
        # Strip whitespaces and clean
        text_clean = text.strip()
        
        # Lookup in dictionary
        lang_dict = self._mock_translations.get(lang, {})
        if text_clean in lang_dict:
            return lang_dict[text_clean]
            
        # Generic mock response if specific text doesn't exist
        fallback_phrases = {
            "th": f"[ภาษาไทย] {text_clean}",
            "id": f"[Bahasa Indonesia] {text_clean}",
            "tl": f"[Tagalog] {text_clean}",
            "ms": f"[Bahasa Melayu] {text_clean}",
            "ta": f"[தமிழ்] {text_clean}"
        }
        return fallback_phrases.get(lang, f"[{lang.upper()}] {text_clean}")

# Dry run testing
if __name__ == '__main__':
    import asyncio
    
    async def test():
        client = SeaLionClient()
        alert = "Beach Cleanup Alert! High concentration of litter detected. Please check your map for zone assignments."
        
        print("Testing mock translations:")
        for lang in ['th', 'id', 'tl', 'ta', 'ja']:
            translation = await client.translate_text(alert, lang)
            print(f"  {lang} -> {translation}")
            
    asyncio.run(test())
