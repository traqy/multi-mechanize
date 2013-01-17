class Generator:
    def next(self):
        idx = 0
        while True:
            yield idx
            idx += 1
