import psutil
import time
from server import Server

def monitor_memory():
    process = psutil.Process()
    while True:
        mem_info = process.memory_info()
        if mem_info.rss > 100 * 1024 * 1024:  # If over 100MB
            runner.cleanup()
        print(f"RSS: {mem_info.rss / 1024 ** 2:.2f} MB")
        time.sleep(5)  # Sprawdzaj co 5 sekund

if __name__ == "__main__":
    runner = Server()
    import threading
    monitor_thread = threading.Thread(target=monitor_memory)
    monitor_thread.start()
    runner.runThePage()