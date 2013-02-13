#!/usr/bin/env python
# -*- coding: UTF-8 -*-
#
#  Copyright (c) 2010-2012 Corey Goldberg (corey@goldb.org)
#  License: GNU LGPLv3
#
#  This file is part of Multi-Mechanize | Performance Test Framework
#



import ConfigParser
import multiprocessing
import optparse
import os
# -- NOT-NEEDED: import Queue
import shutil
import subprocess
import sys
import time
import atexit
import traceback

try:
    # installed
    import multimechanize
except ImportError:
    # from dev/source
    this_dir = os.path.abspath(os.path.dirname(__file__))
    sys.path.append(os.path.join(this_dir, '../../'))
    import multimechanize

import multimechanize.core as core
import multimechanize.results as results
import multimechanize.resultswriter as resultswriter
import multimechanize.progressbar as progressbar
from multimechanize import __version__ as VERSION

def main():
    """
    Main function to run multimechanize benchmark/performance test.
    """

    usage = 'Usage: %prog <project name> [options]'
    parser = optparse.OptionParser(usage=usage, version=VERSION)
    parser.add_option('-p', '--port', dest='port', type='int', help='rpc listener port')
    parser.add_option('-r', '--results', dest='results_dir', help='results directory to reprocess')
    parser.add_option('-b', '--bind-addr', dest='bind_addr', help='rpc bind address', default='localhost')
    parser.add_option('-d', '--directory', dest='projects_dir', help='directory containing project folder', default='.')
    cmd_opts, args = parser.parse_args()

    try:
        project_name = args[0]
    except IndexError:
        sys.stderr.write('\nERROR: no project specified\n\n')
        sys.stderr.write('%s\n' % usage)
        sys.stderr.write('Example: multimech-run my_project\n\n')
        sys.exit(1)

    try:
        core.init(cmd_opts.projects_dir, project_name)
        # -- ORIGINAL-MAIN:
        if cmd_opts.results_dir:  # don't run a test, just re-process results
            rerun_results(project_name, cmd_opts, cmd_opts.results_dir)
        elif cmd_opts.port:
            import multimechanize.rpcserver
            multimechanize.rpcserver.launch_rpc_server(cmd_opts.bind_addr, cmd_opts.port, project_name, run_test)
        else:
            run_test(project_name, cmd_opts)
        return
    except Exception, e:
        parser.error(e)

def setup_generators ( projects_dir, project_name, generator_scripts ):
    """
    loads / validates all generators specified by the config file.
    """
    generators = {}
    try:
        for generator in generator_scripts:
            script = generator_scripts[generator]
            generators[generator] = core.GeneratorWrapper(os.path.join(projects_dir, project_name, "generators", script))
            generators[generator].start()
            atexit.register(generators[generator].terminate)
        return generators
    except:
        traceback.print_exc()
        pass
        return {}

def run_test(project_name, cmd_opts, remote_starter=None):
    if remote_starter is not None:
        remote_starter.test_running = True
        remote_starter.output_dir = None

    run_time, rampup, results_ts_interval, console_logging, progress_bar, results_database, pre_run_script, post_run_script, xml_report, user_group_configs, generator_scripts = configure(project_name, cmd_opts)

    # Run setup script
    if pre_run_script is not None:
        cmd = "{0}/{1}/test_scripts/{2}".format(cmd_opts.projects_dir, project_name, pre_run_script)
        print 'Running global pre_run_script: %s\n' % cmd
        subprocess.call( cmd )
    

    run_localtime = time.localtime()
    output_dir = '%s/%s/results/results_%s' % (cmd_opts.projects_dir, project_name, time.strftime('%Y.%m.%d_%H.%M.%S/', run_localtime))

    generators = setup_generators ( cmd_opts.projects_dir, project_name, generator_scripts )
    # this queue is shared between all processes/threads
    queue = multiprocessing.Queue()
    rw = resultswriter.ResultsWriter(queue, output_dir, console_logging)
    rw.daemon = True
    rw.start()
    script_prefix = os.path.join(cmd_opts.projects_dir, project_name, "test_scripts")
    script_prefix = os.path.normpath(script_prefix)

    user_groups = []
    for i, ug_config in enumerate(user_group_configs):
        script_file = os.path.join(script_prefix, ug_config.script_file)
        gen_cli = None
        if ug_config.generator:
            gen_cli = generators[ug_config.generator].get_client()
        ug = core.UserGroup(queue, i, ug_config.name, ug_config.num_threads,
                            script_file, run_time, rampup, gen_cli, ug_config.user_group_global_config)
        user_groups.append(ug)
    for user_group in user_groups:
        user_group.start()
        atexit.register(user_group.terminate)

    start_time = time.time()

    if console_logging:
        for user_group in user_groups:
            user_group.join()
    else:
        print '\n  user_groups:  %i' % len(user_groups)
        print '  threads: %i\n' % (ug_config.num_threads * len(user_groups))

        if progress_bar:
            p = progressbar.ProgressBar(run_time)
            elapsed = 0
            while elapsed < (run_time + 1):
                p.update_time(elapsed)
                if sys.platform.startswith('win'):
                    print '%s   transactions: %i  timers: %i  errors: %i\r' % (p, rw.trans_count, rw.timer_count, rw.error_count),
                else:
                    print '%s   transactions: %i  timers: %i  errors: %i' % (p, rw.trans_count, rw.timer_count, rw.error_count)
                    sys.stdout.write(chr(27) + '[A' )
                time.sleep(1)
                elapsed = time.time() - start_time

            print p

        while [user_group for user_group in user_groups if user_group.is_alive()] != []:
            if progress_bar:
                if sys.platform.startswith('win'):
                    print 'waiting for all requests to finish...\r',
                else:
                    print 'waiting for all requests to finish...\r'
                    sys.stdout.write(chr(27) + '[A' )
            time.sleep(.5)

        if not sys.platform.startswith('win'):
            print

    # all agents are done running at this point
    time.sleep(.2) # make sure the writer queue is flushed
    print '\n\nanalyzing results...\n'
    results.output_results(output_dir, 'results.csv', run_time, rampup, results_ts_interval, user_group_configs, xml_report)
    print 'created: %sresults.html\n' % output_dir
    if xml_report:
        print 'created: %sresults.jtl' % output_dir
        print 'created: last_results.jtl\n'

    # copy config file to results directory
    project_config = os.sep.join([cmd_opts.projects_dir, project_name, 'config.cfg'])
    saved_config = os.sep.join([output_dir, 'config.cfg'])
    shutil.copy(project_config, saved_config)

    if results_database is not None:
        print 'loading results into database: %s\n' % results_database
        import multimechanize.resultsloader
        multimechanize.resultsloader.load_results_database(project_name, run_localtime, output_dir, results_database,
                run_time, rampup, results_ts_interval, user_group_configs)

    if post_run_script is not None:
        cmd = "{0}/{1}/test_scripts/{2}".format(cmd_opts.projects_dir, project_name, post_run_script)
        print 'Running global post_run_script: %s\n' % cmd
        subprocess.call( cmd )

    print 'done.\n'

    if remote_starter is not None:
        remote_starter.test_running = False
        remote_starter.output_dir = output_dir

    return



def rerun_results(project_name, cmd_opts, results_dir):
    output_dir = '%s/%s/results/%s/' % (cmd_opts.projects_dir, project_name, results_dir)
    saved_config = '%s/config.cfg' % output_dir
    #run_time, rampup, results_ts_interval, console_logging, progress_bar, results_database, pre_run_script, post_run_script, xml_report, user_group_configs = configure(project_name, cmd_opts, config_file=saved_config)
    run_time, rampup, results_ts_interval, console_logging, progress_bar, results_database, pre_run_script, post_run_script, xml_report, user_group_configs, generator_scripts = configure(project_name, cmd_opts, config_file=saved_config)
    print '\n\nanalyzing results...\n'
    results.output_results(output_dir, 'results.csv', run_time, rampup, results_ts_interval, user_group_configs, xml_report)
    print 'created: %sresults.html\n' % output_dir
    if xml_report:
        print 'created: %sresults.jtl' % output_dir
        print 'created: last_results.jtl\n'



def configure(project_name, cmd_opts, config_file=None):
    user_group_configs = []
    generator_scripts = {}
    user_group_global_config = {}
    config = ConfigParser.ConfigParser()
    if config_file is None:
        config_file = '%s/%s/config.cfg' % (cmd_opts.projects_dir, project_name)
    config.read(config_file)
    for section in sorted(config.sections()):
        if section == 'global':
            run_time = config.getint(section, 'run_time')
            rampup = config.getint(section, 'rampup')
            results_ts_interval = config.getint(section, 'results_ts_interval')
            try:
                console_logging = config.getboolean(section, 'console_logging')
            except ConfigParser.NoOptionError:
                console_logging = False
            try:
                progress_bar = config.getboolean(section, 'progress_bar')
            except ConfigParser.NoOptionError:
                progress_bar = True
            try:
                results_database = config.get(section, 'results_database')
                if results_database == 'None': results_database = None
            except ConfigParser.NoOptionError:
                results_database = None
            try:
                pre_run_script = config.get(section, 'pre_run_script')
                if pre_run_script == 'None': pre_run_script = None
            except ConfigParser.NoOptionError:
                pre_run_script = None
            try:
                post_run_script = config.get(section, 'post_run_script')
                if post_run_script == 'None': post_run_script = None
            except ConfigParser.NoOptionError:
                post_run_script = None
            try:
                xml_report = config.getboolean(section, 'xml_report')
            except ConfigParser.NoOptionError:
                xml_report = False
        elif section == "user_group_global":
            for option in config.options('user_group_global'):
                option_val =  config.get(section, option)
                user_group_global_config.setdefault(option, option_val)
        elif section == "generators":
            generators = config.options("generators")
            for gen in generators:
                if generator_scripts.has_key(gen):
                    raise AttributeError("multiple configurations found for generator with name : %s" % gen)
                else:
                    generator_scripts[gen] = config.get("generators", gen)

        else:
            threads = config.getint(section, 'threads')
            script = config.get(section, 'script')
            user_group_name = section
            generator = None
            if config.has_option(section, 'generator'):
                generator = config.get(section, 'generator')
                if not generator in generator_scripts.keys():
                    raise AttributeError("generator %s required by user_group %s was not defined in the generators section" % ( generator, user_group_name))

            ug_config = UserGroupConfig(threads, user_group_name, script, generator, user_group_global_config)
            user_group_configs.append(ug_config)
    return (run_time, rampup, results_ts_interval, console_logging, progress_bar, results_database, pre_run_script, post_run_script, xml_report, user_group_configs, generator_scripts)



class UserGroupConfig(object):
    def __init__(self, num_threads, name, script_file, generator, user_group_global_config):
        self.num_threads = num_threads
        self.name = name
        self.script_file = script_file
        self.generator = generator
        self.user_group_global_config = user_group_global_config


if __name__ == '__main__':
    main()
