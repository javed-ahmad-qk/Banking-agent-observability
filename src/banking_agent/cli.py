import uvicorn

from banking_agent.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("banking_agent.api:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    main()
