from backend.app.main import app

# Vercel Python runtime exposes the FastAPI app as the default WSGI/ASGI entrypoint.
# This wrapper keeps the existing backend and frontend routing unchanged while allowing
# deployment as a single serverless function.
