import threading
from collections import defaultdict


class Cache(object):

    def __init__(self):
        self.locks = defaultdict(threading.Lock)
        self.items = {}

    def get(self, key, func, *args, **kwargs):
        with self.locks[key]:
            try:
                item = self.items[key]
                if isinstance(item, Exception):
                    raise item
                return item
            except KeyError:
                try:
                    item = func(*args, **kwargs)
                except Exception as e:
                    item = e
                self.items[key] = item
                return item
