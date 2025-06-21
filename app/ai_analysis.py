import asyncio
import os
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import dateparser
import spacy
import cv2
import numpy as np
from PIL import Image
import pytesseract
from vosk import Model, KaldiRecognizer
import wave
import json
import pytz

# Load spaCy model for NLP
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # If model not found, download it
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

# Initialize Vosk model for speech recognition
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"
if not os.path.exists(VOSK_MODEL_PATH):
    print(f"Vosk model not found at {VOSK_MODEL_PATH}")
    print("Please download the model from https://alphacephei.com/vosk/models")
    vosk_model = None
else:
    vosk_model = Model(VOSK_MODEL_PATH)

# Date and time patterns
DATE_PATTERNS = [
    r'\b(today|tomorrow|yesterday)\b',
    r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b',
    r'\b(january|february|march|april|may|june|july|august|september|october|november|december)\b',
    r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b',
    r'\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
    r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b'
]

TIME_PATTERNS = [
    r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b',
    r'\b(\d{1,2})\s*(am|pm)\b',
    r'\b(morning|afternoon|evening|night|noon|midnight)\b',
    r'\b(in\s+\d+\s+(minutes?|hours?|days?|weeks?))\b'
]

async def analyze_voice_input(audio_file_path: str) -> Dict[str, Any]:
    """Analyze voice input using Vosk speech recognition"""
    if not vosk_model:
        return {"text": "", "confidence": 0.0, "error": "Vosk model not available"}
    
    try:
        # Open audio file
        wf = wave.open(audio_file_path, "rb")
        
        # Create recognizer
        rec = KaldiRecognizer(vosk_model, wf.getframerate())
        rec.SetWords(True)
        
        # Process audio
        text = ""
        confidence = 0.0
        word_count = 0
        
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    text += " " + result["text"]
                if result.get("result"):
                    for word_info in result["result"]:
                        confidence += word_info.get("conf", 0.0)
                        word_count += 1
        
        # Get final result
        final_result = json.loads(rec.FinalResult())
        if final_result.get("text"):
            text += " " + final_result["text"]
        if final_result.get("result"):
            for word_info in final_result["result"]:
                confidence += word_info.get("conf", 0.0)
                word_count += 1
        
        wf.close()
        
        # Calculate average confidence
        avg_confidence = confidence / word_count if word_count > 0 else 0.0
        
        return {
            "text": text.strip(),
            "confidence": avg_confidence
        }
    
    except Exception as e:
        return {"text": "", "confidence": 0.0, "error": str(e)}

async def analyze_text_input(text: str) -> Dict[str, Any]:
    """Analyze text input using spaCy NLP"""
    try:
        # Process text with spaCy
        doc = nlp(text.lower())
        
        # Extract entities
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char
            })
        
        # Extract key phrases
        key_phrases = []
        for chunk in doc.noun_chunks:
            key_phrases.append(chunk.text)
        
        # Sentiment analysis (simple approach)
        positive_words = ["important", "urgent", "critical", "essential", "vital"]
        negative_words = ["maybe", "perhaps", "sometime", "later"]
        
        sentiment_score = 0
        for token in doc:
            if token.text in positive_words:
                sentiment_score += 1
            elif token.text in negative_words:
                sentiment_score -= 1
        
        return {
            "entities": entities,
            "key_phrases": key_phrases,
            "sentiment_score": sentiment_score,
            "word_count": len(doc),
            "processed_text": text
        }
    
    except Exception as e:
        return {"error": str(e)}

async def analyze_image_input(image_file_path: str) -> Dict[str, Any]:
    """Analyze image input using Tesseract OCR and OpenCV"""
    try:
        # Read image with OpenCV
        image = cv2.imread(image_file_path)
        if image is None:
            return {"text": "", "confidence": 0.0, "error": "Could not read image"}
        
        # Preprocess image for better OCR
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding to get binary image
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Apply morphological operations to remove noise
        kernel = np.ones((1, 1), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # OCR with Tesseract
        try:
            text = pytesseract.image_to_string(binary)
            confidence = pytesseract.image_to_data(binary, output_type=pytesseract.Output.DICT)
            
            # Calculate average confidence
            conf_values = [int(x) for x in confidence['conf'] if int(x) > 0]
            avg_confidence = sum(conf_values) / len(conf_values) if conf_values else 0.0
            
            return {
                "text": text.strip(),
                "confidence": avg_confidence / 100.0  # Normalize to 0-1
            }
        except Exception as ocr_error:
            return {"text": "", "confidence": 0.0, "error": f"OCR failed: {str(ocr_error)}"}
    
    except Exception as e:
        return {"text": "", "confidence": 0.0, "error": str(e)}

async def extract_scheduling_info(text: str, user_timezone: str = None) -> Dict[str, Any]:
    """Extract scheduling information from text using NLP and pattern matching"""
    try:
        text_lower = text.lower()
        # Try to get user's timezone from frontend, else use local
        tz = None
        if user_timezone:
            try:
                tz = pytz.timezone(user_timezone)
            except Exception:
                tz = None
        if not tz:
            tz = datetime.now().astimezone().tzinfo
        now = datetime.now(tz)
        
        # Initialize scheduling info
        scheduling_info = {
            "detected_date": None,
            "detected_time": None,
            "confidence": 0.0,
            "extracted_text": text,
            "suggested_title": None
        }
        
        # Extract dates using dateparser
        date_entities = []
        for match in re.finditer(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', text):
            try:
                parsed_date = dateparser.parse(match.group())
                if parsed_date:
                    date_entities.append({
                        "text": match.group(),
                        "date": parsed_date,
                        "start": match.start(),
                        "end": match.end()
                    })
            except:
                continue
        
        # More robust fuzzy matching for 'tomorrow' and common misspellings
        tomorrow_variants = [
            'tomorrow', 'tommorow', 'tomorow', 'tomoroww', 'tommorrow', 'tmrw', 'tmr', 'tmrw.', 'tmr.', 'tmorrow'
        ]
        relative_date_patterns = {
            "today": now,
            **{variant: now + timedelta(days=1) for variant in tomorrow_variants},
            "yesterday": now - timedelta(days=1),
            "yesturday": now - timedelta(days=1),
            "next week": now + timedelta(weeks=1),
            "next month": now + timedelta(days=30)
        }
        
        # Use regex to match whole words with common misspellings
        for pattern, date in relative_date_patterns.items():
            pattern_regex = r'\b' + re.escape(pattern) + r'\b'
            if re.search(pattern_regex, text_lower):
                date_entities.append({
                    "text": pattern,
                    "date": date,
                    "start": text_lower.find(pattern),
                    "end": text_lower.find(pattern) + len(pattern)
                })
        
        # Extract times
        time_entities = []
        time_patterns = [
            r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b',
            r'\b(\d{1,2})\s*(am|pm)\b',
            r'\b(morning|afternoon|evening|night|noon|midnight)\b'
        ]
        
        for pattern in time_patterns:
            for match in re.finditer(pattern, text_lower):
                time_entities.append({
                    "text": match.group(),
                    "start": match.start(),
                    "end": match.end()
                })
        
        # Combine date and time
        if date_entities:
            scheduling_info["detected_date"] = date_entities[0]["date"]
            scheduling_info["confidence"] += 0.5
        
        if time_entities:
            scheduling_info["detected_time"] = time_entities[0]["text"]
            scheduling_info["confidence"] += 0.3
        
        # Generate suggested title
        doc = nlp(text)
        nouns = [token.text for token in doc if token.pos_ in ["NOUN", "PROPN"]]
        if nouns:
            scheduling_info["suggested_title"] = " ".join(nouns[:3])
        
        # Increase confidence if we found both date and time
        if scheduling_info["detected_date"] and scheduling_info["detected_time"]:
            scheduling_info["confidence"] = min(1.0, scheduling_info["confidence"] + 0.2)
        
        # Extract entities
        entities = {
            "dates": [],
            "times": [],
            "people": [ent.text for ent in doc.ents if ent.label_ == "PERSON"],
            "places": [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]
        }
        
        # Combine entities into title
        title_parts = []
        if scheduling_info["suggested_title"]:
            title_parts.append(scheduling_info["suggested_title"])
        if entities["people"]:
            title_parts.append(f"with {', '.join(entities['people'])}")
        if entities["places"]:
            title_parts.append(f"at {', '.join(entities['places'])}")
        
        final_title = " ".join(title_parts) if title_parts else "Reminder"
        
        print('DEBUG scheduling_info:', scheduling_info)
        return {
            "suggested_title": final_title,
            "detected_date": scheduling_info["detected_date"],
            "detected_time": scheduling_info["detected_time"],
            "confidence": scheduling_info["confidence"],
            "entities": entities
        }
    
    except Exception as e:
        return {
            "detected_date": None,
            "detected_time": None,
            "confidence": 0.0,
            "extracted_text": text,
            "suggested_title": None,
            "error": str(e)
        } 