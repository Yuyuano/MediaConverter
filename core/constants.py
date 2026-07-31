VIDEO_EXTS = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.m2ts'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.tiff', '.tif', '.ico', '.raw', '.cr2', '.nef'}
AUDIO_EXTS = {'.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a', '.wma'}
ALL_MEDIA_EXTS = VIDEO_EXTS | IMAGE_EXTS | AUDIO_EXTS
APP_VERSION = "5.2"

DEFAULT_CRF = 23
DEFAULT_AUDIO_BITRATE = '192k'
DEFAULT_IMAGE_QUALITY = 85
MAX_HISTORY_RECORDS = 20
FFMPEG_SUBPROCESS_TIMEOUT = 30
