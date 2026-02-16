import logging

from sqlalchemy import Engine, create_engine, text
from tenacity import after_log, before_log, retry, stop_after_attempt, wait_fixed

from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

max_tries = 60 * 5  # 5 minutes
wait_seconds = 1


@retry(
    stop=stop_after_attempt(max_tries),
    wait=wait_fixed(wait_seconds),
    before=before_log(logger, logging.INFO),
    after=after_log(logger, logging.WARN),
)
def init(db_engine: Engine) -> None:
    try:
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(e)
        raise e


def main() -> None:
    logger.info("Initializing service")
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
    init(engine)
    logger.info("Service finished initializing")


if __name__ == "__main__":
    main()
