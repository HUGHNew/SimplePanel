#!/usr/bin/env python3
import os
import time
import json
import socket
import urllib.request
import urllib.error
import subprocess
import shutil
from datetime import datetime
from typing import Any, Dict, List, Tuple

class StatsRegistry:
    _registry: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name):
        def decorator(stats_class):
            cls._registry[name] = stats_class
            return stats_class
        return decorator
    
    @classmethod
    def get_all_stats_classes(cls):
        return cls._registry
    
    @classmethod
    def get_stats_class(cls, name):
        return cls._registry.get(name)

class BaseStats:
    def collect(self) -> Dict[str, Any]:
        raise NotImplementedError("Subclass must implement abstract method")
    
    def to_json(self) -> Dict[str, Any]:
        return self.collect()


@StatsRegistry.register("cpu")
class CpuStats(BaseStats):
    def _read_time(self,) -> Tuple[int, int]:
        with open('/proc/stat', 'r') as f:
            cpu_stats = f.readline().split()

        # CPU times: user, nice, system, idle, iowait, irq, softirq
        cpu_times = [int(x) for x in cpu_stats[1:8]]
        return sum(cpu_times), cpu_times[3]
    def collect(self) -> Dict[str, Any]:
        try:
            total_time_0, idle_time_0 = self._read_time()

            time.sleep(1)

            total_time_1, idle_time_1 = self._read_time()

            delta_total = total_time_1 - total_time_0
            delta_idle = idle_time_1 - idle_time_0
            
            cpu_usage = 100 * (1 - delta_idle / delta_total)
            cpu_count = os.cpu_count() or 1
            cpu_model = "Unknown"
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if line.startswith('model name'):
                            cpu_model = line.split(':')[1].strip()
                            break
            except Exception:
                pass
            
            return {
                "usage": round(cpu_usage, 2),
                "cores": cpu_count,
                "model": cpu_model
            }
        except Exception as e:
            print(f"Error getting CPU stats: {e}")
            return {"usage": 0, "cores": 1, "model": "Unknown"}


@StatsRegistry.register("gpu")
class GpuStats(BaseStats):
    
    def collect(self) -> Dict[str, Any]:
        if not shutil.which('nvidia-smi'):
            return {"available": False, "gpus": []}
        
        try:
            gpu_count_output = subprocess.check_output(
                ['nvidia-smi', '--query-gpu=count', '--format=csv,noheader,nounits'],
                stderr=subprocess.DEVNULL
            ).decode('utf-8').strip()            

            if not gpu_count_output:
                return {"available": False, "gpus": []}
            

            output = subprocess.check_output([
                'nvidia-smi', 
                '--query-gpu=index,name,memory.total,memory.used,utilization.gpu',
                '--format=csv,noheader,nounits'
            ], stderr=subprocess.DEVNULL).decode('utf-8')
            
            gpus = []
            for line in output.strip().split('\n'):
                if line:
                    parts = line.split(', ')
                    if len(parts) >= 5:
                        gpu_idx = int(parts[0])
                        name = parts[1]
                        mem_total = float(parts[2])  # MB
                        mem_used = float(parts[3])   # MB
                        utilization = float(parts[4])  # %
                        
                        gpus.append({
                            "index": gpu_idx,
                            "name": name,
                            "memory_total_mb": mem_total,
                            "memory_used_mb": mem_used,
                            "memory_used_percent": round(mem_used / mem_total * 100, 2) if mem_total > 0 else 0,
                            "utilization": round(utilization, 2)
                        })
            
            return {
                "available": True,
                "count": len(gpus),
                "gpus": gpus
            }
        except Exception as e:
            print(f"Error getting GPU stats: {e}")
            return {"available": False, "gpus": []}


@StatsRegistry.register("memory")
class MemoryStats(BaseStats):
    def __init__(self):
        super().__init__()
    
    def collect(self) -> Dict[str, Any]:
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            
            mem_info = {}
            for line in lines:
                parts = line.split(':')
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value_parts = parts[1].strip().split()
                    if len(value_parts) >= 1 and value_parts[0].isdigit():
                        value = int(value_parts[0])
                        if len(value_parts) >= 2 and value_parts[1] == 'kB':
                            value = value / 1024
                        mem_info[key] = value
            
            total_mb = mem_info.get('MemTotal', 0)
            free_mb = mem_info.get('MemFree', 0)
            available_mb = mem_info.get('MemAvailable', free_mb)
            used_mb = total_mb - available_mb
            used_percent = round(used_mb / total_mb * 100, 2) if total_mb > 0 else 0
            
            swap_total = mem_info.get('SwapTotal', 0)
            swap_free = mem_info.get('SwapFree', 0)
            swap_used = swap_total - swap_free
            swap_used_percent = round(swap_used / swap_total * 100, 2) if swap_total > 0 else 0
            
            return {
                "total_mb": round(total_mb, 2),
                "used_mb": round(used_mb, 2),
                "available_mb": round(available_mb, 2),
                "used_percent": used_percent,
                "swap": {
                    "total_mb": round(swap_total, 2),
                    "used_mb": round(swap_used, 2),
                    "used_percent": swap_used_percent
                }
            }
        except Exception as e:
            print(f"Error getting memory stats: {e}")
            return {
                "total_mb": 0, 
                "used_mb": 0, 
                "available_mb": 0, 
                "used_percent": 0,
                "swap": {"total_mb": 0, "used_mb": 0, "used_percent": 0}
            }

@StatsRegistry.register("disk")
class DiskStats(BaseStats):
    def __init__(self):
        super().__init__()
    
    def _get_mount_points(self) -> List[Dict[str, str]]:
        mount_points = []
        try:
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        device = parts[0]
                        mount_point = parts[1]
                        fs_type = parts[2]
                        
                        if (fs_type in ['ext4', 'ext3', 'ext2', 'xfs', 'btrfs', 'ntfs', 'fat', 'vfat', 'fuseblk', 'f2fs'] and 
                            not mount_point.startswith('/sys/') and 
                            not mount_point.startswith('/boot') and 
                            not mount_point.startswith('/proc/') and
                            not mount_point.startswith('/dev/') and
                            not mount_point.startswith('/run/')):
                            mount_points.append({
                                "device": device,
                                "mount_point": mount_point,
                                "fs_type": fs_type
                            })
        except Exception as e:
            print(f"Error reading mount points: {e}")
        
        # fallback to root
        if not mount_points:
            mount_points.append({
                "device": "unknown",
                "mount_point": "/",
                "fs_type": "unknown"
            })
        
        return mount_points
    
    def collect(self) -> Dict[str, Any]:
        mount_points = self._get_mount_points()
        disks = []
        
        for mp in mount_points:
            mount_point = mp["mount_point"]
            try:
                total, used, free = shutil.disk_usage(mount_point)
                
                # byte -> GiB
                total_gb = round(total / (1024**3), 2)
                used_gb = round(used / (1024**3), 2)
                free_gb = round(free / (1024**3), 2)
                used_percent = round(100 * used / total, 2) if total > 0 else 0
                
                disks.append({
                    "device": mp["device"],
                    "mount_point": mount_point,
                    "fs_type": mp["fs_type"],
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "used_percent": used_percent
                })
            except Exception as e:
                print(f"Error getting disk usage for {mount_point}: {e}")
        
        return {"disks": disks}


@StatsRegistry.register("system")
class SystemStats(BaseStats):
    def __init__(self):
        super().__init__()
    
    def collect(self) -> Dict[str, Any]:

        try:

            hostname = socket.gethostname()

            uptime = 0
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime = float(f.readline().split()[0])
            except Exception:
                pass

            os_name = "Linux"
            with open('/etc/os-release') as f:
                for line in f:
                    if line.startswith("PRETTY_NAME"):
                        os_name = line.split("=")[1].strip()
                        break

            
            return {
                "hostname": hostname,
                "uptime_days": round(uptime / 86400, 2),
                "timestamp": datetime.now().isoformat(),
                "os": os_name,
            }
        except Exception as e:
            print(f"Error getting system stats: {e}")
            return {
                "hostname": socket.gethostname(),
                "uptime_days": 0,
            }

class SystemStatsCollector:
    def __init__(self, server_url: str, stats_list: List[str]=[]):
        self.server_url = server_url
        self.stats_classes = {}

        if not stats_list:
            stats_list = list(StatsRegistry.get_all_stats_classes().keys())
        
        registers = StatsRegistry.get_all_stats_classes()
        for name in stats_list:
            if name not in registers:
                print(f"Unknown stats class: {name}")
                continue
            self.stats_classes[name] = registers[name]()
        
        self.system_stats = self.stats_classes.get("system")
        
    def collect_all_stats(self) -> Dict[str, Any]:
        result = {}
        
        if self.system_stats:
            system_info = self.system_stats.collect()
            result.update(system_info)
        
        for name, stats_collector in self.stats_classes.items():
            if name != "system":
                result[name] = stats_collector.collect()
        
        return result
    
    def send_stats(self) -> bool:
        stats = self.collect_all_stats()
        data = json.dumps(stats).encode('utf-8')
        
        try:
            req = urllib.request.Request(
                url=f"{self.server_url}/report",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req) as response:
                print(f"[{datetime.now().strftime('%Y-%m-%d/%H')}] Stats sent successfully. Response: {response.status}")
                return True
        except urllib.error.URLError as e:
            print(f"Error sending stats: {e}")
            return False