#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
#  Copyright (c) 2010-2012 Corey Goldberg (corey@goldb.org)
#  License: GNU LGPLv3
#
#  This file is part of Multi-Mechanize | Performance Test Framework
#


import multiprocessing
import os
import sys
import threading
import time

from multimechanize.script_loader import ScriptLoader
from multimechanize.script_loader import GeneratorValidator
import os.path

import Pyro4

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


class GeneratorWrapper(threading.Thread):
    """
    wraps a generator script into a standalone Pyro service that provides
    data for user groups. The generator script provided must provide a class named
    Generator implementing either a python generator via a next() method or a key/value getter via a get(key)
    method.
    """

    class GeneratorClient(object):
        def __init__(self, uri):
            self.uri = uri
            self.proxy = Pyro4.Proxy(uri)
        def next(self):
            return self.proxy.next()
        def get(self, key):
            return self.proxy.get(key)

    class GeneratorProxy:
        def __init__(self, obj):
            self._obj = obj
            self.lock = threading.Lock()
            self._gen = obj.next()
        def next(self):
            self.lock.acquire()
            try:
                return self._gen.next()
            finally:
                self.lock.release()

        def get(self, key):
            return self._obj.get(key)

    def __init__(self, script_file):
        """
        """
        threading.Thread.__init__(self)
        self.daemon = True
        self.module = load_script(script_file)
        GeneratorValidator.ensure_module_valid(self.module)
        self.generator = getattr(self.module, "Generator")()
        self.daemon_object = Pyro4.Daemon()
        self.genproxy = GeneratorWrapper.GeneratorProxy(getattr(self.module, "Generator")())
        uri = self.daemon_object.register(self.genproxy)
        self.client = GeneratorWrapper.GeneratorClient(uri)

    def get_client(self):
        return self.client

    def run(self):
        self.daemon_object.requestLoop()

    def terminate(self):
        self.daemon_object.shutdown()




class UserGroup(multiprocessing.Process):
    def __init__(self, queue, process_num, user_group_name, num_threads,
                 script_file, run_time, rampup, generator_client, user_group_global_config):
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
        self.user_group_global_config = user_group_global_config

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
                                 script_module, self.script_file, self.generator_client, self.user_group_global_config)
            agent_thread.daemon = True
            threads.append(agent_thread)
            agent_thread.start()
        for agent_thread in threads:
            agent_thread.join()



class Agent(threading.Thread):
    def __init__(self, queue, process_num, thread_num, start_time, run_time,
                 user_group_name, script_module, script_file, generator_client, user_group_global_config):
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
        self.user_group_global_config = user_group_global_config

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
        trans.user_group_global_config = self.user_group_global_config

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
