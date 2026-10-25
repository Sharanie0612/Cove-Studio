"""Bounded NDJSON input shared by desktop, worker and portable transports.

Limits count UTF-8 bytes excluding LF and its optional preceding CR. An
oversized frame ends the input session: draining an unbounded line could keep
the reader occupied forever, and treating its remainder as a request is unsafe.
Only the limit is exposed in errors, never any part of the rejected input.
"""

MCP_FRAME_BYTES = 128 * 1024
# Existing tool results may occupy 16 MiB of serialized JSON. Allow the same
# result in either direction of the SDK bridge, plus its transport envelope.
RUNTIME_FRAME_BYTES = 16 * 1024 * 1024 + 64 * 1024
READ_CHUNK_BYTES = 64 * 1024


class FrameTooLarge(ValueError):
    code = 'FRAME_TOO_LARGE'

    def __init__(self, limit_bytes):
        self.limit_bytes = limit_bytes
        super().__init__(f'Protocol frame exceeds {limit_bytes} UTF-8 bytes')

    def details(self):
        return {'code': self.code, 'limitBytes': self.limit_bytes}


def read_frames(stream, limit_bytes):
    """Yield complete text or binary frames using only bounded readline calls.

Text streams are counted by their UTF-8 encoding, not Python character count.
    Each temporary encoding is at most four bytes per requested character. No
    whole rejected frame is joined or decoded, including when the sender never
    supplies a newline.
"""
    if not isinstance(limit_bytes, int) or limit_bytes < 1:
        raise ValueError('Frame limit must be a positive integer')
    while True:
        parts, size = [], 0
        while True:
            # Two extra bytes permit an exact-boundary frame followed by CRLF.
            part = stream.readline(min(READ_CHUNK_BYTES, limit_bytes - size + 2))
            binary = isinstance(part, bytes)
            newline, carriage = (b'\n', b'\r') if binary else ('\n', '\r')
            if not part:
                if not parts:
                    return
                if size > limit_bytes:
                    raise FrameTooLarge(limit_bytes)
                yield (b'' if binary else '').join(parts)
                return
            size += len(part) if binary else len(part.encode('utf-8'))
            ended = part.endswith(newline)
            if ended:
                part = part[:-1]
            parts.append(part)
            # CR can fall in the preceding chunk when the final read is LF.
            last = part or (parts[-2] if len(parts) > 1 else part)
            payload_size = size - int(ended) - int(ended and last.endswith(carriage))
            if payload_size > limit_bytes:
                if not ended and size == limit_bytes + 1 and part.endswith(carriage):
                    continue
                raise FrameTooLarge(limit_bytes)
            if ended:
                line = (b'' if binary else '').join(parts)
                yield line[:-1] if line.endswith(carriage) else line
                break
