"""GPU metrics for monitoring NVIDIA GPU utilization.

This module provides Prometheus metrics for GPU monitoring,
including memory usage, utilization, temperature, and power.

Note: nvidia-ml-py (pynvml) is optional and only used when available.
Metrics will show 0 if no GPU is available or pynvml is not installed.
"""

import time
import threading
from typing import Optional, List, Dict, Any

from prometheus_client import Gauge, Info, REGISTRY, CollectorRegistry

from app.logging_config import get_logger

logger = get_logger(__name__)

# Try to import pynvml for GPU monitoring
try:
    import pynvml
    PYNVML_AVAILABLE = True
except ImportError:
    PYNVML_AVAILABLE = False
    logger.warning("pynvml not available - GPU metrics will be disabled")


class GPUMetrics:
    """NVIDIA GPU metrics for Prometheus.
    
    Collects and exposes GPU metrics including:
    - Memory usage (used, free, total)
    - GPU utilization percentage
    - Temperature
    - Power usage
    - Processes using GPU
    
    Metrics are collected in a background thread to avoid
    blocking request handlers.
    """
    
    def __init__(
        self,
        registry: CollectorRegistry = REGISTRY,
        collection_interval: float = 15.0,
    ):
        """Initialize GPU metrics.
        
        Args:
            registry: Prometheus registry
            collection_interval: Seconds between metric collections
        """
        self.registry = registry
        self.collection_interval = collection_interval
        self._initialized = False
        self._device_count = 0
        self._collection_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # -------------------------------------------------------------------------
        # Memory Metrics
        # -------------------------------------------------------------------------
        self.memory_used = Gauge(
            "gpu_memory_used_bytes",
            "GPU memory currently in use",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        self.memory_total = Gauge(
            "gpu_memory_total_bytes",
            "Total GPU memory available",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        self.memory_free = Gauge(
            "gpu_memory_free_bytes",
            "Free GPU memory",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        self.memory_utilization = Gauge(
            "gpu_memory_utilization_percent",
            "GPU memory utilization percentage",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        # -------------------------------------------------------------------------
        # Utilization Metrics
        # -------------------------------------------------------------------------
        self.utilization = Gauge(
            "gpu_utilization_percent",
            "GPU compute utilization percentage",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        # -------------------------------------------------------------------------
        # Temperature Metrics
        # -------------------------------------------------------------------------
        self.temperature = Gauge(
            "gpu_temperature_celsius",
            "GPU temperature in Celsius",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        self.temperature_threshold = Gauge(
            "gpu_temperature_threshold_celsius",
            "GPU thermal throttle threshold",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        # -------------------------------------------------------------------------
        # Power Metrics
        # -------------------------------------------------------------------------
        self.power_usage = Gauge(
            "gpu_power_usage_watts",
            "Current GPU power usage in Watts",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        self.power_limit = Gauge(
            "gpu_power_limit_watts",
            "GPU power limit in Watts",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        # -------------------------------------------------------------------------
        # Process Metrics
        # -------------------------------------------------------------------------
        self.process_count = Gauge(
            "gpu_process_count",
            "Number of processes using GPU",
            labelnames=["gpu_index"],
            registry=registry,
        )
        
        # -------------------------------------------------------------------------
        # GPU Info
        # -------------------------------------------------------------------------
        self.gpu_info = Info(
            "gpu",
            "GPU device information",
            registry=registry,
        )
        
        # -------------------------------------------------------------------------
        # Availability
        # -------------------------------------------------------------------------
        self.gpu_available = Gauge(
            "gpu_available",
            "Whether GPU is available (1=yes, 0=no)",
            registry=registry,
        )
        
        # -------------------------------------------------------------------------
        # AI Brain Specific
        # -------------------------------------------------------------------------
        self.model_loaded = Gauge(
            "ai_brain_model_loaded",
            "Whether AI Brain model is loaded in GPU memory (1=yes, 0=no)",
            registry=registry,
        )
    
    def initialize(self) -> bool:
        """Initialize NVML and start metrics collection.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if not PYNVML_AVAILABLE:
            logger.warning("GPU metrics disabled - pynvml not installed")
            self.gpu_available.set(0)
            return False
        
        try:
            pynvml.nvmlInit()
            self._device_count = pynvml.nvmlDeviceGetCount()
            self._initialized = True
            
            # Set GPU info
            if self._device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                uuid = pynvml.nvmlDeviceGetUUID(handle)
                if isinstance(uuid, bytes):
                    uuid = uuid.decode("utf-8")
                
                driver_version = pynvml.nvmlSystemGetDriverVersion()
                if isinstance(driver_version, bytes):
                    driver_version = driver_version.decode("utf-8")
                
                self.gpu_info.info({
                    "name": name,
                    "uuid": uuid,
                    "driver_version": driver_version,
                    "device_count": str(self._device_count),
                })
                
                self.gpu_available.set(1)
                logger.info(
                    "GPU metrics initialized",
                    device_count=self._device_count,
                    gpu_name=name,
                )
            
            return True
            
        except Exception as e:
            logger.error("Failed to initialize GPU metrics", error=str(e))
            self.gpu_available.set(0)
            return False
    
    def start_collection(self) -> None:
        """Start background metrics collection thread."""
        if not self._initialized:
            if not self.initialize():
                return
        
        if self._collection_thread is not None and self._collection_thread.is_alive():
            logger.warning("GPU metrics collection already running")
            return
        
        self._stop_event.clear()
        self._collection_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True,
            name="gpu-metrics-collector",
        )
        self._collection_thread.start()
        logger.info("Started GPU metrics collection")
    
    def stop_collection(self) -> None:
        """Stop background metrics collection."""
        if self._collection_thread is not None:
            self._stop_event.set()
            self._collection_thread.join(timeout=5.0)
            self._collection_thread = None
            logger.info("Stopped GPU metrics collection")
        
        if self._initialized and PYNVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._initialized = False
    
    def _collection_loop(self) -> None:
        """Background loop to collect GPU metrics."""
        while not self._stop_event.is_set():
            try:
                self.collect()
            except Exception as e:
                logger.error("Error collecting GPU metrics", error=str(e))
            
            # Wait for next collection interval
            self._stop_event.wait(self.collection_interval)
    
    def collect(self) -> None:
        """Collect current GPU metrics."""
        if not self._initialized or not PYNVML_AVAILABLE:
            return
        
        try:
            for i in range(self._device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                gpu_index = str(i)
                
                # Memory
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                self.memory_used.labels(gpu_index=gpu_index).set(mem_info.used)
                self.memory_total.labels(gpu_index=gpu_index).set(mem_info.total)
                self.memory_free.labels(gpu_index=gpu_index).set(mem_info.free)
                self.memory_utilization.labels(gpu_index=gpu_index).set(
                    (mem_info.used / mem_info.total) * 100 if mem_info.total > 0 else 0
                )
                
                # Utilization
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    self.utilization.labels(gpu_index=gpu_index).set(util.gpu)
                except pynvml.NVMLError:
                    pass
                
                # Temperature
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle,
                        pynvml.NVML_TEMPERATURE_GPU,
                    )
                    self.temperature.labels(gpu_index=gpu_index).set(temp)
                    
                    # Thermal threshold
                    threshold = pynvml.nvmlDeviceGetTemperatureThreshold(
                        handle,
                        pynvml.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN,
                    )
                    self.temperature_threshold.labels(gpu_index=gpu_index).set(threshold)
                except pynvml.NVMLError:
                    pass
                
                # Power
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW to W
                    self.power_usage.labels(gpu_index=gpu_index).set(power)
                    
                    power_lim = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000
                    self.power_limit.labels(gpu_index=gpu_index).set(power_lim)
                except pynvml.NVMLError:
                    pass
                
                # Processes
                try:
                    processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                    self.process_count.labels(gpu_index=gpu_index).set(len(processes))
                except pynvml.NVMLError:
                    pass
                    
        except Exception as e:
            logger.error("Error collecting GPU metrics", error=str(e))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of current GPU metrics.
        
        Returns:
            Dictionary with GPU metrics summary
        """
        if not self._initialized or not PYNVML_AVAILABLE:
            return {
                "available": False,
                "device_count": 0,
                "devices": [],
            }
        
        try:
            devices = []
            for i in range(self._device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                
                device_info = {
                    "index": i,
                    "name": name,
                    "memory_used_mb": round(mem_info.used / 1024 / 1024, 2),
                    "memory_total_mb": round(mem_info.total / 1024 / 1024, 2),
                    "memory_free_mb": round(mem_info.free / 1024 / 1024, 2),
                    "memory_utilization_percent": round(
                        (mem_info.used / mem_info.total) * 100, 2
                    ),
                }
                
                # Add utilization if available
                try:
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    device_info["utilization_percent"] = util.gpu
                except pynvml.NVMLError:
                    device_info["utilization_percent"] = None
                
                # Add temperature if available
                try:
                    temp = pynvml.nvmlDeviceGetTemperature(
                        handle,
                        pynvml.NVML_TEMPERATURE_GPU,
                    )
                    device_info["temperature_celsius"] = temp
                except pynvml.NVMLError:
                    device_info["temperature_celsius"] = None
                
                # Add power if available
                try:
                    power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000
                    device_info["power_watts"] = round(power, 2)
                except pynvml.NVMLError:
                    device_info["power_watts"] = None
                
                devices.append(device_info)
            
            return {
                "available": True,
                "device_count": self._device_count,
                "devices": devices,
            }
            
        except Exception as e:
            logger.error("Error getting GPU summary", error=str(e))
            return {
                "available": False,
                "error": str(e),
                "device_count": 0,
                "devices": [],
            }
    
    def set_model_loaded_status(self, loaded: bool) -> None:
        """Set whether AI model is loaded in GPU.
        
        Args:
            loaded: True if model is loaded
        """
        self.model_loaded.set(1 if loaded else 0)


# Singleton instance
gpu_metrics = GPUMetrics()
