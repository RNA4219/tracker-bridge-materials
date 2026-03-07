class TrackerBridgeError(Exception):
    pass


class NotFoundError(TrackerBridgeError):
    pass


class DuplicateError(TrackerBridgeError):
    pass


class ValidationError(TrackerBridgeError):
    pass
