import os
import json
#from threading import Lock
import threading

class FileQueue:
    def __init__(self, filename="queue.json"):
        self.filename = filename
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            with open(self.filename, "r") as f:
                self.queue = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.queue = []

    def _save(self):
        with open(self.filename, "w") as f:
            json.dump(self.queue, f)

    def enqueue(self, item):
        print('Enqueue:' + str(item))
        with self.lock:
            self.queue.append(item)
            self._save()

    def dequeue(self):
        with self.lock:
            if not self.is_empty():
                item = self.queue.pop(0)
                self._save()
                return item
            return None

    def peek(self):
         with self.lock:
            return self.queue[0]

    def is_empty(self):        
        return len(self.queue) == 0

    def size(self):
        with self.lock:
            return len(self.queue)
if __name__ == "__main__":       
    q = FileQueue('batchQueue.json')
    for item in ['c9a2980a-5496-4da2-9d79-e5fe7cf78483','b67dc4f9-c321-4c5b-8ae5-c099f16c5ade','af53bd2a-7cd3-456b-8fda-3ba9401d2213']:        
        data = {'id': item}
    #     q.enqueue( json.dumps(data) )
    for data in q.dequeue():
        print( q.size() )


