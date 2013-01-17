#   this is a data generator virtual user. it progressively sleeps for a longer
#   time based on the value returned by the generator its configured against.


import time

class Transaction(object):
    def __init__(self):
        self.custom_timers = {}

    def run(self):
        n = self.generator.next()
        time.sleep(n)
        self.custom_timers['Example_Timer'] = n


if __name__ == '__main__':
    trans = Transaction()
    trans.run()
    print trans.custom_timers
