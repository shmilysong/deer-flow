_installed = False


def install_env_settings(app=None):
    global _installed
    if _installed:
        return

    try:
        if app is None:
            from app.gateway.app import app as _app

            app = _app

        from deerflow_extensions.env_settings.router import router

        app.include_router(router)

        _installed = True
    except Exception as _e:
        import logging

        logging.getLogger(__name__).warning("[EnvSettings] install failed: %s", _e)
