"""Metadata-only plugin message catalogs. Never translate protocol or user data."""
import re

LOCALES = ('zh-CN', 'en-US')


def validate_localization(value):
    if not isinstance(value, dict) or set(value) != {'defaultLocale', 'messages'} or value['defaultLocale'] not in LOCALES:
        raise ValueError('localization requires defaultLocale and messages')
    messages = value['messages']
    if not isinstance(messages, dict) or set(messages) - set(LOCALES):
        raise ValueError('Unsupported plugin message locale')
    for catalog in messages.values():
        if not isinstance(catalog, dict) or len(catalog) > 2000:
            raise ValueError('Plugin messages must be a dictionary with at most 2000 entries')
        for source, translated in catalog.items():
            if not isinstance(source, str) or not source.strip() or not isinstance(translated, str) or not translated.strip() or max(len(source), len(translated)) > 16000:
                raise ValueError('Plugin messages must contain nonempty text')
            if set(re.findall(r'\{(\w+)\}', source)) != set(re.findall(r'\{(\w+)\}', translated)):
                raise ValueError('Plugin translation interpolation parameters must match')


def translate(localization, locale, message, values=None):
    catalog = localization.get('messages', {}).get(locale, {})
    text = catalog.get(message, message)
    parameters = values or {}
    return re.sub(r'\{(\w+)\}', lambda match: str(parameters.get(match[1], match[0])), text)
