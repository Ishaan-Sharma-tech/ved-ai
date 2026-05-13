"""
Workspace Manager — Strict context orchestration.
Controls focus modes by terminating distracting applications.
"""

import psutil
import logging

TOOL_NAME = "workspace_manager"
TOOL_DESCRIPTION = "Manage workspaces and focus modes. Actions: enable_focus, disable_focus."

logger = logging.getLogger("aether.tools.workspace_manager")

DISTRACTING_APPS = ["discord.exe", "steam.exe", "telegram.exe", "whatsapp.exe", "epicgameslauncher.exe"]

async def run(**kwargs) -> str:
    action = kwargs.get("action", "").lower().strip()
    
    if action == "enable_focus":
        killed = []
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info.get('name')
                if name and name.lower() in DISTRACTING_APPS:
                    proc.kill()
                    killed.append(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
                
        # Hosts file modification (Needs Admin)
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        blocked_sites = ["www.youtube.com", "youtube.com", "www.reddit.com", "reddit.com"]
        hosts_status = "Skipped hosts file (No Admin rights)."
        
        try:
            with open(hosts_path, "r+") as f:
                content = f.read()
                added = False
                for site in blocked_sites:
                    if site not in content:
                        f.write(f"\n127.0.0.1 {site}")
                        added = True
                if added:
                    hosts_status = "Blocked distracting sites in hosts file."
                else:
                    hosts_status = "Distracting sites already blocked."
        except PermissionError:
            pass
        except Exception as e:
            hosts_status = f"Hosts error: {e}"
            
        return f"Focus mode enabled! Killed: {', '.join(set(killed)) or 'None'}. {hosts_status}"
        
    elif action == "disable_focus":
        hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
        blocked_sites = ["www.youtube.com", "youtube.com", "www.reddit.com", "reddit.com"]
        hosts_status = "Skipped hosts file (No Admin rights)."
        
        try:
            with open(hosts_path, "r") as f:
                lines = f.readlines()
            
            with open(hosts_path, "w") as f:
                removed = False
                for line in lines:
                    if not any(site in line for site in blocked_sites):
                        f.write(line)
                    else:
                        removed = True
                        
                if removed:
                    hosts_status = "Unblocked distracting sites."
                else:
                    hosts_status = "No sites were historically blocked."
        except PermissionError:
            pass
        except Exception as e:
            hosts_status = f"Hosts error: {e}"
            
        return f"Focus mode disabled! Relax mode active. {hosts_status}"
        
    return "Unknown action. Use 'enable_focus' or 'disable_focus'."
