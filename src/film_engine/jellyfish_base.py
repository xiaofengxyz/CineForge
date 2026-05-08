from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


UPSTREAM_URL = "https://github.com/Forget-C/Jellyfish"


@dataclass
class JellyfishBaseStatus:
    path: str
    available: bool
    compose_ready: bool
    missing: list[str] = field(default_factory=list)
    upstream_url: str = UPSTREAM_URL
    run_commands: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "available": self.available,
            "compose_ready": self.compose_ready,
            "missing": list(self.missing),
            "upstream_url": self.upstream_url,
            "run_commands": list(self.run_commands),
        }


def inspect_jellyfish_base(base_path: str | Path = "vendor/jellyfish") -> JellyfishBaseStatus:
    base = Path(base_path)
    required = [
        "deploy/compose/docker-compose.yml",
        "deploy/compose/.env.example",
        "backend/pyproject.toml",
        "front/package.json",
        "site",
    ]
    missing = [item for item in required if not (base / item).exists()]
    available = base.exists() and not missing
    compose_ready = (base / "deploy/compose/docker-compose.yml").exists() and (
        base / "deploy/compose/.env.example"
    ).exists()
    return JellyfishBaseStatus(
        path=str(base),
        available=available,
        compose_ready=compose_ready,
        missing=missing,
        run_commands=[
            {
                "id": "docker_compose",
                "label": "Jellyfish full stack",
                "command": "docker compose -f deploy/compose/docker-compose.yml up",
                "ports": {"frontend": "7788", "backend": "8000", "site": "1313"},
            },
            {
                "id": "backend_dev",
                "label": "Backend API",
                "command": "cd backend && uv run uvicorn app.main:app --reload --port 8000",
                "ports": {"backend": "8000"},
            },
            {
                "id": "front_dev",
                "label": "Frontend Studio",
                "command": "cd front && pnpm dev --host 0.0.0.0",
                "ports": {"frontend": "5173"},
            },
        ],
    )

