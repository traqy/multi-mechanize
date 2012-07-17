#!/usr/bin/env python
#
#  Copyright (c) 2010 Corey Goldberg (corey@goldb.org)
#  License: GNU LGPLv3
#
#  This file is the global setup pre_run_script
#



class Transaction(object):

    def run(self):
        print "Setup pre_run_script works!"


if __name__ == '__main__':
    trans = Transaction()
    trans.run()
