"""
Resource Manager - Intelligent Worker Allocation
Determines optimal worker counts for different tasks based on system resources provided by Java
"""

import os
import platform
import multiprocessing
import logging
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages intelligent worker allocation based on system resources"""
    
    def __init__(self, cpu_count: Optional[int] = None, physical_cores: Optional[int] = None, 
                 total_ram_gb: Optional[float] = None, available_ram_gb: Optional[float] = None):
        """
        Initialize with system resources (provided by Java or auto-detected)
        
        Args:
            cpu_count: Logical CPU core count (if None, will auto-detect)
            physical_cores: Physical CPU core count (if None, will use cpu_count)
            total_ram_gb: Total system RAM in GB (if None, will be 0)
            available_ram_gb: Available RAM in GB (if None, will be 0)
        """
        self.cpu_count = cpu_count if cpu_count is not None else multiprocessing.cpu_count()
        self.physical_cores = physical_cores if physical_cores is not None else self.cpu_count
        self.total_ram_gb = total_ram_gb if total_ram_gb is not None else 0.0
        self.available_ram_gb = available_ram_gb if available_ram_gb is not None else 0.0
        
        logger.info("=== System Resources ===")
        logger.info(f"CPU Cores (Logical): {self.cpu_count}")
        logger.info(f"CPU Cores (Physical): {self.physical_cores}")
        if self.total_ram_gb > 0:
            logger.info(f"Total RAM: {self.total_ram_gb:.2f} GB")
            logger.info(f"Available RAM: {self.available_ram_gb:.2f} GB")
        else:
            logger.info("RAM info not provided")
    
    def update_resources(self, cpu_count: Optional[int] = None, physical_cores: Optional[int] = None,
                        total_ram_gb: Optional[float] = None, available_ram_gb: Optional[float] = None):
        """Update resource values (called from Java with current system state)"""
        if cpu_count is not None:
            self.cpu_count = cpu_count
        if physical_cores is not None:
            self.physical_cores = physical_cores
        if total_ram_gb is not None:
            self.total_ram_gb = total_ram_gb
        if available_ram_gb is not None:
            old_available = self.available_ram_gb
            self.available_ram_gb = available_ram_gb
            if abs(old_available - self.available_ram_gb) > 1.0:  # More than 1GB change
                logger.info(f"Available RAM updated: {old_available:.2f}GB → {self.available_ram_gb:.2f}GB")
    
    def get_optimal_worker_count(self, task_type: str) -> int:
        """
        Calculate optimal worker count based on task type and system resources
        
        Args:
            task_type: Type of task ("whisper", "encoding", "subtitle_search", "download", "metadata")
            
        Returns:
            Optimal number of workers for this task type
        """
        if task_type == "whisper":
            # Whisper AI: Memory-intensive (4-8GB per instance)
            return self._calculate_whisper_workers()
        
        elif task_type == "encoding":
            # Video encoding: CPU-intensive, use physical cores
            # Leave 1-2 cores free for system
            return max(1, self.physical_cores - 1)
        
        elif task_type == "subtitle_search":
            # Subtitle search: Network I/O bound, can parallelize heavily
            # Use more workers than CPU cores (network waiting)
            return min(8, self.cpu_count * 2)
        
        elif task_type == "download":
            # Downloads: Network I/O bound, moderate parallelization
            return min(6, self.cpu_count)
        
        elif task_type == "metadata":
            # Metadata operations: Light CPU, moderate I/O
            return min(4, self.cpu_count)
        
        else:
            # Default: use half of logical cores
            return max(2, self.cpu_count // 2)
    
    def _calculate_whisper_workers(self) -> int:
        """
        Calculate optimal Whisper workers based on available RAM
        
        Memory requirements per Whisper model:
        - Tiny: ~1GB
        - Base: ~2GB
        - Small: ~5GB
        - Medium: ~10GB
        - Large: ~15GB
        
        We assume Small model (5GB) as default, with 4GB buffer for system
        """
        # If RAM info not available, use conservative estimate based on CPU
        if self.available_ram_gb <= 0:
            logger.info("RAM info not available, using CPU-based estimate for Whisper workers")
            return max(1, min(2, self.physical_cores // 2))
        
        # Conservative estimate: 5GB per Whisper instance (small model is most common)
        gb_per_instance = 5.0
        
        # Reserve 4GB for system and other processes
        available_for_whisper = max(0, self.available_ram_gb - 4)
        
        # Calculate how many instances we can run
        max_instances = int(available_for_whisper / gb_per_instance)
        
        # Limit to physical cores (Whisper is CPU-intensive too)
        max_instances = min(max_instances, self.physical_cores)
        
        # At least 1, at most 4 (diminishing returns beyond 4 parallel transcriptions)
        optimal = max(1, min(4, max_instances))
        
        logger.info(f"Whisper workers: {optimal} (based on {self.available_ram_gb:.2f}GB available RAM, {gb_per_instance}GB per instance)")
        return optimal
    
    def get_system_info(self) -> Dict:
        """Get detailed system information for diagnostics"""
        return {
            "cpu_count_logical": self.cpu_count,
            "cpu_count_physical": self.physical_cores,
            "total_ram_gb": round(self.total_ram_gb, 2) if self.total_ram_gb > 0 else None,
            "available_ram_gb": round(self.available_ram_gb, 2) if self.available_ram_gb > 0 else None,
            "platform": platform.system(),
            "platform_version": platform.version(),
            "python_version": platform.python_version()
        }
    
    def can_run_parallel_whisper(self, num_instances: int = 2) -> Tuple[bool, str]:
        """
        Check if system can handle multiple parallel Whisper instances
        
        Args:
            num_instances: Number of parallel instances to check
            
        Returns:
            Tuple of (can_run: bool, reason: str)
        """
        if self.available_ram_gb <= 0:
            # No RAM info, use conservative CPU check only
            if self.physical_cores < num_instances:
                return False, f"Insufficient CPU cores: need {num_instances}, have {self.physical_cores}"
            return True, f"Can run {num_instances} parallel Whisper instances (RAM info unavailable)"
        
        gb_per_instance = 4.0
        required_ram = num_instances * gb_per_instance + 2  # +2GB for system
        
        if self.available_ram_gb < required_ram:
            return False, f"Insufficient RAM: need {required_ram:.1f}GB, have {self.available_ram_gb:.1f}GB"
        
        if self.physical_cores < num_instances:
            return False, f"Insufficient CPU cores: need {num_instances}, have {self.physical_cores}"
        
        return True, f"Can run {num_instances} parallel Whisper instances"
    
    def should_use_gpu(self) -> bool:
        """Check if GPU acceleration should be used (if available)"""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_count = torch.cuda.device_count()
                logger.info(f"CUDA available: {gpu_count} GPU(s) detected")
                return True
        except ImportError:
            pass
        
        logger.info("No GPU acceleration available, using CPU")
        return False
    
    def get_encoding_workers(self) -> int:
        """Get optimal encoding worker count"""
        # For encoding, use physical cores minus 1 (leave one core free)
        # But at least 1 worker
        workers = max(1, self.physical_cores - 1)
        logger.info(f"Encoding workers: {workers} (based on {self.physical_cores} physical cores)")
        return workers


# Global instance for easy access
_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get or create the global ResourceManager instance"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


def update_system_resources(cpu_count: int, physical_cores: int, total_ram_gb: float, available_ram_gb: float):
    """Update system resources from Java (called when Java provides fresh measurements)"""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager(cpu_count, physical_cores, total_ram_gb, available_ram_gb)
    else:
        _resource_manager.update_resources(cpu_count, physical_cores, total_ram_gb, available_ram_gb)
    logger.info("System resources updated from Java")

