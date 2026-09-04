import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "src"))

try:
    from config.settings import settings
    
    # Check essential variables
    if not settings.telegram_token or not settings.telegram_token.get_secret_value().strip():
        print("Missing TELEGRAM_TOKEN")
        sys.exit(1)
        
    if not settings.get_gemini_keys():
        print("Missing GEMINI_KEYS")
        sys.exit(1)
        
    if not settings.github_app_id and not settings.github_pat:
        print("Missing GitHub authentication (App ID or PAT)")
        sys.exit(1)
        
    if settings.github_app_id and not settings.github_app_private_key_path:
        print("Missing GitHub App private key path")
        sys.exit(1)
        
    print("Environment variables validated successfully.")
    sys.exit(0)
except Exception as e:
    print(f"Configuration error: {e}")
    sys.exit(1)
