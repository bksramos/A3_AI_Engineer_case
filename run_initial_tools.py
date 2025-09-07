# app/tools/mcp_server_setup.py
import os
import sys
import logging
from dotenv import load_dotenv
load_dotenv(os.getenv("DOTENV"))
sys.path.append(os.getenv("TOOLS"))
from mcp.server.fastmcp import FastMCP
from tools.incident_tools import (
    incident_tool_functions
) 

# Create the MCP server instance
mcp = FastMCP("Incident Agent")

# Decorate and register tools
# The mcp.tool() decorator needs an actual function name, not just the call.
# We'll need to wrap or re-assign.

# Collect all tool implementation functions
all_tool_impls = {
    # Incicent Tools
    "parse_incident_structure": incident_tool_functions[0]
}


# Dynamically create and register decorated tools
# This is a bit more advanced but keeps tool definitions clean
registered_mcp_tools = []
for tool_name, tool_impl_func in all_tool_impls.items():
    # Create a new function with the correct name and the decorator
    # The docstring and signature are taken from tool_impl_func
    decorated_tool = mcp.tool(name=tool_name)(tool_impl_func)
    registered_mcp_tools.append(decorated_tool)

if __name__ == "__main__":
    try:
        print("Iniciando servidor MCP1...")
        mcp.run(transport="sse")
        
    except KeyboardInterrupt:
        print("\nDesligando servidor...")
    except Exception as e:
        logging.error(f"Erro ao iniciar servidor: {e}", exc_info=True)
    finally:
        print("Servidor encerrado!")

