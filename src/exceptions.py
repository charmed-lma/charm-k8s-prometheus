class CharmError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return repr(self.message)


class ExternalLabelParseError(CharmError):
    pass


class TimeStringParseError(CharmError):
    pass


class PrometheusAPIError(CharmError):
    pass
