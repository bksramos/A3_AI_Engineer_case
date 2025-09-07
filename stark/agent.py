import os
import sys
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.getenv("DOTENV"))

# Add paths
sys.path.append(os.getenv("CARTER"))
sys.path.append(os.getenv("TOOLS"))

# Import only the parsing tool
from incident_tools import parse_incident_structure

# Import simplified instructions
try:
    from instructions import (
        get_system_prompt,
        should_parse_incident,
        extract_parsing_text,
        format_json_response,
        get_error_response,
        is_valid_incident_description
    )
    INSTRUCTIONS_AVAILABLE = True
except ImportError:
    print("Warning: instructions.py not found. Using basic parsing.")
    INSTRUCTIONS_AVAILABLE = False


class SimpleParsingToolset:
    """Simple toolset that only handles incident parsing"""
    
    def __init__(self):
        self.tool_mapping = {
            'parse_incident_structure': parse_incident_structure
        }
        print("Simple Parsing Toolset initialized")
    
    async def parse_incident_structure(self, incident_description: str, ollama_url: str = None, model: str = "tinyllama"):
        """Parse incident into structured format"""
        return await parse_incident_structure(
            incident_description=incident_description,
            ollama_url=ollama_url,
            model=model
        )
    
    async def close(self):
        """No resources to cleanup in simple version"""
        pass


class SimpleParserAgent:
    """Simple agent that only parses incidents to JSON"""
    
    def __init__(self, name: str = "IncidentParser", model: str = "tinyllama"):
        self.name = name
        self.model = model
        self.tools = SimpleParsingToolset()
        self.ollama_url = os.getenv("OLLAMA_URL", "http://172.29.80.1:11434")
        
        print(f"Simple Parser Agent '{name}' initialized")
        print(f"Model: {model}")
        print("Ready to parse incidents to JSON")
    
    async def process_message(self, message: str) -> str:
        """Process message and return JSON if it's an incident description"""
        try:
            # Extract the actual incident text to parse
            if INSTRUCTIONS_AVAILABLE:
                # Use instructions to determine if we should parse
                if should_parse_incident(message) or is_valid_incident_description(message):
                    incident_text = extract_parsing_text(message)
                else:
                    return self._get_help_message()
            else:
                # Fallback: always try to parse if it looks like an incident
                if any(keyword in message.lower() for keyword in 
                       ['falha', 'erro', 'problema', 'incidente', 'servidor', 'rede', 'sistema']):
                    incident_text = message
                    if message.startswith('Parse:'):
                        incident_text = message[6:].strip()
                else:
                    return self._get_help_message()
            
            # Parse the incident
            result = await self.tools.parse_incident_structure(
                incident_description=incident_text,
                ollama_url=self.ollama_url,
                model=self.model
            )
            
            if result.get("status") == "success":
                incident_data = result.get("incident", {})
                
                # Return only JSON format
                if INSTRUCTIONS_AVAILABLE:
                    return format_json_response(incident_data)
                else:
                    return json.dumps(incident_data, indent=2, ensure_ascii=False)
            else:
                error_msg = result.get("message", "Unknown parsing error")
                if INSTRUCTIONS_AVAILABLE:
                    return get_error_response(error_msg)
                else:
                    return json.dumps({
                        "data_ocorrencia": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "local": "N/A",
                        "tipo_incidente": "Erro no processamento",
                        "impacto": f"Erro: {error_msg}"
                    }, indent=2, ensure_ascii=False)
                    
        except Exception as e:
            error_msg = f"Processing error: {str(e)}"
            if INSTRUCTIONS_AVAILABLE:
                return get_error_response(error_msg)
            else:
                return json.dumps({
                    "data_ocorrencia": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "local": "N/A", 
                    "tipo_incidente": "Erro no processamento",
                    "impacto": error_msg
                }, indent=2, ensure_ascii=False)
    
    def _get_help_message(self) -> str:
        """Return help message for invalid input"""
        help_msg = {
            "message": "Please provide an incident description to parse",
            "examples": [
                "Parse: Ontem às 14h houve falha no servidor de São Paulo",
                "Falha na rede durou 2 horas no escritório RJ",
                "Sistema de banco indisponível por 30 minutos"
            ],
            "expected_output": {
                "data_ocorrencia": "YYYY-MM-DD HH:MM",
                "local": "Location",
                "tipo_incidente": "Incident type",
                "impacto": "Impact description"
            }
        }
        return json.dumps(help_msg, indent=2, ensure_ascii=False)
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.tools.close()


class SimpleRunner:
    """Runner for the simple parser agent"""
    
    def __init__(self, agent: SimpleParserAgent):
        self.agent = agent
    
    async def run_interactive(self):
        """Run interactive parsing session"""
        print(f"Starting {self.agent.name}")
        print("Incident Parser - Converts incident descriptions to JSON")
        print("Type 'quit', 'exit', or 'bye' to end")
        print("Examples:")
        print("  Parse: Ontem às 14h houve falha no servidor")
        print("  Falha na rede durou 2 horas no RJ")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\nIncident: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye', 'sair']:
                    print(f"Goodbye! {self.agent.name} signing off.")
                    break
                
                if not user_input:
                    continue
                
                # Process and get JSON
                json_output = await self.agent.process_message(user_input)
                print(f"\nJSON Output:\n{json_output}")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
        
        await self.agent.cleanup()
    
    async def process_single(self, incident_text: str) -> str:
        """Process a single incident and return JSON"""
        try:
            return await self.agent.process_message(incident_text)
        finally:
            await self.agent.cleanup()


def create_parser_agent(model: str = "tinyllama") -> SimpleParserAgent:
    """Create a simple parsing agent"""
    print("Creating Simple Incident Parser...")
    
    # Verify Ollama connection
    ollama_url = os.getenv("OLLAMA_URL", "http://172.29.80.1:11434")
    try:
        import httpx
        response = httpx.get(f"{ollama_url}/api/tags", timeout=5.0)
        if response.status_code == 200:
            print("Ollama API is accessible")
        else:
            print(f"Ollama API returned status {response.status_code}")
    except Exception as e:
        print(f"Could not verify Ollama connection: {e}")
    
    return SimpleParserAgent(name="IncidentParser", model=model)


# Test function
async def test_parser_agent():
    """Test the parser agent"""
    agent = create_parser_agent()
    
    test_cases = [
        "Parse: Ontem às 14h, no escritório de São Paulo, houve uma falha no servidor principal que afetou o sistema de faturamento por 2 horas.",
        "Hoje pela manhã ocorreu um problema na rede da filial Rio de Janeiro que deixou o sistema indisponível por 30 minutos.",
        "Falha no banco de dados em Brasília durou 1 hora e afetou todas as operações.",
        "Hello world"  # Should return help message
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case}")
        result = await agent.process_message(test_case)
        print(f"Result:\n{result}")
        print("-" * 50)
    
    await agent.cleanup()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run tests
        asyncio.run(test_parser_agent())
    elif len(sys.argv) > 1 and sys.argv[1] == "single":
        # Single incident processing
        if len(sys.argv) < 3:
            print("Usage: python agent.py single 'incident description'")
            sys.exit(1)
        
        incident = sys.argv[2]
        agent = create_parser_agent()
        runner = SimpleRunner(agent)
        result = asyncio.run(runner.process_single(incident))
        print(result)
    else:
        # Interactive mode
        agent = create_parser_agent()
        runner = SimpleRunner(agent)
        asyncio.run(runner.run_interactive())