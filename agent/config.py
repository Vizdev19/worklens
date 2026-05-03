import os
from dotenv import load_dotenv

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")
CAPTURE_INTERVAL_MINUTES = int(os.getenv("CAPTURE_INTERVAL_MINUTES", "10"))
IDLE_SKIP_MINUTES = int(os.getenv("IDLE_SKIP_MINUTES", "5"))   # skip if idle > 5 min
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "70"))
MAX_WIDTH = int(os.getenv("MAX_WIDTH", "1920"))                 # resize if wider
KEYRING_SERVICE = "EmployeeMonitor"
