import sys

EXTENSION_PATH = "/app/deerflow_extensions"
if EXTENSION_PATH not in sys.path:
    sys.path.insert(0, EXTENSION_PATH)

DEERFLOW_PATH = "/app/backend/packages/harness"
if DEERFLOW_PATH not in sys.path:
    sys.path.insert(0, DEERFLOW_PATH)

try:
    from deerflow_extensions.ads_auth.startup import install_ads_auth
    install_ads_auth()
except Exception:
    pass
