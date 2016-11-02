import random
from .config import get_setting_value
import logging

logger = logging.getLogger(__name__)

def set_seed():
    if get_setting_value('SET_SEED'):
        logger.info('Setting seed to {}'.format(get_setting_value('SEED')))
        random.seed(get_setting_value('SEED'))

set_seed()