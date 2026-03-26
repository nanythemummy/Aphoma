import logging
import threading
import time
def thread_function(name):
    logging.info("Thread %s: Starting its thing", name)
    time.sleep(2)
    logging.info("Thread %s: Stopping its thing.",name)
if __name__ == "__main__":
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level = logging.INFO, datefmt= "%H:%M:%S")
    logging.info("Main : before creating thread")
    x = threading.Thread(target=thread_function,args=(1,))
    logging.info("Main : wait to finish")
    #x.join()
    logging.info("Main : done")
