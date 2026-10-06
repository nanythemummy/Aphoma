import logging
import logging.config

_configured = False

def getLogger(name):

    global _configured
    if name == "__main__":
        logger = logging.getLogger()
        if not _configured:
            #fileConfig() defaults to disable_existing_loggers=True, which permanently disables any
            #other module's logger that already exists at this point and isn't listed in
            #logging.conf's [loggers] section (only "root" is)--and since this branch re-runs every
            #time anything logs via getLogger(__name__) from the "__main__" script, it kept silently
            #and unpredictably disabling other modules' loggers depending on timing (e.g. a module-level
            #logger created at import time, or a lazily-created one caught by a later re-run). Configure
            #logging exactly once, and don't disable loggers that already exist.
            logging.config.fileConfig('logging.conf', disable_existing_loggers=False)
            _configured = True
    else:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
    return logger


def addLogHandler(handler):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger  = logging.getLogger()
    logger.addHandler(handler)
    handler.setLevel(logging.DEBUG)