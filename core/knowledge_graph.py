"""
Knowledge Graph — Ved's long-term associative memory.
Uses NetworkX to store triplets (Subject-Predicate-Object).
"""
import networkx as nx
import json
import os
import logging
import asyncio
from pathlib import Path
from core.corporate.utils import _resilient_chat

logger = logging.getLogger("aether.knowledge_graph")

# Use project root for portability
PROJECT_ROOT = Path(__file__).parent.parent
KG_DIR = PROJECT_ROOT / "memory"
KG_FILE = KG_DIR / "aether_kg.json"

G = nx.DiGraph()
_kg_lock = asyncio.Lock()

def load_graph():
    global G
    if KG_FILE.exists():
        try:
            with open(KG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                try:
                    G = nx.node_link_graph(data, directed=True, multigraph=False)
                except TypeError:
                    # Older NetworkX versions don't accept these kwargs
                    G = nx.node_link_graph(data)
                if not isinstance(G, nx.DiGraph):
                    G = nx.DiGraph(G)
        except Exception as e:
            logger.error(f"Failed to load KG: {e}")
            G = nx.DiGraph()
    else:
        KG_DIR.mkdir(parents=True, exist_ok=True)
        G = nx.DiGraph()
        save_graph()

def save_graph():
    try:
        # Ensure dir exists before saving
        KG_DIR.mkdir(parents=True, exist_ok=True)
        with open(KG_FILE, "w", encoding="utf-8") as f:
            # Using standard node_link_data without forcing 'edges' kwarg for stability
            data = nx.node_link_data(G)
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save KG: {e}")

# Load the graph into memory immediately when the module is imported
load_graph()

async def extract_and_inject(text: str):
    """Background task to extract triplets and inject them into the graph."""
    if not text or len(text.strip()) < 10:
        return
        
    prompt = f"""You are a Knowledge Graph entity extractor. 
Extract up to 3 core undeniable facts, projects, or preferences from the user's message as Subject-Predicate-Object triplets.
Return ONLY a raw JSON array of objects with keys 's' (subject), 'p' (predicate), 'o' (object).
Example string: "I hate using Tailwind CSS for the Aeon project"
Example JSON: [{{"s": "User", "p": "hates", "o": "Tailwind CSS"}}, {{"s": "Tailwind CSS", "p": "used in", "o": "Aeon project"}}]
If no strong facts exist, return an empty array []. No markdown, just raw JSON.
User message: '{text}'"""
    
    messages = [{"role": "system", "content": prompt}]
    try:
        # Use a background thread for the sync parts of the graph update
        response_str = await _resilient_chat(messages, model="llama-3.1-8b-instant", role="worker")
        start = response_str.find("[")
        end = response_str.rfind("]")
        if start != -1 and end != -1:
            raw_json = response_str[start:end+1]
            triplets = json.loads(raw_json)
            
            async with _kg_lock:
                added = False
                for t in triplets:
                    s, p, o = t.get('s'), t.get('p'), t.get('o')
                    if s and p and o:
                        G.add_node(s)
                        G.add_node(o)
                        G.add_edge(s, o, relation=p)
                        added = True
                if added:
                    await asyncio.to_thread(save_graph)
                    logger.info(f"KG updated with {len(triplets)} triplets.")
    except Exception as e:
        logger.warning(f"KG Extraction failed: {e}")

def get_context_from_kg(query: str, max_triplets=10) -> list[str]:
    """Sweep the graph for node matches based on the query."""
    words = [w.lower() for w in query.split() if w.lower() not in ["can", "you", "the", "and", "how", "what", "where", "why", "this", "that", "make", "create"] and len(w) > 3][:15]
    if not words:
        return []
        
    matched_nodes = []
    for node in G.nodes():
        node_lower = str(node).lower()
        if any(w in node_lower for w in words):
            matched_nodes.append(node)
            
    if not matched_nodes:
        return []
        
    facts = []
    for node in matched_nodes[:5]:
        for out_edge in G.out_edges(node, data=True):
            facts.append(f"[{out_edge[0]}] {out_edge[2].get('relation', 'related to')} [{out_edge[1]}]")
        for in_edge in G.in_edges(node, data=True):
            facts.append(f"[{in_edge[0]}] {in_edge[2].get('relation', 'related to')} [{in_edge[1]}]")
            
    return list(set(facts))[:max_triplets]
