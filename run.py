import sys
import traceback

from app import app


if __name__ == "__main__":
    with open("flask.server.log", "a", encoding="utf-8") as log:
        sys.stdout = log
        sys.stderr = log
        try:
            app.run(host="127.0.0.1", port=5000, debug=False)
        except Exception:
            traceback.print_exc()
            raise
