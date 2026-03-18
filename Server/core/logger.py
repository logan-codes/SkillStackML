import logging

class StringFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        data = (
            f"level:{record.levelname.lower()}"
            f"|message:{record.getMessage()}"
            f"|logger:{record.name}"
            f"|timestamp:{timestamp}"
        )

        if record.exc_info:
            data += f"|exception:{self.formatException(record.exc_info)}"

        return data
    

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(StringFormatter())
        file_handler = logging.FileHandler("app.log")
        file_handler.setFormatter(StringFormatter())
        logger.addHandler(handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


logger = get_logger("app")
