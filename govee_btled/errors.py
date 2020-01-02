class ConnectionTimeout(RuntimeError):
    """ Raised when an initial connection attempt to the LED fails. """
    def __init__(self, mac, wrapped):
        self.mac = mac
        self.wrapped = wrapped
        super().__init__(f'Failed connecting to {mac}')