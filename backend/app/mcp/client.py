import asyncio
import json
import logging
import os
import subprocess
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger("forgeos.mcp")

class MCPClient:
    """
    Spawns and manages standard MCP servers (Slack, GitHub, etc.)
    using stdin/stdout subprocesses with JSON-RPC.
    """
    def __init__(self, name: str, command: List[str], env: Optional[Dict[str, str]] = None):
        self.name = name
        self.command = command
        self.env = env or {}
        self.process: Optional[subprocess.Popen] = None
        self._id_counter = 0

    async def connect(self):
        """
        Starts the MCP server subprocess.
        """
        logger.info(f"Connecting to MCP server: {self.name} via command: {' '.join(self.command)}")
        try:
            # Spawn subprocess
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, **self.env}
            )
            # Perform MCP handshake (initialize request)
            await self._initialize_handshake()
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {self.name}: {str(e)}")

    async def _initialize_handshake(self):
        """
        Sends initial JSON-RPC request to establish connection capabilities.
        """
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "OpenFlaw-MCP-Client",
                    "version": "1.0.0"
                }
            }
        }
        await self._send_request(req)
        # Read initialization response
        res = await self._read_response()
        logger.info(f"MCP server {self.name} initialized: {res}")

        # Send initialized notification
        notify = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await self._send_request(notify)

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    async def _send_request(self, payload: Dict[str, Any]):
        if not self.process or not self.process.stdin:
            return
        raw_msg = json.dumps(payload) + "\n"
        self.process.stdin.write(raw_msg)
        self.process.stdin.flush()

    async def _read_response(self) -> Optional[Dict[str, Any]]:
        if not self.process or not self.process.stdout:
            return None
        # Runs in a separate thread pool to prevent locking the async event loop
        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, self.process.stdout.readline)
        if not line:
            return None
        try:
            return json.loads(line.strip())
        except Exception:
            return None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Invokes an MCP tool on the connected server.
        """
        req_id = self._next_id()
        req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        logger.info(f"Calling MCP Tool on {self.name}: {tool_name} with args {arguments}")
        await self._send_request(req)
        
        # Await response
        response = await self._read_response()
        if response and "result" in response:
            return response["result"]
        return {"error": "Failed to receive response from MCP server"}

    def disconnect(self):
        if self.process:
            self.process.terminate()
            self.process = None
            logger.info(f"MCP server {self.name} disconnected.")

# Helper manager class
class MCPManager:
    def __init__(self):
        self.servers: Dict[str, MCPClient] = {}

    async def start_mcp_servers(self):
        """
        Initializes Slack and GitHub MCP servers if tokens are provided.
        """
        # GitHub MCP Server config
        if settings.GITHUB_TOKEN and not settings.SIMULATION_MODE:
            github_env = {"GITHUB_PERSONAL_ACCESS_TOKEN": settings.GITHUB_TOKEN}
            github_client = MCPClient(
                name="GitHub MCP",
                command=["npx", "-y", "@modelcontextprotocol/server-github"],
                env=github_env
            )
            self.servers["github"] = github_client
            await github_client.connect()

        # Slack MCP Server config
        if settings.SLACK_BOT_TOKEN and not settings.SIMULATION_MODE:
            slack_env = {"SLACK_BOT_TOKEN": settings.SLACK_BOT_TOKEN}
            slack_client = MCPClient(
                name="Slack MCP",
                command=["npx", "-y", "@modelcontextprotocol/server-slack"],
                env=slack_env
            )
            self.servers["slack"] = slack_client
            await slack_client.connect()

    def shutdown(self):
        for client in self.servers.values():
            client.disconnect()

mcp_manager = MCPManager()
