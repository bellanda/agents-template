from sqlalchemy import MetaData

metadata = MetaData()

from api.models import agents  # noqa: F401, E402
