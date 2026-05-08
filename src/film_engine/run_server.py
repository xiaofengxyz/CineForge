from __future__ import annotations

from .server import create_server


def main() -> None:
    server = create_server("127.0.0.1", 8799)
    print("LuminAI Studio Dashboard: http://127.0.0.1:8799")
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

