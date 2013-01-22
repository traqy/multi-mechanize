.. _scripts-label:

Scripting Guide
===============

*******************************
    Virtual User Script Writing
*******************************

Scripts are written in Python. You have full access to the Python 
standard library and any additional modules you have installed.

**************
    The Basics
**************

Each script must implement a ``Transaction()`` class.  This class 
must implement a ``run()`` method.

So a basic test script consists of::

    class Transaction(object):
        def run(self):
            # do something here
            return

During a test run, your ``Transaction()`` class is instantiated once, 
and then its ``run()`` method is called repeatedly in a loop::

    class Transaction(object):

        def __init__(self):
            # do per-user user setup here
            # this gets called once on user creation
            return

        def run(self):
            # do user actions here
            # this gets called repeatedly
            return

******************
    Basic Examples
******************

A full user script that generates HTTP GETs, using ``mechanize``::

    import mechanize

    class Transaction(object):    
        def run(self):
            br = mechanize.Browser()
            br.set_handle_robots(False)    
            resp = br.open('http://www.example.com/')
            resp.read()

This script adds response assertions::

    import mechanize

    class Transaction(object):
        def run(self):
            br = mechanize.Browser()
            br.set_handle_robots(False)
            
            resp = br.open('http://www.example.com/')
            resp.read()
            
            assert (resp.code == 200), 'Bad Response: HTTP %s' % resp.code
            assert ('Example Web Page' in resp.get_data())

This script uses a custom timer. Custom timers are used to wrap 
blocks of code for timing purposes::

    import mechanize
    import time

    class Transaction(object):        
        def run(self):
            br = mechanize.Browser()
            br.set_handle_robots(False)
            
            start_timer = time.time()
            resp = br.open('http://www.example.com/')
            resp.read()
            latency = time.time() - start_timer
            
            self.custom_timers['Example_Homepage'] = latency

*********************
    Advanced Examples
*********************

Wikipedia search with form fill/submit, timers, assertions, custom headers, think-times::

    import mechanize
    import time


    class Transaction(object):
        
        def __init__(self):
            pass

        def run(self):
            # create a Browser instance
            br = mechanize.Browser()
            # don't bother with robots.txt
            br.set_handle_robots(False)
            # add a custom header so wikipedia allows our requests
            br.addheaders = [('User-agent', 'Mozilla/5.0 Compatible')]
            
            # start the timer
            start_timer = time.time()
            # submit the request
            resp = br.open('http://www.wikipedia.org/')
            resp.read()
            # stop the timer
            latency = time.time() - start_timer
            
            # store the custom timer
            self.custom_timers['Load_Front_Page'] = latency  
            
            # verify responses are valid
            assert (resp.code == 200), 'Bad Response: HTTP %s' % resp.code
            assert ('Wikipedia, the free encyclopedia' in resp.get_data())
            
            # think-time
            time.sleep(2)  
            
            # select first (zero-based) form on page
            br.select_form(nr=0)
            # set form field        
            br.form['search'] = 'foo'  
            
            # start the timer
            start_timer = time.time()
            # submit the form
            resp = br.submit()  
            resp.read()
            # stop the timer
            latency = time.time() - start_timer
            
            # store the custom timer
            self.custom_timers['Search'] = latency  
            
            # verify responses are valid
            assert (resp.code == 200), 'Bad Response: HTTP %s' % resp.code
            assert ('foobar' in resp.get_data()), 'Text Assertion Failed'
            
            # think-time
            time.sleep(2)

this example generates HTTP GETs, using ``urllib2``::

    import urllib2
    import time

    class Transaction(object):
        def run(self):
            start_timer = time.time()
            resp = urllib2.urlopen('http://www.example.com/')
            content = resp.read()
            latency = time.time() - start_timer
            
            self.custom_timers['Example_Homepage'] = latency
            
            assert (resp.code == 200), 'Bad Response: HTTP %s' % resp.code
            assert ('Example Web Page' in content), 'Text Assertion Failed'
        
this example generates HTTP POSTs containing a SOAP request in its body, using ``urllib2``. 
The request message (SOAP envelope) is read from a file::

    import urllib2
    import time

    class Transaction(object):
        def __init__(self):
            self.custom_timers = {}
            with open('soap.xml') as f:
                self.soap_body = f.read()
        
        def run(self):
            req = urllib2.Request(url='http://www.foo.com/service', data=self.soap_body)
            req.add_header('Content-Type', 'application/soap+xml')
            req.add_header('SOAPAction', 'http://www.foo.com/action')

            start_timer = time.time()
            resp = urllib2.urlopen(req)
            content = resp.read()
            latency = time.time() - start_timer
            
            self.custom_timers['Example_SOAP_Msg'] = latency
            
            assert (resp.code == 200), 'Bad Response: HTTP %s' % resp.code
            assert ('Example SOAP Response' in content), 'Text Assertion Failed'

this example generates HTTP POSTs, using ``httplib``::

    import httplib
    import urllib
    import time


    class Transaction(object):
        def __init__(self):
            self.custom_timers = {}
        
        def run(self):
            post_body=urllib.urlencode({
                'USERNAME': 'corey',
                'PASSWORD': 'secret',})
            headers = {'Content-type': 'application/x-www-form-urlencoded'}            
            
            start_timer = time.time()
            conn = httplib.HTTPConnection('www.example.com')
            conn.request('POST', '/login.cgi', post_body, headers)
            resp = conn.getresponse()
            content = resp.read()
            latency = time.time() - start_timer
            
            self.custom_timers['LOGIN'] = latency
            assert (resp.status == 200), 'Bad Response: HTTP %s' % resp.status
            assert ('Example Web Page' in content), 'Text Assertion Failed'
        
this example generates HTTP GETs, using httplib, with detailed timing::

    import httplib
    import time

    class Transaction(object):
        def run(self):
            conn = httplib.HTTPConnection('www.example.com')
            start = time.time()
            conn.request('GET', '/')
            request_time = time.time()
            resp = conn.getresponse()
            response_time = time.time()
            conn.close()     
            transfer_time = time.time()
            
            self.custom_timers['request sent'] = request_time - start
            self.custom_timers['response received'] = response_time - start
            self.custom_timers['content transferred'] = transfer_time - start
            
            assert (resp.status == 200), 'Bad Response: HTTP %s' % resp.status


    if __name__ == '__main__':
        trans = Transaction()
        trans.run()
        
        for timer in ('request sent', 'response received', 'content transferred'):
            print '%s: %.5f secs' % (timer, trans.custom_timers[timer])



*********************************
    Data Generator Script Writing
*********************************

Data generators can be used for communicating test data to virtual user scripts. This data can either be shared by all user groups or be made available to specific groups.
The basic requirement of a data generator is a plain python script that implements atleast one of :meth:`Generator.get` or :meth:`Generator.next` (must return a python generator object). As expected the next method 
provides the semantics of a the virtual user scripts consuming a queue of test data, and the get method provides a dictionary look up. 



Examples
~~~~~~~~

A generator that provides line by line access (lines.py)::

    class Generator:
        def next(self):
            fp = open("/var/log/system.log","r")
            for line in fp:
                yield line 

The virtual user script that consumes this data (line_consumer.py)::


    class Transaction:
        def run(self):
            assert len(self.generator.next()) > 0

A generator that provides both a queue and key/value lookup (logs.py)::

    import math 

    class Generator:
        def __init__(self):
            self.data = dict( (k, math.log(k)) for k in range(1,100000))
        def next(self):
            for k,v in self.data.items():
                yield k,v 
        def get(self, key):
            return self.data[key]


The virtual user script that consumes this data ( log_consumer.py )::
    
    import time
    class Transaction:
        def __init__(self):
            self.counter = 1
        
        def run(self):
            time.sleep( self.generator.get(self.counter) )
            self.counter += 1

The generator is mapped to user groups via the config file. Each named generator in the ``[generators]`` section is initialized only once regardless of the number of user groups referencing them. 
If the intention is to have per user group generators, then the same generator script can be referenced multiple times in the ``[generators]`` section with a unique name for each user group to reference. 
The example below shows a combined use case::


    [generators]
    line_feed = lines.py 
    line_feed_2 = lines.py 
    log = logs.py 

    [user-group-1]
    script = line_consumer.py 
    threads = 10
    generator = line_feed 

    [user-group-2]
    script = line_consumer.py 
    threads = 10 
    generator = line_feed_2 

    [user-group-3]
    script = line_consumer.py 
    threads = 10 
    generator = line_feed 

    [user-group-4]
    script = log_consumer.py 
    threads = 10 
    generator = log 
