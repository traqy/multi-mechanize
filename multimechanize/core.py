#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
#  Copyright (c) 2010-2012 Corey Goldberg (corey@goldb.org)
#  License: GNU LGPLv3
#
#  This file is part of Multi-Mechanize | Performance Test Framework
#


import multiprocessing
import socket
import os
import urllib2
import json
import sys
import threading
import time

from multimechanize.script_loader import ScriptLoader
from multimechanize.script_loader import GeneratorValidator
import os.path

import bottle


def init(projects_dir, project_name):
    """
    Sanity check that all test scripts can be loaded.
    """
    scripts_path = '%s/%s/test_scripts' % (projects_dir, project_name)
    if not os.path.exists(scripts_path):
        sys.stderr.write('\nERROR: can not find project: %s\n\n' % project_name)
        sys.exit(1)
    # -- NORMAL-CASE: Ensure that all scripts can be loaded (at program start).
    ScriptLoader.load_all(scripts_path, validate=True)

def load_script(script_file):
    """
    load a test scripts as python module.
    :returns: imported script as python module.
    """
    module = ScriptLoader.load(script_file)
    # -- skip-here: scriptvalidator.ensure_module_valid(module)
    # note: performed above in scriptloader.load_all() at process start.
    return module


class GeneratorWrapper(multiprocessing.Process, bottle.Bottle):
    """
    wraps a generator script into a standalone web service that provides
    data for user groups. The generator script provided must provide a class named
    Generator implementing either a python generator via a next() method or a key/value getter via a get(key)
    method.
    """
    class DataGeneratorError(Exception):
        pass

    class GeneratorClient(object):
        """
        client class to consume data from the webservice provided by :class:`GeneratorWrapper`
        this client class will be assigned to each Transaction as a the :attr:`generator` member.
        """
        def __init__(self, url):
            self.url = url
        def __get_repsonse__(self, url):
            try:
                data = urllib2.urlopen(url).read()
                try:
                    json_data = json.loads(data)
                    if json_data.has_key("error"):
                        raise GeneratorWrapper.DataGeneratorError(json_data["error"])
                    else:
                        return json_data["data"]
                except Exception,e:
                    raise GeneratorWrapper.DataGeneratorError(e.message)
            except GeneratorWrapper.DataGeneratorError,e:
                raise e
            except Exception,e:
                raise GeneratorWrapper.DataGeneratorError("unknown error")


        def next(self):
            return self.__get_repsonse__(self.url)

        def get(self, key):
            return self.__get_repsonse__(self.url + "?key=%s" % key)

    def __init__(self, script_file):
        """
        """
        self.module = load_script(script_file)
        GeneratorValidator.ensure_module_valid(self.module)
        self.generator = getattr(self.module, "Generator")()
        multiprocessing.Process.__init__(self)
        bottle.Bottle.__init__(self)
        self.next = None
        self.port = self.next_free_port()
        self.client = GeneratorWrapper.GeneratorClient("http://localhost:%s/data" % self.port)

    def __get_next__(self):
        if not self.next:
            self.next = self.generator.next()
        return self.next.next()

    def __get_key__(self, key):
        return self.generator.get(key)

    def __router__(self):
        try:
            if bottle.request.GET.get("key"):
                return {"data":self.__get_key__(bottle.request.GET.get("key"))}
            else:
                return {"data":self.__get_next__()}
        except StopIteration, e:
            return {"error": "no more data in generator"}
        except AttributeError, e:
            return {"error": "%s:%s" % (str(self.module.__name__), e)}
        except Exception, e:
            return {"error": str(e)}

    def run(self):
        self.route("/data/")(self.__router__)
        self.route("/data")(self.__router__)
        bottle.Bottle.run(self, port = self.port, quiet=True)

    def next_free_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
        port = s.getsockname()[1]
        s.close()
        return port



class UserGroup(multiprocessing.Process):
    def __init__(self, queue, process_num, user_group_name, num_threads,
                 script_file, run_time, rampup, generator_client):
        multiprocessing.Process.__init__(self)
        self.queue = queue
        self.process_num = process_num
        self.user_group_name = user_group_name
        self.num_threads = num_threads
        self.script_file = script_file
        self.run_time = run_time
        self.rampup = rampup
        self.start_time = time.time()
        self.generator_client = generator_client

    def run(self):
        # -- ENSURE: (Re-)Import script_module in forked Process
        script_module = load_script(self.script_file)
        threads = []
        for i in range(self.num_threads):
            spacing = float(self.rampup) / float(self.num_threads)
            if i > 0:
                time.sleep(spacing)
            agent_thread = Agent(self.queue, self.process_num, i,
                                 self.start_time, self.run_time,
                                 self.user_group_name,
                                 script_module, self.script_file, self.generator_client)
            agent_thread.daemon = True
            threads.append(agent_thread)
            agent_thread.start()
        for agent_thread in threads:
            agent_thread.join()



class Agent(threading.Thread):
    def __init__(self, queue, process_num, thread_num, start_time, run_time,
                 user_group_name, script_module, script_file, generator_client):
        threading.Thread.__init__(self)
        self.queue = queue
        self.process_num = process_num
        self.thread_num = thread_num
        self.start_time = start_time
        self.run_time = run_time
        self.user_group_name = user_group_name
        self.script_module = script_module
        self.script_file   = script_file
        self.generator_client = generator_client

        # choose most accurate timer to use (time.clock has finer granularity
        # than time.time on windows, but shouldn't be used on other systems).
        if sys.platform.startswith('win'):
            self.default_timer = time.clock
        else:
            self.default_timer = time.time


    def run(self):
        elapsed = 0
        trans = self.script_module.Transaction()
        trans.custom_timers = {}
        trans.generator = self.generator_client
        # scripts have access to these vars, which can be useful for loading unique data
        trans.thread_num = self.thread_num
        trans.process_num = self.process_num

        while elapsed < self.run_time:
            error = ''
            start = self.default_timer()

            try:
                trans.run()
            except Exception, e:  # test runner catches all script exceptions here
                error = str(e).replace(',', '')

            finish = self.default_timer()

            scriptrun_time = finish - start
            elapsed = time.time() - self.start_time

            epoch = time.mktime(time.localtime())

            fields = (elapsed, epoch, self.user_group_name, scriptrun_time, error, trans.custom_timers)
            self.queue.put(fields)
