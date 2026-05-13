"""Desktop version main entry point with PyWebView."""
import asyncio
import logging
import sys
import threading
import traceback
from pathlib import Path

import uvicorn
import webview

# Setup logging to file
log_file = Path.home() / 'AppData' / 'Local' / 'RSSManager' / 'app.log'
log_file.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("Starting RSS Manager Desktop")
logger.info("=" * 60)


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
        logger.info(f"Running from PyInstaller bundle: {base_path}")
    except Exception:
        base_path = Path(__file__).parent
        logger.info(f"Running from source: {base_path}")
    
    return base_path / relative_path


# Add the app directory to Python path
try:
    if hasattr(sys, '_MEIPASS'):
        app_path = Path(sys._MEIPASS) / 'app'
        if app_path.exists():
            sys.path.insert(0, str(app_path.parent))
            logger.info(f"Added to Python path: {app_path.parent}")
    else:
        # Development mode
        sys.path.insert(0, str(Path(__file__).parent))
except Exception as e:
    logger.error(f"Error setting up Python path: {e}")


class DesktopApp:
    """Desktop application manager."""
    
    def __init__(self):
        self.server = None
        self.server_thread = None
        self.port = 8765  # Fixed port for desktop
        self.host = "127.0.0.1"
    
    def start_server(self):
        """Start FastAPI server in background thread."""
        try:
            logger.info("Importing FastAPI app...")
            from app.main_desktop import app
            logger.info("FastAPI app imported successfully")
            
            config = uvicorn.Config(
                app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=False
            )
            self.server = uvicorn.Server(config)
            
            logger.info(f"Starting server on {self.host}:{self.port}")
            
            # Run server in thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.server.serve())
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def start(self):
        """Start the desktop application."""
        try:
            logger.info("Starting RSS Manager Desktop...")
            
            # Start FastAPI server in background thread
            self.server_thread = threading.Thread(target=self.start_server, daemon=True)
            self.server_thread.start()
            
            # Wait for server to start
            import time
            logger.info("Waiting for server to start...")
            time.sleep(3)
            
            # Check if server is running
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex((self.host, self.port))
            sock.close()
            
            if result != 0:
                logger.error(f"Server failed to start on port {self.port}")
                raise Exception("Server failed to start")
            
            logger.info("Server started successfully")
            
            # Create desktop window
            from app.core.config_desktop import settings
            
            logger.info("Creating desktop window...")
            window = webview.create_window(
                title=settings.WINDOW_TITLE,
                url=f"http://{self.host}:{self.port}",
                width=settings.WINDOW_WIDTH,
                height=settings.WINDOW_HEIGHT,
                resizable=True,
                fullscreen=False,
                min_size=(800, 600)
            )
            
            logger.info(f"Opening window at http://{self.host}:{self.port}")
            
            # Start webview (blocking)
            webview.start(debug=False)
            
            logger.info("Application closed")
        except Exception as e:
            logger.error(f"Application error: {e}")
            logger.error(traceback.format_exc())
            raise


def main():
    """Main entry point."""
    try:
        logger.info("Initializing application...")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Python path: {sys.path}")
        logger.info(f"Current directory: {Path.cwd()}")
        
        if hasattr(sys, '_MEIPASS'):
            logger.info(f"PyInstaller temp directory: {sys._MEIPASS}")
        
        app = DesktopApp()
        app.start()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        # Show error dialog
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "RSS Manager Error",
            f"Failed to start application:\n\n{str(e)}\n\nCheck log file at:\n{log_file}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
