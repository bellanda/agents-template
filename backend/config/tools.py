import os

import dotenv

# override=False: a value already in the process env (compose `environment:`, test conftest)
# must beat the repo-root `.env`. With override=True the host-style DATABASE_URL in `.env`
# (localhost) would clobber the docker one (postgres hostname) inside the container.
dotenv.load_dotenv(override=False)


def getenv_or_raise_exception(key: str) -> str:
    """
    Get an environment variable or raise an exception if it is not set.
    """
    value = os.getenv(key)

    if not value:
        raise RuntimeError(f"{key} is not set at .env")

    return value
