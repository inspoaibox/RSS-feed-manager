"""Google Translate service for article translation."""
import httpx
from typing import Optional


class GoogleTranslateError(Exception):
    """Exception raised when Google Translate operation fails."""
    pass


class GoogleTranslateService:
    """Service for translating text using Google Translate API."""
    
    # 语言代码映射
    LANGUAGE_MAP = {
        'zh-CN': 'zh-CN',
        'zh-TW': 'zh-TW', 
        'en': 'en',
        'ja': 'ja',
        'ko': 'ko',
        'fr': 'fr',
        'de': 'de',
        'es': 'es',
        'ru': 'ru',
        'pt': 'pt',
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Google Translate service.
        
        Args:
            api_key: Google Cloud Translation API key. If None, uses free endpoint.
        """
        self.api_key = api_key
        if api_key:
            self.base_url = "https://translation.googleapis.com/language/translate/v2"
        else:
            # 免费的 Google Translate 端点（有请求限制）
            self.base_url = "https://translate.googleapis.com/translate_a/single"
    
    async def translate(self, text: str, target_language: str, source_language: str = 'auto') -> str:
        """
        Translate text to target language.
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'zh-CN', 'en')
            source_language: Source language code, 'auto' for auto-detect
            
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        target_lang = self.LANGUAGE_MAP.get(target_language, target_language)
        
        if self.api_key:
            return await self._translate_with_api(text, target_lang, source_language)
        else:
            return await self._translate_free(text, target_lang, source_language)
    
    async def _translate_with_api(self, text: str, target_lang: str, source_lang: str) -> str:
        """Translate using Google Cloud Translation API (paid)."""
        async with httpx.AsyncClient() as client:
            try:
                params = {
                    'key': self.api_key,
                    'q': text,
                    'target': target_lang,
                }
                if source_lang != 'auto':
                    params['source'] = source_lang
                
                response = await client.post(
                    self.base_url,
                    data=params,
                    timeout=30.0
                )
                response.raise_for_status()
                
                result = response.json()
                translations = result.get('data', {}).get('translations', [])
                if translations:
                    return translations[0].get('translatedText', text)
                return text
                
            except httpx.HTTPStatusError as e:
                raise GoogleTranslateError(f"API error: {e.response.status_code} - {e.response.text}")
            except httpx.RequestError as e:
                raise GoogleTranslateError(f"Request error: {str(e)}")
    
    async def _translate_free(self, text: str, target_lang: str, source_lang: str) -> str:
        """Translate using free Google Translate endpoint (rate limited)."""
        async with httpx.AsyncClient() as client:
            try:
                # 分割长文本（免费端点有长度限制）
                max_length = 5000
                if len(text) > max_length:
                    # 分段翻译
                    parts = self._split_text(text, max_length)
                    translated_parts = []
                    for part in parts:
                        translated = await self._translate_single_free(client, part, target_lang, source_lang)
                        translated_parts.append(translated)
                    return ''.join(translated_parts)
                else:
                    return await self._translate_single_free(client, text, target_lang, source_lang)
                    
            except httpx.HTTPStatusError as e:
                raise GoogleTranslateError(f"API error: {e.response.status_code}")
            except httpx.RequestError as e:
                raise GoogleTranslateError(f"Request error: {str(e)}")
    
    async def _translate_single_free(self, client: httpx.AsyncClient, text: str, target_lang: str, source_lang: str) -> str:
        """Translate a single piece of text using free endpoint."""
        params = {
            'client': 'gtx',
            'sl': source_lang if source_lang != 'auto' else 'auto',
            'tl': target_lang,
            'dt': 't',
            'q': text,
        }
        
        response = await client.get(
            self.base_url,
            params=params,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=30.0
        )
        response.raise_for_status()
        
        result = response.json()
        
        # 解析响应格式 [[["translated text","original text",...],...],...]
        if result and isinstance(result, list) and result[0]:
            translated_parts = []
            for item in result[0]:
                if item and isinstance(item, list) and item[0]:
                    translated_parts.append(item[0])
            return ''.join(translated_parts)
        
        return text
    
    def _split_text(self, text: str, max_length: int) -> list[str]:
        """Split text into chunks, trying to break at sentence boundaries."""
        if len(text) <= max_length:
            return [text]
        
        parts = []
        current = ""
        
        # 尝试按句子分割
        sentences = text.replace('\n', '\n ').split('. ')
        
        for sentence in sentences:
            if len(current) + len(sentence) + 2 <= max_length:
                current += sentence + '. '
            else:
                if current:
                    parts.append(current.strip())
                current = sentence + '. '
        
        if current:
            parts.append(current.strip())
        
        return parts
    
    async def detect_language(self, text: str) -> str:
        """
        Detect the language of the text.
        
        Args:
            text: Text to detect language for
            
        Returns:
            Detected language code
        """
        if self.api_key:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        "https://translation.googleapis.com/language/translate/v2/detect",
                        data={
                            'key': self.api_key,
                            'q': text[:500],  # 只用前500字符检测
                        },
                        timeout=10.0
                    )
                    response.raise_for_status()
                    result = response.json()
                    detections = result.get('data', {}).get('detections', [[]])
                    if detections and detections[0]:
                        return detections[0][0].get('language', 'unknown')
                except Exception:
                    pass
        
        return 'unknown'
    
    async def test_connection(self) -> bool:
        """Test if the translation service is working."""
        try:
            result = await self.translate("Hello", "zh-CN")
            return bool(result and result != "Hello")
        except GoogleTranslateError:
            return False
