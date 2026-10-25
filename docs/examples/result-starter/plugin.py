"""Return ordinary JSON data; Cove owns layout, styling and pagination."""
from collections import Counter
import re
from toolbench.sdk import Plugin


class Tool(Plugin):
    def analyze(self, text=''):
        if not isinstance(text, str) or len(text) > 20_000:
            raise ValueError('文本必须是最多 20000 字符的字符串')
        words = re.findall(r'\w+', text.casefold())
        counts = Counter(words)
        return {
            'characters': len(text), 'words': len(words), 'unique': len(counts),
            'frequencies': [{'word': word, 'count': count}
                            for word, count in counts.most_common()],
        }
