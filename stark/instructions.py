import json
from datetime import datetime

"""
Simple agent instructions for incident parsing only
"""

# System prompt for the parsing agent
SYSTEM_PROMPT = """You are a specialized incident parser assistant. Your only function is to convert natural language incident descriptions into structured JSON format.

You extract exactly these four fields:
- data_ocorrencia: Date and time in YYYY-MM-DD HH:MM format
- local: Location where incident occurred  
- tipo_incidente: Type/category of incident
- impacto: Impact description including duration and affected systems

You respond ONLY with valid JSON. No explanations, no analysis, no additional text."""

# Parsing instruction for LLM
PARSING_INSTRUCTION = """Extract incident information from the description and return ONLY a valid JSON object with these exact fields:

- data_ocorrencia: Date and time in YYYY-MM-DD HH:MM format (if relative time like "ontem"=yesterday, "hoje"=today, calculate based on current date)
- local: Location where incident occurred
- tipo_incidente: Type/category of incident 
- impacto: Impact description including duration and affected systems

Return ONLY the JSON object, no other text."""

# Keywords that indicate user wants parsing (simple detection)
PARSING_KEYWORDS = [
    # Portuguese
    'parse', 'estruturar', 'extrair', 'parsear', 'analisar',
    # English  
    'parse', 'structure', 'extract', 'analyze'
]

# Date-related keywords for extraction
DATE_KEYWORDS = {
    'ontem': -1,      # yesterday
    'hoje': 0,        # today
    'anteontem': -2   # day before yesterday
}

# Time patterns for regex extraction
TIME_PATTERNS = [
    r'(\d{1,2})h(\d{2})?',    # 14h, 14h30
    r'(\d{1,2}):(\d{2})',     # 14:00
    r'às (\d{1,2})',          # às 14
    r'(\d{1,2})h',            # 14h
]

# Location patterns for regex extraction
LOCATION_PATTERNS = [
    r'(?:no|na|em|do|da)\s+(?:escritório|filial|sede|unidade)\s+(?:de|do|da)?\s*([^,\.\s]+)',
    r'(?:em|na|no)\s+([A-Z][a-záêçõ\s]+?)(?:\s*,|\s*\.|\s*que|\s*houve)',
    r'local[:\s]+([^,\.]+)',
]

# Incident type patterns for regex extraction  
TYPE_PATTERNS = [
    r'(falha\s+(?:no|na|do|da)\s+[^,\.]+)',
    r'(erro\s+(?:no|na|do|da)\s+[^,\.]+)', 
    r'(problema\s+(?:no|na|do|da)\s+[^,\.]+)',
    r'(interrupção\s+(?:no|na|do|da)\s+[^,\.]+)',
    r'(pane\s+(?:no|na|do|da)\s+[^,\.]+)',
]

# Impact patterns for regex extraction
IMPACT_PATTERNS = [
    r'(afetou\s+[^,\.]+(?:\s+por\s+[^,\.]+)?)',
    r'(indisponível\s+por\s+[^,\.]+)',
    r'(duração\s+de\s+[^,\.]+)',
    r'(por\s+\d+\s+(?:horas?|minutos?|dias?))',
    r'(ficou\s+[^,\.]+\s+por\s+[^,\.]+)',
]

def get_system_prompt() -> str:
    """Get the system prompt for parsing agent"""
    return SYSTEM_PROMPT

def get_parsing_instruction(current_date: str) -> str:
    """Get parsing instruction with current date context"""
    return f"{PARSING_INSTRUCTION}\n\nCurrent date for reference: {current_date}"

def should_parse_incident(message: str) -> bool:
    """Check if message should trigger incident parsing"""
    message_lower = message.lower()
    
    # Always parse if starts with Parse:
    if message.startswith('Parse:'):
        return True
    
    # Check for parsing keywords
    return any(keyword in message_lower for keyword in PARSING_KEYWORDS)

def is_valid_incident_description(message: str) -> bool:
    """Check if message looks like an incident description"""
    message_lower = message.lower()
    
    # Look for incident indicators
    incident_indicators = [
        'falha', 'erro', 'problema', 'incidente', 'pane',
        'indisponível', 'offline', 'parou', 'caiu',
        'failure', 'error', 'issue', 'down', 'crash'
    ]
    
    return any(indicator in message_lower for indicator in incident_indicators)

def extract_parsing_text(message: str) -> str:
    """Extract the actual incident text from parsing commands"""
    # If starts with Parse:, extract everything after it
    if message.startswith('Parse:'):
        return message[6:].strip()
    
    # Try to extract text after parsing keywords
    message_lower = message.lower()
    for keyword in PARSING_KEYWORDS:
        if keyword in message_lower:
            parts = message.lower().split(keyword, 1)
            if len(parts) > 1:
                extracted = parts[1].strip().lstrip(':').strip()
                if extracted:
                    return extracted
    
    # Return original message if no parsing command found
    return message

def format_json_response(incident_data: dict) -> str:
    """Format incident data as clean JSON"""
    return json.dumps(incident_data, indent=2, ensure_ascii=False)

def get_error_response(error_message: str) -> str:
    """Get standardized error response in JSON format"""
    
    error_data = {
        "data_ocorrencia": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "local": "N/A",
        "tipo_incidente": "Erro no processamento",
        "impacto": f"Erro: {error_message}"
    }
    
    return json.dumps(error_data, indent=2, ensure_ascii=False)