import os
import sys
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add paths for our modules
sys.path.append(os.getenv("CARTER", "."))
sys.path.append(os.getenv("TOOLS", "."))

from agent import create_parser_agent

# Configurações da API
ALLOWED_ORIGINS = ["*"]
PORT = int(os.environ.get("PORT", 8080))

# Initialize FastAPI app
app = FastAPI(
    title="Incident Parser API",
    description="Simple API to parse incident descriptions into structured JSON",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
parser_agent = None

# Pydantic models for request/response
class IncidentRequest(BaseModel):
    description: str
    model: Optional[str] = "tinyllama"

class IncidentResponse(BaseModel):
    status: str
    incident: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    message: str
    ollama_status: str

@app.on_event("startup")
async def startup_event():
    """Initialize the parser agent on startup"""
    global parser_agent
    try:
        print("Initializing Incident Parser Agent...")
        parser_agent = create_parser_agent()
        print("Agent initialized successfully")
    except Exception as e:
        print(f"Failed to initialize agent: {e}")
        raise e

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global parser_agent
    if parser_agent:
        try:
            await parser_agent.cleanup()
            print("Agent cleanup completed")
        except Exception as e:
            print(f"Error during cleanup: {e}")

@app.get("/")
async def read_root():
    """Redirect root to API docs"""
    return RedirectResponse(url="/docs")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    try:
        # Check Ollama connectivity
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://172.29.80.1:11434")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_url}/api/tags", timeout=5.0)
            ollama_status = "connected" if response.status_code == 200 else "error"
        
        return HealthResponse(
            status="healthy",
            message="Incident Parser API is running",
            ollama_status=ollama_status
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            message=f"Health check failed: {str(e)}",
            ollama_status="error"
        )

@app.post("/parse", response_model=IncidentResponse)
async def parse_incident(request: IncidentRequest):
    """
    Parse an incident description into structured JSON
    
    Args:
        request: IncidentRequest with description and optional model
        
    Returns:
        IncidentResponse with parsed incident data or error
    """
    global parser_agent
    
    if not parser_agent:
        raise HTTPException(status_code=500, detail="Parser agent not initialized")
    
    if not request.description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty")
    
    try:
        # Process the incident description
        result = await parser_agent.process_message(request.description)
        
        # Try to parse the JSON response
        import json
        try:
            parsed_incident = json.loads(result)
            
            # Check if it's a valid incident response or help message
            if "data_ocorrencia" in parsed_incident:
                return IncidentResponse(
                    status="success",
                    incident=parsed_incident
                )
            else:
                # It's probably a help message or error
                return IncidentResponse(
                    status="error",
                    error="Invalid incident description. Please provide a clear incident description."
                )
                
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw response as error
            return IncidentResponse(
                status="error",
                error=f"Failed to parse response: {result}"
            )
            
    except Exception as e:
        return IncidentResponse(
            status="error",
            error=f"Processing failed: {str(e)}"
        )

@app.post("/parse/batch")
async def parse_batch_incidents(requests: list[IncidentRequest]):
    """
    Parse multiple incident descriptions
    
    Args:
        requests: List of IncidentRequest objects
        
    Returns:
        List of IncidentResponse objects
    """
    global parser_agent
    
    if not parser_agent:
        raise HTTPException(status_code=500, detail="Parser agent not initialized")
    
    if len(requests) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 incidents per batch")
    
    results = []
    
    for i, request in enumerate(requests):
        try:
            # Reuse the single parse logic
            response = await parse_incident(request)
            results.append(response)
        except Exception as e:
            results.append(IncidentResponse(
                status="error",
                error=f"Failed to process incident {i+1}: {str(e)}"
            ))
    
    return results

@app.get("/models")
async def get_available_models():
    """Get available Ollama models"""
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_URL", "http://172.29.80.1:11434")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_url}/api/tags", timeout=10.0)
            
            if response.status_code == 200:
                models_data = response.json()
                models = [model["name"] for model in models_data.get("models", [])]
                return {"status": "success", "models": models}
            else:
                return {"status": "error", "message": "Could not fetch models from Ollama"}
                
    except Exception as e:
        return {"status": "error", "message": f"Error connecting to Ollama: {str(e)}"}

@app.get("/examples")
async def get_examples():
    """Get example incident descriptions and expected outputs"""
    examples = [
        {
            "input": "Ontem às 14h, no escritório de São Paulo, houve uma falha no servidor principal que afetou o sistema de faturamento por 2 horas.",
            "expected_output": {
                "data_ocorrencia": "2025-09-06 14:00",
                "local": "São Paulo",
                "tipo_incidente": "Falha no servidor principal",
                "impacto": "afetou o sistema de faturamento por 2 horas"
            }
        },
        {
            "input": "Hoje pela manhã ocorreu um problema na rede da filial Rio de Janeiro que deixou o sistema indisponível por 30 minutos.",
            "expected_output": {
                "data_ocorrencia": "2025-09-07 08:00",
                "local": "Rio de Janeiro",
                "tipo_incidente": "Problema na rede",
                "impacto": "sistema indisponível por 30 minutos"
            }
        },
        {
            "input": "Falha no banco de dados em Brasília durou 1 hora e afetou todas as operações.",
            "expected_output": {
                "data_ocorrencia": "2025-09-07 00:00",
                "local": "Brasília",
                "tipo_incidente": "Falha no banco de dados",
                "impacto": "durou 1 hora e afetou todas as operações"
            }
        }
    ]
    
    return {"examples": examples}

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=PORT,
        log_level="info"
    )