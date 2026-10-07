"""One lossless canonical representation for model transport and identities."""
import hashlib
import json


def canonical_json(value):
    def check(item):
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError('canonical_json_requires_string_keys')
            for child in item.values():
                check(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                check(child)
    check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def canonical_hash(value):
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()
