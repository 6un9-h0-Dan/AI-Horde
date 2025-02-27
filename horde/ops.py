from loguru import logger

from horde.flask import HORDE, db
from horde.database import functions as database

@logger.catch(reraise=True)
def force_patreon_kudos(user_id, prevent_date_change):
    with HORDE.app_context():
        user = database.find_user_by_id(user_id)
        user.receive_monthly_kudos(force=True, prevent_date_change=prevent_date_change)