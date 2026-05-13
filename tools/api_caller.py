"""
Universal API Caller tool — make HTTP requests to generic interfaces.
"""

import httpx
import json
import logging

logger = logging.getLogger("aether.tools.api_caller")

TOOL_NAME = "api_caller"
TOOL_DESCRIPTION = "Call any REST API using GET, POST, PUT, DELETE with optional headers and payload."

async def run(**kwargs) -> str:
    url = kwargs.get("url") or kwargs.get("endpoint") or ""
    method = kwargs.get("method", "GET")
    headers = kwargs.get("headers")
    payload = kwargs.get("payload") or kwargs.get("data") or kwargs.get("json")
    
    if not url: return "Error: 'url' parameter is required."
    if not headers:
        headers = {}
        
    method = method.upper()
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            req_params = {
                "method": method,
                "url": url,
                "headers": headers
            }
            if payload and method in ["POST", "PUT", "PATCH"]:
                if "content-type" not in {k.lower() for k in headers.keys()}:
                    req_params["json"] = payload
                else:
                    if "application/json" in str(headers).lower():
                        req_params["json"] = payload
                    else:
                        req_params["data"] = payload

            response = await client.request(**req_params)
            
            try:
                data = response.json()
                out = json.dumps(data, indent=2)
            except:
                out = response.text
                
            out = out[:10000] # Cap output length to avoid destroying context
            return f"[{response.status_code} {response.reason_phrase}]\n{out}"
    except Exception as e:
        logger.error(f"API Caller error: {e}")
        return f"Request failed: {e}"
