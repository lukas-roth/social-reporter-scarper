import logging 

def get_logger(name):
    # Create a custom logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Set the overall log level to DEBUG

    # Create handlers
    c_handler = logging.StreamHandler()  # Console handler
    f_handler = logging.FileHandler('app.log')  # File handler

    c_handler.setLevel(logging.INFO)  # Console handler logs INFO level and above
    f_handler.setLevel(logging.DEBUG)  # File handler logs DEBUG level and above

    # Create formatters and add them to the handlers
    c_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    c_handler.setFormatter(c_format)
    f_handler.setFormatter(f_format)

    # Add handlers to the logger
    if not logger.hasHandlers():
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)

    return logger