import os
import re
import json
import httpx
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Dict, Any

# Load environment variables
dotenv_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

def preprocess_incident_text(text: str) -> str:
    """
    Generic text preprocessing to improve LLM parsing success.
    Focuses on basic normalization and structure enhancement.
    """
    
    # 1. Basic text cleaning
    processed_text = _basic_text_cleaning(text)
    
    # 2. Add missing time context for relative dates
    processed_text = _add_missing_time_context(processed_text)
    
    # 3. Add current date reference for relative dates
    processed_text = _add_date_reference(processed_text)
    
    return processed_text


def _basic_text_cleaning(text: str) -> str:
    """Basic text normalization"""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Normalize punctuation
    text = re.sub(r'\s*,\s*', ', ', text)
    text = re.sub(r'\s*\.\s*', '. ', text)
    
    # Ensure proper sentence ending
    if not text.endswith('.'):
        text += '.'
    
    return text


def _add_missing_time_context(text: str) -> str:
    """Add generic time when relative date has no specific time"""
    
    relative_dates = ['ontem', 'hoje', 'anteontem']
    time_patterns = [r'\d{1,2}h', r'\d{1,2}:\d{2}', r'às \d+', r'pela manhã', r'à tarde', r'à noite']
    
    # Check if text has relative date but no time indicators
    has_relative_date = any(re.search(rf'\b{date}\b', text, re.IGNORECASE) for date in relative_dates)
    has_time_info = any(re.search(pattern, text, re.IGNORECASE) for pattern in time_patterns)
    
    if has_relative_date and not has_time_info:
        # Add generic time context
        text = text + " (horário não especificado)"
    
    return text


def _add_date_reference(text: str) -> str:
    """Add current date context for better relative date processing"""
    
    relative_date_words = ['ontem', 'hoje', 'anteontem']
    
    # Only add if relative dates are present
    if any(word in text.lower() for word in relative_date_words):
        current_date = datetime.now().strftime("%Y-%m-%d")
        text = f"{text} [Referência: {current_date}]"
    
    return text

async def parse_incident_structure(
    incident_description: str,
    ollama_url: str = None,
    model: str = "tinyllama"
) -> Dict[str, Any]:
    """
    Parse an incident description and return it in structured format.
    Uses LLM to extract: data_ocorrencia, local, tipo_incidente, impacto
    """
    try:
        if not ollama_url:
            ollama_url = os.getenv("OLLAMA_URL", "http://172.29.80.1:11434")
        
        processed_text = preprocess_incident_text(incident_description)

        # Get current date for context
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        # Structured parsing prompt
        parsing_prompt = f"""Extract incident information from the following description and return ONLY a valid JSON object with these exact fields:

- data_ocorrencia: Date and time in YYYY-MM-DD HH:MM format (if only date mentioned, use 00:00 for time. If relative time like "ontem" (yesterday), "hoje" (today), calculate based on current date {current_date})
- local: Location where incident occurred
- tipo_incidente: Type/category of incident 
- impacto: Impact description including duration and affected systems

Description: "{processed_text}"

Return ONLY the JSON object, no other text:"""
        
        # Call Ollama
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": parsing_prompt,
                    "stream": False
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                llm_response = response.json().get('response', '').strip()
                
                try:
                    # Try to parse the JSON response
                    parsed_json = json.loads(llm_response)
                    
                    # Validate required fields
                    required_fields = ["data_ocorrencia", "local", "tipo_incidente", "impacto"]
                    for field in required_fields:
                        if field not in parsed_json:
                            parsed_json[field] = "N/A"
                    
                    return {
                        "status": "success",
                        "incident": parsed_json
                    }
                    
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract manually
                    return _fallback_incident_parsing(incident_description)
            else:
                return _fallback_incident_parsing(incident_description)
                
    except Exception as e:
        return _fallback_incident_parsing(incident_description, error=str(e))


def _extract_date_info(text: str) -> str:
    """Extract date information from text with Portuguese support"""
    text_lower = text.lower()
    current_date = datetime.now()
    
    # Check for relative dates
    if "ontem" in text_lower or "yesterday" in text_lower:
        target_date = current_date - timedelta(days=1)
    elif "hoje" in text_lower or "today" in text_lower:
        target_date = current_date
    elif "anteontem" in text_lower:
        target_date = current_date - timedelta(days=2)
    else:
        target_date = current_date
    
    # Try to extract time
    time_patterns = [
        r'(\d{1,2})h(\d{2})?',  # 14h, 14h30
        r'(\d{1,2}):(\d{2})',   # 14:00
        r'às (\d{1,2})',        # às 14
    ]
    
    hour = 0
    minute = 0
    
    for pattern in time_patterns:
        match = re.search(pattern, text_lower)
        if match:
            hour = int(match.group(1))
            if len(match.groups()) > 1 and match.group(2):
                minute = int(match.group(2))
            break
    
    return target_date.replace(hour=hour, minute=minute).strftime("%Y-%m-%d %H:%M")


def _extract_location(text: str) -> str:
    """Extract location from text"""
    location_patterns = [
        r'(?:no|na|em|do|da)\s+(?:escritório|filial|sede|unidade)\s+(?:de|do|da)?\s*([^,\.\s]+)',
        r'(?:em|na|no)\s+([A-Z][a-záêçõ\s]+?)(?:\s*,|\s*\.|\s*que|\s*houve)',
        r'local[:\s]+([^,\.]+)',
    ]
    
    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if len(match.groups()) > 1:
                return match.group(2).strip()
            else:
                return match.group(1).strip()
    
    return "N/A"


def _extract_incident_type(text: str) -> str:
    """Extract incident type from text"""
    type_patterns = [
        r'(falha\s+(?:no|na|do|da)\s+[^,\.]+)',
        r'(erro\s+(?:no|na|do|da)\s+[^,\.]+)',
        r'(problema\s+(?:no|na|do|da)\s+[^,\.]+)',
        r'(interrupção\s+(?:no|na|do|da)\s+[^,\.]+)',
        r'(pane\s+(?:no|na|do|da)\s+[^,\.]+)',
    ]
    
    for pattern in type_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().capitalize()
    
    return "Incidente não especificado"


def _extract_impact(text: str) -> str:
    """Extract impact from text"""
    impact_patterns = [
        r'(afetou\s+[^,\.]+(?:\s+por\s+[^,\.]+)?)',
        r'(indisponível\s+por\s+[^,\.]+)',
        r'(duração\s+de\s+[^,\.]+)',
        r'(por\s+\d+\s+(?:horas?|minutos?|dias?))',
        r'(ficou\s+[^,\.]+\s+por\s+[^,\.]+)',
    ]
    
    for pattern in impact_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # If no specific impact found, return truncated description
    return text[:100] + "..." if len(text) > 100 else text


def _fallback_incident_parsing(incident_description: str, error: str = None) -> Dict[str, Any]:
    """Fallback parsing using regex patterns"""
    try:
        # Extract components using regex
        date_occurrence = _extract_date_info(incident_description)
        location = _extract_location(incident_description)
        incident_type = _extract_incident_type(incident_description)
        impact = _extract_impact(incident_description)
        
        return {
            "status": "success",
            "incident": {
                "data_ocorrencia": date_occurrence,
                "local": location,
                "tipo_incidente": incident_type,
                "impacto": impact
            },
            "method": "regex_fallback"
        }
        
    except Exception as e:
        error_message = error or str(e)
        return {
            "status": "error",
            "message": f"Parsing failed: {error_message}",
            "incident": {
                "data_ocorrencia": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "local": "N/A",
                "tipo_incidente": "Erro no processamento",
                "impacto": incident_description[:100] + "..." if len(incident_description) > 100 else incident_description
            }
        }


# Test function for direct testing
async def test_parse_incident_structure():
    """Test the parsing function directly"""
    test_cases = [
        "Ontem às 14h, no escritório de São Paulo, houve uma falha no servidor principal que afetou o sistema de faturamento por 2 horas.",
        "Hoje pela manhã ocorreu um problema na rede da filial Rio de Janeiro que deixou o sistema indisponível por 30 minutos.",
        "Falha no banco de dados em Brasília durou 1 hora e afetou todas as operações.",
        "Sistema offline no datacenter SP por manutenção programada"
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n--- Test {i} ---")
        print(f"Input: {test_case}")
        
        result = await parse_incident_structure(test_case)
        
        if result.get("status") == "success":
            incident = result.get("incident", {})
            print("Output:")
            print(json.dumps(incident, indent=2, ensure_ascii=False))
        else:
            print(f"Error: {result.get('message', 'Unknown error')}")
        
        print("-" * 50)


# Simple tool registry for compatibility
simple_tools = {
    'parse_incident_structure': parse_incident_structure
}

incident_tool_functions = [
    parse_incident_structure
]

if __name__ == "__main__":
    # Run tests
    asyncio.run(test_parse_incident_structure())