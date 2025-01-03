import logging
import logging.config


def getLogger(name):

    if name == "__main__":
        logger = logging.getLogger()
        logging.config.fileConfig('logging.conf')
    else:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
    return logger


def addLogHandler(handler):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger  = logging.getLogger()
    logger.addHandler(handler)