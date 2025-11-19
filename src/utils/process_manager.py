import os
import sys
import signal
import psutil
from pathlib import Path
import logging

class ProcessManager:
    """Process management utility to prevent duplicate bot instances"""
    
    def __init__(self, pid_file: str = "bot.pid"):
        self.pid_file = Path(pid_file)
        self.pid = os.getpid()
    
    def check_existing_process(self) -> bool:
        """Check if another bot instance is running"""
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Check if process with old PID exists
            if psutil.pid_exists(old_pid):
                try:
                    old_process = psutil.Process(old_pid)
                    # Check if it's actually our bot (check process name or command line)
                    if 'python' in old_process.name().lower() or 'bot' in ' '.join(old_process.cmdline()):
                        logging.warning(f"Found existing bot process with PID {old_pid}")
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # PID file exists but process doesn't, remove it
            self.pid_file.unlink(missing_ok=True)
            return False
            
        except (ValueError, FileNotFoundError, PermissionError):
            # Invalid PID file, remove it
            self.pid_file.unlink(missing_ok=True)
            return False
    
    def kill_existing_process(self) -> bool:
        """Kill existing bot process"""
        if not self.pid_file.exists():
            return True
        
        try:
            with open(self.pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            if psutil.pid_exists(old_pid):
                try:
                    old_process = psutil.Process(old_pid)
                    old_process.terminate()
                    old_process.wait(timeout=10)  # Wait up to 10 seconds
                    logging.info(f"Successfully terminated old bot process with PID {old_pid}")
                except (psutil.NoSuchProcess, psutil.TimeoutExpired, psutil.AccessDenied) as e:
                    logging.error(f"Failed to terminate old process: {e}")
                    return False
            
            self.pid_file.unlink(missing_ok=True)
            return True
            
        except (ValueError, FileNotFoundError) as e:
            logging.error(f"Error reading PID file: {e}")
            return False
    
    def write_pid_file(self) -> bool:
        """Write current PID to file"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(self.pid))
            logging.info(f"Bot started with PID {self.pid}")
            return True
        except (PermissionError, IOError) as e:
            logging.error(f"Failed to write PID file: {e}")
            return False
    
    def remove_pid_file(self) -> bool:
        """Remove PID file on shutdown"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logging.info("PID file removed")
            return True
        except (PermissionError, IOError) as e:
            logging.error(f"Failed to remove PID file: {e}")
            return False
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, shutting down gracefully...")
            self.remove_pid_file()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

# Global instance
process_manager = ProcessManager()