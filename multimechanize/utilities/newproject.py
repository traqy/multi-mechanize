#!/usr/bin/env python
#
#  Copyright (c) 2010-2012 Corey Goldberg (corey@goldb.org)
#  License: GNU LGPLv3
#
#  This file is part of Multi-Mechanize | Performance Test Framework
#


import os
import sys


CONFIG_NAME = 'config.cfg'
SCRIPT_NAME = 'v_user.py'
SCRIPTS_DIR = 'test_scripts'
SETUP_ENV_SCRIPT_NAME = 'setup_env.py'
TEARDOWN_ENV_SCRIPT_NAME = "teardown_env.py"


CONFIG_CONTENT = """
[global]
run_time = 30
rampup = 0
results_ts_interval = 10
progress_bar = on
console_logging = off
xml_report = off
pre_run_script = setup_env.py
post_run_script = teardown_env.py

[user_group-1]
threads = 3
script = %s

[user_group-2]
threads = 3
script = %s

""" % (SCRIPT_NAME, SCRIPT_NAME)


SCRIPT_CONTENT = """
import mechanize
import time
 
class Transaction:
    def __init__(self):
        self.custom_timers = {}
    def run(self):        
        start_timer = time.time()
 
        self.story()
 
        latency = time.time() - start_timer        
        self.custom_timers['Example_Homepage'] = latency
 
    def story(self):
        br = mechanize.Browser()
        br.set_handle_robots(False)
        resp = br.open('http://www.example.com/')
        resp.read()        
 
if __name__ == '__main__':
    trans = Transaction()
    trans.run()
    print trans.custom_timers
"""

SETUP_ENV_SCRIPT_CONTENT = """#!/usr/bin/env python

class Transaction(object):
 
    def run(self):
        # Initializations of your test project environment should be done such as the following:
        #  * Initialize data on database engine such as MySQL if your test cases require presetup data on database backend
        #  * Generate and populate huge data to a filesystem storage
        foo="setup your environment logic here"
 
if __name__ == '__main__':
    trans = Transaction()
    trans.run()
"""

TEARDOWN_ENV_SCRIPT_CONTENT = """#!/usr/bin/env python

class Transaction(object):
 
    def run(self):
        # Teardown logic must be specified here such deleting data created by the setup_env.py or created during the multimech-run project.
        bar="Define your story logic here on how to destroy your environment."
 
if __name__ == '__main__':
    trans = Transaction()
    trans.run()
"""

def create_project(
        project_name,
        config_name=CONFIG_NAME,
        script_name=SCRIPT_NAME,
        scripts_dir=SCRIPTS_DIR,
        config_content=CONFIG_CONTENT,
        script_content=SCRIPT_CONTENT,

        script_setup_env_name=SETUP_ENV_SCRIPT_NAME,
        script_setup_env_content=SETUP_ENV_SCRIPT_CONTENT,
        script_teardown_env_name=TEARDOWN_ENV_SCRIPT_NAME,
        script_teardown_env_content=TEARDOWN_ENV_SCRIPT_CONTENT

    ):
    if os.path.exists(project_name):
        sys.stderr.write('\nERROR: project already exists: %s\n\n' % project_name)
        sys.exit(1)
    try:
        os.makedirs(project_name)
        os.makedirs(os.path.join(project_name, scripts_dir))
    except OSError as e:
        sys.stderr.write('\nERROR: can not create directory for %r\n\n' % project_name)
        sys.exit(1)
    with open(os.path.join(project_name, config_name), 'w') as f:
        f.write(config_content)
    with open(os.path.join(project_name, scripts_dir, script_name), 'w') as f:
        f.write(script_content)
    with open(os.path.join(project_name, scripts_dir, script_setup_env_name), 'w') as f:
        f.write(script_setup_env_content)
    os.chmod(os.path.join(project_name, scripts_dir, script_setup_env_name), 0755 )
    with open(os.path.join(project_name, scripts_dir, script_teardown_env_name), 'w') as f:
        f.write(script_teardown_env_content)
    os.chmod(os.path.join(project_name, scripts_dir, script_teardown_env_name), 0755 )


def main():
    try:
        project_name = sys.argv[1]
    except IndexError:
        sys.stderr.write('\nERROR: no project specified\n\n')
        sys.stderr.write('Usage: multimech-newproject <project name>\n\n')
        sys.exit(1)

    create_project(project_name)


if __name__ == '__main__':
    main()
