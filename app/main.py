import psutil
import time
from server import Server

def monitor_memory():
    process = psutil.Process()
    while True:
        mem_info = process.memory_info()
        print(f"RSS: {mem_info.rss / 1024 ** 2:.2f} MB, VMS: {mem_info.vms / 1024 ** 2:.2f} MB")
        time.sleep(5)  # Sprawdzaj co 5 sekund

if __name__ == "__main__":
    run = Server()
    import threading
    monitor_thread = threading.Thread(target=monitor_memory)
    monitor_thread.start()
    run.runThePage()