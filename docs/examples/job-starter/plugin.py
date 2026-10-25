"""A hardware-free job example. Only the callback contains business logic."""
import hashlib

from toolbench.sdk import BackgroundJob, CommandError, Plugin


class Tool(Plugin):
    def __init__(self, context):
        super().__init__(context)
        self.job = BackgroundJob(context)

    def run(self, text='Hello Cove', batches=50):
        if not isinstance(text, str) or not 1 <= len(text) <= 10000:
            raise CommandError('请输入 1–10000 个字符。', 'INVALID_TEXT')
        if type(batches) is not int or not 1 <= batches <= 500:
            raise CommandError('批次数必须为 1–500 的整数。', 'INVALID_BATCHES')

        def process(control):
            digest = hashlib.sha256()
            for index in range(batches):
                control.check_cancelled()
                digest.update(text.encode('utf-8'))
                # An interruptible delay makes progress visible in this demo.
                # Real I/O should have its own timeout and cancellation support.
                control.wait(0.02)
                control.update(completed=index + 1, message=f'已处理 {index + 1} / {batches} 批')
            return {'message': f'已完成 {batches} 批文本处理。SHA-256：{digest.hexdigest()}'}

        return self.job.start(process, total=batches, message='准备处理文本…')

    def snapshot(self):
        return self.job.snapshot()

    def cancel(self):
        return self.job.cancel()

    def close(self):
        self.job.close()
