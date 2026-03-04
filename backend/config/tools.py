import os

import dotenv

dotenv.load_dotenv(override=True)


def getenv_or_raise_exception(key: str) -> str:
    """
    Get an environment variable or raise an exception if it is not set.
    """
    value = os.getenv(key)

    if not value:
        raise RuntimeError(f"{key} is not set at .env")

    return value
