from toolbench.sdk import Plugin, CommandError


class Tool(Plugin):
    def __init__(self, context):
        super().__init__(context)
        self.value = 0

    def snapshot(self):
        with self.lock:
            return {'value': self.value}

    def increment(self, amount=1):
        if type(amount) is not int or not 1 <= amount <= 10:
            raise CommandError('amount must be an integer between 1 and 10', 'INVALID_AMOUNT')
        with self.lock:
            self.value += amount
            return {'value': self.value}
