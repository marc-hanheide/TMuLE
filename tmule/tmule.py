#! /usr/bin/env python
from __future__ import print_function, absolute_import

from libtmux import Server
from yaml import load
from logging import error, warning, info, debug, basicConfig, INFO
from pprint import pformat
from time import sleep
import signal
import os
import sys
from os import path
import argparse
from subprocess import call
from psutil import Process, wait_procs
import sys
from .loader import Loader
from threading import Thread
from datetime import datetime
from os.path import abspath, dirname

basicConfig(level=INFO)

sys.path.append(os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..'))
)


class TMux:

    def __init__(self, session_name=None, configfile=None, sleep_sec=0.0):
        self.session_name = 'tmule'
        self.configfile = configfile
        if self.configfile:
            self.load_config()
            if 'session' in self.config:
                self.session_name = self.config['session']
        else:
            self.config = None
        if session_name:
            self.session_name = session_name
        self.sleep_sec = sleep_sec
        # max number of loops to wait for process to come up
        self.maxCheckLoops = 16
        # time to wait between checks (factor multiplied by loop)
        self.sleepCheckLoop = 1

    def _on_terminate(self, proc):
        info("process {} terminated with exit code {}"
             .format(proc, proc.returncode))

    def _terminate(self, pid):
        procs = Process(pid).children(recursive=True)
        for p in procs:
            info("trying to terminate %s" % p)
            p.terminate()
        _, still_alive = wait_procs(procs, timeout=1,
                                       callback=self._on_terminate)
        for p in still_alive:
            info("killing %s" % p)
            p.kill()

    def _get_children_pids(self, pid):
        return Process(pid).children(recursive=True)

    def var_substitute(self, root):
        if type(root) == dict:
            for d in root:
                root[d] = self.var_substitute(root[d])
        elif type(root) == list:
            for l in range(0, len(root)):
                root[l] = self.var_substitute(root[l])
        elif type(root) == str:
            for vs in self.var_dict:
                root = root.replace(
                    '@%s@' % vs,
                    self.var_dict[vs])
        return root

    def load_config(self):
        with open(self.configfile) as data_file:
            self.config = load(data_file, Loader)
            self.var_dict = {
                'TMULE_CONFIG_FILE': abspath(self.configfile),
                'TMULE_CONFIG_DIR': dirname(abspath(self.configfile)),
                'TMULE_SESSION_NAME': self.session_name
            }
            self.config = self.var_substitute(self.config)
            self.known_tags = set([])
            for w in self.config['windows']:
                if 'tags' in w:
                    for t in w['tags']:
                        self.known_tags.add(t)

    def init(self):
        if not self.config:
            error('config file not loaded; call "load_config" first!')
        else:
            self.server = Server()
            if self.server.has_session(self.session_name):
                self.session = self.server.find_where({
                    "session_name": self.session_name
                })

                debug('found running session %s on server' % self.session_name)
            else:
                info('starting new session %s on server' % self.session_name)
                self.session = self.server.new_session(
                    session_name=self.session_name
                )

            for win in self.config['windows']:
                # print win, "***", self.config['windows']
                window = self.session.find_where({
                    "window_name": win['name']
                })
                if window:
                    debug('window %s already exists' % win['name'])
                else:
                    info('create window %s' % win['name'])
                    window = self.session.new_window(win['name'])
                exist_num_panes = len(window.list_panes())
                while exist_num_panes < len(win['panes']):
                    info('new pane needed in window %s' % win['name'])
                    window.split_window(vertical=1)
                    exist_num_panes = len(window.list_panes())
                window.cmd('select-layout', 'tiled')

    def find_window(self, window_name):
        for win in self.config['windows']:
            if win['name'] == window_name:
                window = self.session.find_where({
                    "window_name": win['name']
                })
                # window.select_window()
                return win, window

    def send_ctrlc(self, pane):
        datestr = datetime.now().strftime('%c')
        pane.cmd("send-keys", "", "C-c")
        pane.cmd("send-keys", "", "C-c")
        pane.cmd("send-keys", "", "C-c")
        pane.send_keys('# tmux-controller sent Ctrl-C at %s' % datestr,
                       enter=True, suppress_history=True)

    def launch_window(self, window_name, enter=True):
        info('launch %s' % window_name)
        winconf, window = self.find_window(window_name)
        pane_no = 0
        datestr = datetime.now().strftime('%c')
        for cmd in winconf['panes']:
            pane = window.select_pane('%s:%s.%d' % (
                window.session.name, window_name, pane_no))
            debug('pane: %d -> %s' % (pane_no, pane))
            self.send_ctrlc(pane)
            pane.send_keys('# tmux-controller starts new command %s' % datestr,
                           enter=True, suppress_history=True)
            if 'init_cmd' in self.config:
                pane.send_keys(self.config['init_cmd'],
                               enter=enter, suppress_history=False)
            pane.send_keys(cmd, enter=enter, suppress_history=False)
            pane_no += 1
        winconf['_running'] = True

    def launch_all_windows(self, tags=set([])):
        for winconf in self.config['windows']:
            selected = 'skip' not in winconf or not winconf['skip']
            if selected and tags:
                if 'tags' in winconf:
                    selected = set(winconf['tags']).intersection(tags)
                else:
                    selected = False
            if selected:
                self.launch_window(winconf['name'])
                w = self.sleep_sec
                if 'wait' in winconf:
                    w = float(winconf['wait'])
                if w > 0:
                    info('sleep %f seconds after launch of %s' % (
                        w, winconf['name']))
                    sleep(w)
                if 'check' in winconf:
                    debug('need to run check command')
                    running = False
                    loop = 0
                    check_cmd = '\n'
                    if 'init_cmd' in self.config:
                        check_cmd += self.config['init_cmd'] + '\n'
                    check_cmd += winconf['check']

                    while not running and loop < self.maxCheckLoops:
                        loop += 1
                        sleep(loop * self.sleepCheckLoop)
                        #running = (call(winconf['check'], shell=True) == 0)
                        running = (call(
                            check_cmd, executable='/bin/bash', shell=True, stdout=None,
                            stdin=None) == 0)
                        info('ran check for %s (loop %d) => %s' % (
                            winconf['name'], loop, running))
                    if loop >= self.maxCheckLoops:
                        error(
                            'window %s failed to come up in time, '
                            'not continuing launch.'
                            % winconf['name'])
                        break

    def stop_all_windows(self, tags=set([])):
        for winconf in self.config['windows'][::-1]:
            selected = 'skip' not in winconf or not winconf['skip']
            if selected and tags:
                if 'tags' in winconf:
                    selected = set(winconf['tags']).intersection(tags)
            if selected:
                self.stop_window(winconf['name'])

    def get_children_pids_all_windows(self):
        pids = []
        for winconf in self.config['windows']:
            pids.extend(
                self.get_children_pids_window(winconf['name'])
            )
        return pids

    def kill_all_windows(self):
        for winconf in self.config['windows'][::-1]:
            try:
                self.kill_window(winconf['name'])
            except Exception as e:
                warning(
                    'There was an exception shutting down, '
                    'carrying on regardless: %s' % str(e))
        self.server.kill_session(self.session_name)

    def stop_window(self, window_name):
        info('stop %s' % window_name)
        winconf, window = self.find_window(window_name)
        self._stop_window(winconf, window)

    def __pids_clean_up(self, pids):
        sleep(1)
        for p in pids:
            try:
                self._terminate(p)
            except Exception as e:
                info('exception in termination, can be ignored: %s' % str(e))

    def _stop_window(self, winconf, window):
        pane_no = 0
        for _ in winconf['panes']:
            pane = window.select_pane('%s:%s.%d' % (
                window.session.name, window.name, pane_no))
            self.send_ctrlc(pane)
            pane_no += 1
        pids = self._get_pids_window(window)
        Thread(target=self.__pids_clean_up, args=(pids,)).start()
        #for p in pids:
           #self._terminate(p)
        winconf['_running'] = False

    def kill_window(self, window_name):
        info('terminate %s' % window_name)
        winconf, window = self.find_window(window_name)
#                       "-F '#{pane_active} #{pane_pid}")
        self._stop_window(winconf, window)
        pids = self._get_pids_window(window)
        sleep(1)
        Thread(target=self.__pids_clean_up, args=(pids,)).start()
        winconf['_running'] = False

    def list_windows(self):
        return [w['name'] for w in self.config['windows']]

    def get_pids_window(self, window_name):
        winconf, window = self.find_window(window_name)
        return self._get_pids_window(window)

    def _get_pids_window(self, window):
        r = window.cmd('list-panes',
                       "-F #{pane_pid}")
        return [int(p) for p in r.stdout]

    def get_children_pids_window(self, window_name):
        _, window = self.find_window(window_name)
        return self._get_children_pids_window(window)

    def _get_children_pids_window(self, window):
        winpids = self._get_pids_window(window)
        pids = []
        for pid in winpids:
            pids.extend(self._get_children_pids(pid))
        return [p.pid for p in pids]

    def is_running(self, window_name):
        winconf, window = self.find_window(window_name)
        pids = self._get_children_pids_window(window)
        if len(pids) < 1:
            return False
        if 'check' in winconf:
            debug('need to run check command')
            check_cmd = '\n'
            if 'init_cmd' in self.config:
                check_cmd += self.config['init_cmd'] + '\n'
            check_cmd += winconf['check']
            running = (call(
                check_cmd, executable='/bin/bash', shell=True, stdout=None,
                stdin=None) == 0)
            return running
        else:
            return True

    def _server(self, port=9999, keepalive=True):
        from .ws_protocol import JsonWSProtocol
        import web
        from web.httpserver import StaticMiddleware, StaticApp

        from autobahn.twisted.websocket import WebSocketServerProtocol, \
            WebSocketServerFactory
        from autobahn.twisted.resource import WebSocketResource, WSGIRootResource

        from twisted.internet import reactor
        from twisted.web.server import Site
        from twisted.web.wsgi import WSGIResource
        from twisted.python import log
        from twisted.web.static import File

        tmux_self = self

        class TMuxWebServer(web.auto_application):

            def __init__(self):

                web.auto_application.__init__(
                    self
                )

                self._renderer = web.template.render(
                    path.realpath(
                        path.join(
                            path.dirname(__file__),
                            'www'
                        )
                    ),
                    base="base", globals=globals())

                self_app = self

                class Index(self.page):
                    path = '/'

                    def GET(self):
                        tmux_self.load_config()
                        tmux_self.init()
                        ws_uri = '%s://%s%sws' % (
                            'ws' if web.ctx['protocol'] == 'http' else 'wss',
                            web.ctx['host'],
                            web.ctx['fullpath']
                        )
                        return self_app._renderer.index(
                            ws_uri,
                            tmux_self.config, tmux_self.known_tags)

                class Log(self.page):
                    path = '/log'

                    def GET(self):
                        lines = tmux_self.server.cmd(
                            'capture-pane', '-p', '-C', '-S', '-100000').stdout
                        return '\n'.join(lines)

        class TMuxWSProtocol(JsonWSProtocol):

            def __init__(self):
                super(TMuxWSProtocol, self).__init__()

            def on_button(self, payload):
                debug('button pressed: \n%s' % pformat(payload))
                window_name = payload['id']
                cmd = payload['cmd']
                if cmd == 'launch':
                    if window_name == '':
                        tmux_self.launch_all_windows()
                    else:
                        tmux_self.launch_window(window_name)
                elif cmd == 'launch-tag':
                    tmux_self.launch_all_windows(tags={window_name})
                elif cmd == 'stop':
                    if window_name == '':
                        tmux_self.stop_all_windows()
                    else:
                        tmux_self.stop_window(window_name)
                elif cmd == 'stop-tag':
                    tmux_self.stop_all_windows(tags={window_name})
                elif cmd == 'terminate':
                        tmux_self.kill_all_windows()
                        sleep(1)
                        tmux_self.init()

                sleep(1)
                self.sendJSON(self.on_status())

            def on_status(self, payload=None):
                debug('status-requested: ')

                res = {
                    'windows': {},
                    'method': 'update_status'
                }
                for w in tmux_self.config['windows']:
                    res['windows'][w['name']] = tmux_self.is_running(w['name'])

                return res

                # return {'button_outcome': True}

        log.startLogging(sys.stdout)
        wsFactory = WebSocketServerFactory()
        wsFactory.protocol = TMuxWSProtocol
        wsResource = WebSocketResource(wsFactory)
        staticResource = File(
            path.realpath(
                path.join(
                    path.dirname(__file__),
                    'www/static'
                )
            )            
        )

        app = TMuxWebServer()

        # create a Twisted Web WSGI resource for our Flask server
        wsgiResource = WSGIResource(reactor, reactor.getThreadPool(), app.wsgifunc())

        # create a root resource serving everything via WSGI/Flask, but
        # the path "/ws" served by our WebSocket stuff
        rootResource = WSGIRootResource(wsgiResource, {
            b'ws': wsResource,
            b'static': staticResource
        })

        # create a Twisted Web Site and run everything
        site = Site(rootResource)

        reactor.listenTCP(port, site)
        reactor.run()        # kill everything when server dies
        if not keepalive:
            self.kill_all_windows()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", '-c', type=str,
                        default='tmule.yaml',
                        help="YAML config file. see sample-config.yaml. "
                        "Default: tmule.yaml")
    parser.add_argument("--init", '-i', type=bool, default=True,
                        help="Should tmux be initialised? Default: True")

    parser.add_argument("--session", '-s', type=str,
                        default=None,
                        help="The session that is controlled. "
                        "Default: 'tmule'")
    parser.add_argument("--wait", '-W', type=float,
                         default=0.0,
                         help="Seconds to wait between launching windows. Default: 1.0")

    subparsers = parser.add_subparsers(dest='cmd',
                                       help='sub-command help')
    subparsers.add_parser('list', help='show windows')
    parser_launch = subparsers.add_parser('launch', help='launch window(s)')
    parser_launch.add_argument("--window", '-w', type=str,
                               default="",
                               help="Window to be launched. Default: ALL")
    parser_launch.add_argument("--tag", '-t',
                               action='append',
                               default=[],
                               help="Tag of windows to be launched, "
                               "can be repeated several times.")
    parser_stop = subparsers.add_parser('stop', help='stop windows(s)')
    parser_stop.add_argument("--window", '-w', type=str,
                             default="",
                             help="Window to be stopped. Default: ALL")
    parser_stop.add_argument("--tag", '-t',
                             action='append',
                             default=[],
                             help="Tag of windows to be stopped, "
                             "can be repeated several times.")
    parser_relaunch = subparsers.add_parser('relaunch',
                                            help='relaunch windows(s)')
    parser_relaunch.add_argument("--window", '-w', type=str,
                                 default="",
                                 help="Window to be relaunched. Default: ALL")
    parser_relaunch.add_argument("--tag", '-t',
                                 action='append',
                                 default=[],
                                 help="Tag of windows to be relaunched, "
                                 "can be repeated several times.")
    subparsers.add_parser('terminate', help='kill window(s)')
    parser_server = subparsers.add_parser('server', help='run web server')
    parser_server.add_argument("--port", '-p', type=int,
                                 default=9999,
                                 help="Port to run the server on (default: 9999)")
    parser_server.add_argument("--keepalive", '-k', action='store_true',
                                 help="When quitting the server, shall the session be kept alive? (default: session terminated)")

    parser_pids = subparsers.add_parser('pids', help='pids of processes')
    parser_pids.add_argument(
        "--window", '-w', type=str,
        default="",
        help="Window for which PIDs are shown. Default: ALL")
    parser_pids = subparsers.add_parser(
        'running',
        help='returns true of there is a process running in the window')
    parser_pids.add_argument("--window", '-w', type=str,
                             required=True,
                             help="Window to be checked.")

    args = parser.parse_args()

    tmux = TMux(
        session_name=args.session,
        configfile=args.config,
        sleep_sec=args.wait)

    if args.init:
        tmux.init()

    if args.cmd == 'list':
        print(pformat(tmux.list_windows()))
    elif args.cmd == 'launch':
        if args.window == '':
            tmux.launch_all_windows(tags=set(args.tag))
            pass
        else:
            tmux.launch_window(args.window)
    elif args.cmd == 'stop':
        if args.window == '':
            tmux.stop_all_windows(tags=set(args.tag))
        else:
            tmux.stop_window(args.window)
    elif args.cmd == 'relaunch':
        if args.window == '':
            tmux.stop_all_windows(tags=set(args.tag))
            sleep(1)
            tmux.launch_all_windows(tags=set(args.tag))
        else:
            tmux.stop_window(args.window)
            sleep(1)
            tmux.launch_window(args.window)
    elif args.cmd == 'terminate':
        tmux.kill_all_windows()
    elif args.cmd == 'running':
        print(tmux.is_running(args.window))
    elif args.cmd == 'server':
        tmux._server(args.port, args.keepalive)
    elif args.cmd == 'pids':
        if args.window == '':
            print(pformat(tmux.get_children_pids_all_windows()))
        else:
            print(pformat(tmux.get_children_pids_window(args.window)))
    else:
        error('unknown command %s', args.cmd)

    # windows_to_launch = [
    #     'htop', 'navigation', 'speech', 'ui', 'pnp', 'dataset'
    # ]
    # for w in windows_to_launch:
    #     tmux.launch_window(w, True)
    #     sleep(1)
    # #sleep(8)
    # tmux.stop_all_windows()
    # tmux.terminate()


if __name__ == "__main__":
    main()
