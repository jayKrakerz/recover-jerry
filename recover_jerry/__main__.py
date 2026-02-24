"""Entry point: python -m recover_jerry"""

import uvicorn
from .config import settings


def main():
    uvicorn.run(
        "recover_jerry.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
