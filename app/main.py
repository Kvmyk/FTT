import ctypes
import psutil
import time
import gc
from server import Server

try:
    libc = ctypes.CDLL("libc.so.6")
except Exception as e:
    libc = None

def monitor_memory():
    process = psutil.Process()
    while True:
        if libc:
            # Uwalnia nieużywaną pamięć z heapu
            libc.malloc_trim(0)
        gc.collect()    
        mem_info = process.memory_info()
        print(f"RSS: {mem_info.rss / 1024 ** 2:.2f} MB, VMS: {mem_info.vms / 1024 ** 2:.2f} MB")
        time.sleep(5)  # Sprawdzaj co 5 sekund

if __name__ == "__main__":
    runner = Server()
    import threading
    monitor_thread = threading.Thread(target=monitor_memory)
    monitor_thread.start()
    runner.runThePage()