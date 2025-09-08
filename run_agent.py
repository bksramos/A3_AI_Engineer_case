import os
import sys
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.getenv("DOTENV"))

# Add paths
sys.path.append(os.getenv("STARK"))
sys.path.append(os.getenv("TOOLS"))

from agent import create_parser_agent, SimpleRunner


async def verify_setup():
    """Verify the setup before starting"""
    print("\nVerifying setup...")
    
    # Check Ollama (only requirement now)
    ollama_url = os.getenv("OLLAMA_URL", "http://172.29.80.1:11434")
    print(f"Checking Ollama at: {ollama_url}")
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ollama_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                print("✅ Ollama API is accessible")
                models = response.json().get('models', [])
                if models:
                    print(f"   Available models: {', '.join([m['name'] for m in models[:3]])}")
            else:
                print(f"⚠️ Ollama API returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Could not connect to Ollama: {e}")
        print("   Make sure Ollama is running: ollama serve")
        return False
    
    # Check instructions file (optional)
    if Path("instructions.py").exists():
        print("✅ Instructions file found: instructions.py")
    else:
        print("⚠️ Instructions file not found - using fallback prompts")
    
    return True


async def main(model: str):
    """Main function to run the parser agent"""
    print("=" * 60)
    print("Simple Incident Parser Agent")
    print("=" * 60)
    
    # Verify setup first
    setup_ok = await verify_setup()
    if not setup_ok:
        print("\n⚠️ Ollama is not properly configured.")
        print("Continue anyway? (y/n): ", end="")
        if input().strip().lower() != 'y':
            print("Exiting...")
            return
    
    print(f"\n--- Incident Description Parser ---")
    print(f"--- Model: {model} ---")
    
    print(f"\nInitializing parser agent...")
    
    # Create the parser agent
    agent = create_parser_agent(model=model)
        
    print(f"Parser agent '{agent.name}' ready!")
    print("-" * 60)

    # Use SimpleRunner for interaction
    runner = SimpleRunner(agent=agent)
    
    try:
        await runner.run_interactive()
    finally:
        # Ensure cleanup
        if hasattr(agent, 'cleanup'):
            await agent.cleanup()


async def run_single_query(model: str, query: str):
    """Run a single query without interactive mode"""
    print(f"Creating parser agent with model {model}...")
    
    # Create agent
    agent = create_parser_agent(model=model)
    
    try:
        print(f"\nParsing incident: {query}")
        response = await agent.process_message(query)
        print(f"\nJSON Output:\n{response}")
    finally:
        await agent.cleanup()


async def run_batch_queries(model: str, queries_file: str):
    """Run multiple queries from a file"""
    try:
        with open(queries_file, 'r', encoding='utf-8') as f:
            queries = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"❌ File not found: {queries_file}")
        return
    
    print(f"Creating parser agent with model {model}...")
    
    # Create agent
    agent = create_parser_agent(model=model)
    
    try:
        print(f"Processing {len(queries)} incident descriptions from {queries_file}")
        print("-" * 60)
        
        for i, query in enumerate(queries, 1):
            print(f"\nIncident {i}: {query}")
            response = await agent.process_message(query)
            print(f"JSON Output:\n{response}")
            print("-" * 40)
    finally:
        await agent.cleanup()


def print_usage_examples():
    """Print usage examples"""
    print("📝 Simple Incident Parser Agent")
    print("\nUsage Examples:")
    print("  Interactive mode:")
    print("    python run_agent.py")
    print("    python run_agent.py --model llama3")
    print()
    print("  Single incident parsing:")
    print("    python run_agent.py --mode query --query 'Ontem às 14h houve falha no servidor'")
    print()
    print("  Batch processing:")
    print("    python run_agent.py --mode batch --file incidents.txt")
    print()
    print("  Test mode:")
    print("    python run_agent.py --mode test")
    print()


async def run_tests(model: str):
    """Run test cases"""
    print(f"Running parser tests with model: {model}")
    
    agent = create_parser_agent(model=model)
    
    test_cases = [
        "Ontem às 14h, no escritório de São Paulo, houve uma falha no servidor principal que afetou o sistema de faturamento por 2 horas.",
        "Hoje pela manhã ocorreu um problema na rede da filial Rio de Janeiro que deixou o sistema indisponível por 30 minutos.",
        "Falha no banco de dados em Brasília durou 1 hora e afetou todas as operações.",
        "Sistema offline no datacenter SP por manutenção programada das 02h às 06h",
        "Hello world"  # Should return help message
    ]
    
    try:
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'='*50}")
            print(f"Test {i}: {test_case}")
            print('='*50)
            
            result = await agent.process_message(test_case)
            print(result)
    finally:
        await agent.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Simple Incident Parser Agent - Converts incident descriptions to structured JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_agent.py                                         # Interactive mode
    python run_agent.py --model llama3                          # With specific model
    python run_agent.py --mode query --query "server failure"   # Single parsing
    python run_agent.py --mode batch --file incidents.txt       # Batch processing
    python run_agent.py --mode test                             # Run test cases
        """
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="tinyllama",
        help="Specify the Ollama model to use (default: tinyllama)"
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        choices=["interactive", "query", "batch", "test"],
        default="interactive",
        help="Run mode: interactive (default), single query, batch processing, or test"
    )
    
    parser.add_argument(
        "--query",
        type=str,
        help="Single incident description to parse (used with --mode query)"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        help="File containing incident descriptions to parse (used with --mode batch)"
    )

    args = parser.parse_args()

    try:
        # Check if no arguments provided
        if len(sys.argv) == 1:
            print_usage_examples()
            print("\nStarting interactive mode...\n")
        
        if args.mode == "interactive":
            asyncio.run(main(model=args.model))
        
        elif args.mode == "query":
            if not args.query:
                print("❌ Error: --query argument required for query mode")
                print("\nExample: python run_agent.py --mode query --query 'Falha no servidor ontem'")
                sys.exit(1)
            asyncio.run(run_single_query(args.model, args.query))
        
        elif args.mode == "batch":
            if not args.file:
                print("❌ Error: --file argument required for batch mode")
                print("\nExample: python run_agent.py --mode batch --file incidents.txt")
                sys.exit(1)
            asyncio.run(run_batch_queries(args.model, args.file))
        
        elif args.mode == "test":
            asyncio.run(run_tests(args.model))
        
    except KeyboardInterrupt:
        print("\n\n👋 Session ended by user.")
    except Exception as e:
        print(f"\n❌ A critical error occurred: {e}")
        import traceback
        traceback.print_exc()