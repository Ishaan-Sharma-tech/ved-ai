import os
import itertools
from dotenv import load_dotenv

load_dotenv()

class GroqKeyVault:
    def __init__(self):
        self.ceo_key = os.environ.get("GROQ_CEO_KEY", "")
        self.freelance_key = os.environ.get("GROQ_FREELANCE_KEY", "")
        
        # Load keys 3 through 6 into the worker pool
        pool_keys = []
        for i in range(3, 7):
            k = os.environ.get(f"GROQ_WORKER_KEY_{i}")
            if k: pool_keys.append(k)
            
        self.worker_pool = itertools.cycle(pool_keys) if pool_keys else None
        
        # All 6 keys for the classifier to use universally
        all_keys = [self.ceo_key, self.freelance_key] + pool_keys
        self.universal_pool = itertools.cycle([k for k in all_keys if k])

    def get_executive_key(self, role: str) -> str:
        if role == "ceo": return self.ceo_key
        if role == "freelance": return self.freelance_key
        return self.get_worker_key()

    def get_worker_key(self) -> str:
        if self.worker_pool:
            return next(self.worker_pool)
        return self.ceo_key # Fallback
        
    def get_universal_key(self) -> str:
        if self.universal_pool:
            return next(self.universal_pool)
        return self.ceo_key # Fallback

GROQ_VAULT = GroqKeyVault()
