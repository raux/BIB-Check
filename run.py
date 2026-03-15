"""Entry point for BibValidate-AI backend server.

Usage::

    python run.py

The ``if __name__ == "__main__"`` guard is required for safe multiprocessing on
macOS and Windows where the default start method is ``spawn``.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
