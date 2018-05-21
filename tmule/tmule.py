#! /usr/bin/env python
from libtmux import Server
from yaml import load
from logging import error, warn, info, debug, basicConfig, INFO, WARN, DEBUG
from pprint import pformat, pprint
from time import sleep
import signal
import os
from os import path
import argparse
from subprocess import call
from psutil import Process, wait_procs
import sys
from loader import Loader

from datetime import datetime
basicConfig(level=INFO)

sys.path.append(os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..'))
)


class TMux:

    def __init__(self, session_name="tmule", configfile=None):
        if configfile:
            self.load_config(configfile)
        else:
            self.config = None
        self.session_name = session_name

    def _on_terminate(self, proc):
        info("process {} terminated with exit code {}"
             .format(proc, proc.returncode))

    def _terminate(self, pid):
        procs = Process(pid).children()
        for p in procs:
            p.terminate()
        gone, still_alive = wait_procs(procs, timeout=1,
                                       callback=self._on_terminate)
        for p in still_alive:
            p.kill()

    def _get_children_pids(self, pid):
        return Process(pid).children(recursive=True)

    def load_config(self, filename="sample_config.json"):
        with open(filename) as data_file:
            self.config = load(data_file,Loader)

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
                #window.select_window()
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
            pane = window.select_pane('%%%d' % (pane_no + 1))
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

    def launch_all_windows(self):
        for winconf in self.config['windows']:
            self.launch_window(winconf['name'])

    def stop_all_windows(self):
        for winconf in self.config['windows']:
            self.stop_window(winconf['name'])

    def get_children_pids_all_windows(self):
        pids = []
        for winconf in self.config['windows']:
            pids.extend(
                self.get_children_pids_window(winconf['name'])
            )
        return pids

    def kill_all_windows(self):
        for winconf in self.config['windows']:
            self.kill_window(winconf['name'])
        self.server.kill_session(self.session_name)

    def stop_window(self, window_name):
        info('stop %s' % window_name)
        winconf, window = self.find_window(window_name)
        self._stop_window(winconf, window)

    def _stop_window(self, winconf, window):
        pane_no = 0
        for cmd in winconf['panes']:
            pane = window.select_pane('%%%d' % (pane_no + 1))
            self.send_ctrlc(pane)
            pane_no += 1
        pids = self._get_pids_window(window)
        sleep(.1)
        for p in pids:
            self._terminate(p)
        winconf['_running'] = False

    def kill_window(self, window_name):
        info('terminate %s' % window_name)
        winconf, window = self.find_window(window_name)
#                       "-F '#{pane_active} #{pane_pid}")
        self._stop_window(winconf, window)
        pids = self._get_pids_window(window)
        for pid in pids:
            Process(pid).terminate()
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
        winconf, window = self.find_window(window_name)
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
            if call(winconf['check'], shell=True) == 0:
                return True
            else:
                return False
        else:
            return True

    def _server(self):
        import webnsock
        import web

        tmux_self = self

        class TMuxWebServer(webnsock.WebServer):

            def __init__(self):

                webnsock.WebServer.__init__(
                    self
                )

                self._render = web.template.render(
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
                        return self_app._render.index(tmux_self.config)

                class Log(self.page):
                    path = '/log'

                    def GET(self):
                        lines = tmux_self.server.cmd(
                            'capture-pane', '-p', '-C', '-S', '-100000').stdout
                        return '\n'.join(lines)

        class TMuxWSProtocol(webnsock.JsonWSProtocol):

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
                elif cmd == 'stop':
                    if window_name == '':
                        tmux_self.stop_all_windows()
                    else:
                        tmux_self.stop_window(window_name)
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

                #return {'button_outcome': True}

        self.webserver = webnsock.WebserverThread(TMuxWebServer(), port=9999)
        self.backend = webnsock.WSBackend(TMuxWSProtocol)

        signal.signal(
            signal.SIGINT,
            lambda s, f: webnsock.signal_handler(
                self.webserver, self.backend, s, f))
        self.webserver.start()
        self.backend.talker(port=9998)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str,
                        default='tmule.yaml',
                        help="YAML config file. see sample-config.yaml. Default: tmule.yaml")
    parser.add_argument("--init", type=bool, default=True,
                        help="Should tmux be initialised? Default: True")
    parser.add_argument("--session", type=str,
                        default='tmule',
                        help="The session that is controlled. Default: tmule")

    subparsers = parser.add_subparsers(dest='cmd',
                                       help='sub-command help')
    parser_list = subparsers.add_parser('list', help='show windows')
    parser_launch = subparsers.add_parser('launch', help='launch window(s)')
    parser_launch.add_argument("--window", '-w', type=str,
                               default="",
                               help="Window to be launched. Default: ALL")
    parser_stop = subparsers.add_parser('stop', help='stop windows(s)')
    parser_stop.add_argument("--window", '-w', type=str,
                             default="",
                             help="Window to be stopped. Default: ALL")
    parser_relaunch = subparsers.add_parser('relaunch',
                                            help='relaunch windows(s)')
    parser_relaunch.add_argument("--window", '-w', type=str,
                                 default="",
                                 help="Window to be relaunched. Default: ALL")
    parser_kill = subparsers.add_parser('terminate', help='kill window(s)')
    parser_kill.add_argument("--window", '-w', type=str,
                             default="",
                             help="Window to be killed. Default: ALL")
    parser_server = subparsers.add_parser('server', help='run web server')
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

    tmux = TMux(session_name=args.session, configfile=args.config)

    if (args.init):
        tmux.init()

    if args.cmd == 'list':
        print(pformat(tmux.list_windows()))
    elif args.cmd == 'launch':
        if args.window == '':
            tmux.launch_all_windows()
            pass
        else:
            tmux.launch_window(args.window)
    elif args.cmd == 'stop':
        if args.window == '':
            tmux.stop_all_windows()
        else:
            tmux.stop_window(args.window)
    elif args.cmd == 'relaunch':
        if args.window == '':
            tmux.stop_all_windows()
            sleep(1)
            tmux.launch_all_windows()
        else:
            tmux.stop_window(args.window)
            sleep(1)
            tmux.launch_window(args.window)
    elif args.cmd == 'terminate':
        if args.window == '':
            tmux.kill_all_windows()
        else:
            tmux.kill_window(args.window)
    elif args.cmd == 'running':
        print tmux.is_running(args.window)
    elif args.cmd == 'server':
        tmux._server()
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
