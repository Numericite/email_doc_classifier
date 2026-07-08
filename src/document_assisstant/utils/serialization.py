from datetime import datetime, date


def serialize(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, 'email_address'):
        return {'name': getattr(value, 'name', None),
                'email': value.email_address}
    return value