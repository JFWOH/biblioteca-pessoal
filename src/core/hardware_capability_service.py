"""
Hardware Capability Service
Detects system capabilities to decide if we can run Gemma 4 12B or just E4B or fallback.
"""
import logging
import platform
import ctypes

try:
    import torch
    HAS_TORCH = True
except (ImportError, OSError):
    HAS_TORCH = False

logger = logging.getLogger(__name__)

class HardwareCapabilityService:
    def __init__(self):
        self._cached_tier = None
    
    def get_recommended_tier(self) -> str:
        if self._cached_tier is not None:
            return self._cached_tier
            
        tier = "Tier B" # Default
        
        try:
            if HAS_TORCH and torch.cuda.is_available():
                vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                if vram_gb > 10.0:
                    tier = "Tier A"
                else:
                    tier = "Tier B"
            else:
                if platform.system() == "Windows":
                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]
                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                    ram_gb = stat.ullTotalPhys / (1024**3)
                    if ram_gb < 8.0:
                        tier = "Tier C"
                
        except Exception as e:
            logger.warning(f"Erro ao detectar capability: {e}. Usando Tier B (E4B).")
            
        self._cached_tier = tier
        return tier
        
    def get_proactive_model_name(self) -> str:
        tier = self.get_recommended_tier()
        if tier == "Tier A":
            return "gemma4:12b"
        elif tier == "Tier B":
            return "gemma4:e4b"
        else:
            return ""
