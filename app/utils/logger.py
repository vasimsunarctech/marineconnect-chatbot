import logging
import os
from datetime import datetime

def setup_logger():
    log_dir = 'storage/log'
    os.makedirs(log_dir, exist_ok=True)
    
    logger = logging.getLogger('MarineConnect')
    logger.setLevel(logging.DEBUG)
    
    log_file = os.path.join(log_dir, 'marineconnect.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logger()