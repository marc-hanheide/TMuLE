from subprocess import Popen, PIPE, list2cmdline
import os
import logging
import exc
import formats
from _compat import console_to_str
from pprint import pprint
from datetime import datetime

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def which(exe=None, default_paths=[
            '/bin', '/sbin', '/usr/bin', '/usr/sbin', '/usr/local/bin'
        ], append_env_path=True):
    """Return path of bin. Python clone of /usr/bin/which.
    from salt.util - https://www.github.com/saltstack/salt - license apache
    :param exe: Application to search PATHs for.
    :type exe: str
    :param default_path: Application to search PATHs for.
    :type default_path: list
    :param append_env_path: Append PATHs in environmental variables.
    :type append_env_path: bool
    :rtype: str
    """
    def _is_executable_file_or_link(exe):
        # check for os.X_OK doesn't suffice because directory may executable
        return (os.access(exe, os.X_OK) and
                (os.path.isfile(exe) or os.path.islink(exe)))

    if _is_executable_file_or_link(exe):
        # executable in cwd or fullpath
        return exe

    # Enhance POSIX path for the reliability at some environments, when
    # $PATH is changing. This also keeps order, where 'first came, first
    # win' for cases to find optional alternatives
    if append_env_path:
        search_path = os.environ.get('PATH') and \
            os.environ['PATH'].split(os.pathsep) or list()
    else:
        search_path = []

    for default_path in default_paths:
        if default_path not in search_path:
            search_path.append(default_path)
    for path in search_path:
        full_path = os.path.join(path, exe)
        if _is_executable_file_or_link(full_path):
            return full_path
    logger.info(
        '\'{0}\' could not be found in the following search path: '
        '\'{1}\''.format(exe, search_path))

    return None


class tmux_cmd(object):

    """:term:`tmux(1)` command via :py:mod:`subprocess`.
    :param tmux_search_paths: Default PATHs to search tmux for, defaults to
        ``default_paths`` used in :func:`which`.
    :type tmux_search_paths: list
    :param append_env_path: Append environment PATHs to tmux search paths.
    :type append_env_path: bool
    Usage::
        proc = tmux_cmd('new-session', '-s%' % 'my session')
        if proc.stderr:
            raise exc.LibTmuxException(
                'Command: %s returned error: %s' % (proc.cmd, proc.stderr)
            )
        print('tmux command returned %s' % proc.stdout)
    Equivalent to:
    .. code-block:: bash
        $ tmux new-session -s my session
    .. versionchanged:: 0.8
        Renamed from ``tmux`` to ``tmux_cmd``.
    """

    def __init__(self, *args, **kwargs):
        if 'host' in kwargs:
            host = kwargs.get('host')
        else:
            host = None

        tmux_bin = which(
            'tmux',
            default_paths=kwargs.get('tmux_search_paths', [
                '/bin', '/sbin', '/usr/bin', '/usr/sbin', '/usr/local/bin'
            ]),
            append_env_path=kwargs.get('append_env_path', True)
        )
        if not tmux_bin:
            raise(exc.TmuxCommandNotFound)

        cmd = []
        if host:
            cmd += ['ssh']
            cmd += ['-t']
            cmd += [host]
            cmd += ['--']
        cmd += [tmux_bin]
        cmd += args  # add the command arguments to cmd
        cmd = [str(c) for c in cmd]
        logger.info(cmd)
        self.cmd = cmd

        try:
            self.process = Popen(
                cmd,
                stdout=PIPE,
                stderr=PIPE,
            )
            self.process.wait()
            self.returncode = self.process.returncode
            stdout = self.process.stdout.read()
            self.process.stdout.close()
            stderr = self.process.stderr.read()
            self.process.stderr.close()
        except Exception as e:
            logger.error(
                'Exception for %s: \n%s' % (
                    list2cmdline(cmd),
                    e
                )
            )

        self.stdout = console_to_str(stdout)
        self.stdout = self.stdout.split('\n')
        self.stdout = list(filter(None, self.stdout))  # filter empty values

        self.stderr = console_to_str(stderr)
        self.stderr = self.stderr.split('\n')
        self.stderr = list(filter(None, self.stderr))  # filter empty values

        if 'has-session' in cmd and len(self.stderr):
            if not self.stdout:
                self.stdout = self.stderr[0]

        logger.debug(
            'self.stdout for %s: \n%s' %
            (' '.join(cmd), self.stdout)
        )


class TMux():
    def __init__(self, host=None):
        self.host = host
        self.windows = {}
        self.panes = {}


    def tmux(self, *args):
        return tmux_cmd(*args, host=self.host)

    def has_session(self, session):
        t = self.tmux('has-session', '-t', session)
        return t.returncode == 0

    def ensure_session(self, session):
        if not self.has_session(session):
            self.tmux(
                'new-session', '-d',
                '-s', session,
                '-n', "__init__")
            self.tmux(
                'set-option',
                'history-limit', '100000')

    def list_windows(self):
        self.ensure_session('__tmule-control__')
        wformats = ['session_name', 'session_id'] + formats.WINDOW_FORMATS
        tmux_formats = ['#{%s}' % format for format in wformats]
        t = self.tmux(
            'list-windows', '-a',
            '"-F%s"' % '\t'.join(tmux_formats)
            )
        #logger.info(t.stdout)
        if t.returncode > 0:
            #return {}
            raise exc.LibTmuxException(t.stdout)
        windows = t.stdout
        windows = [
            dict(zip(
                 wformats, window.split('\t'))) for window in windows]

        # clear up empty dict
        windows = [
            dict((k, v) for k, v in window.items() if v) for window in windows
        ]
        win_ids = {
            '%s:%s' %
            (w['session_name'], w['window_name']): w for w in windows}

        self.windows = win_ids
        return win_ids

    def has_window(self, window, check=False):
        if len(self.windows) == 0 or check:
            self.list_windows()
        return window in self.windows

    def ensure_window(self, window):
        if not self.has_window(window, True):
            comp = window.split(':')
            logger.info(
                'new window %s in session %s' %
                (comp[1], comp[0]))
            self.ensure_session(comp[0])
            self.tmux(
                'new-window', '-a',
                '-n', comp[1],
                '-t', comp[0])

    def list_panes(self):
        self.ensure_session('__tmule-control__')
        pformats = ['session_name',
                    'session_id', 'window_name'
                    ] + formats.PANE_FORMATS
        tmux_formats = ['#{%s}' % format for format in pformats]
        t = self.tmux(
            'list-panes', '-a',
            '"-F%s"' % '\t'.join(tmux_formats)
            )
        if t.returncode > 0:
            raise exc.LibTmuxException(t.stdout)
        panes = t.stdout
        panes = [
            dict(zip(
                 pformats, window.split('\t'))) for window in panes]

        # clear up empty dict
        panes = [
            dict((k, v) for k, v in window.items() if v) for window in panes
        ]
        pane_ids = {
            '%s:%s.%s' %
            (w['session_name'],
                w['window_name'], w['pane_index']): w for w in panes}

        self.panes = pane_ids
        return pane_ids

    def has_pane(self, pane, check=False):
        if len(self.windows) == 0 or check:
            self.list_panes()
        return pane in self.panes

    def ensure_pane(self, pane):
        while not self.has_pane(pane, True):
            comp = pane.split(':')
            logger.info(
                'new pane in window %s in session %s' %
                (comp[1], comp[0]))
            # p = int(comp[1].split('.')[1])
            win = comp[1].split('.')[0]
            self.ensure_window(comp[0] + ':' + win)
            self.tmux(
                'split-window',
                '-t', comp[0] + ':' + win)
            self.tmux(
                'select-layout',
                '-t', comp[0] + ':' + win,
                'tiled')

    def send_keys(self, pane, keys, enter=False):
        self.ensure_pane(pane)
        if enter:
            self.tmux(
                'send-keys',
                '-t', pane,
                '\'' + keys + '\' C-m')
        else:
            self.tmux(
                'send-keys',
                '-t', pane,
                '\'' + keys + '\'')

    def send_ctrlc(self, pane):
        datestr = datetime.now().strftime('%c')
        self.tmux(
            'send-keys',
            '-t', pane,
            '""', 'C-c')
        self.tmux(
            'send-keys',
            '-t', pane,
            '""', 'C-c')
        self.tmux(
            'send-keys',
            '-t', pane,
            '""', 'C-c')
        self.send_keys(pane, '# tmux-controller sent Ctrl-C at %s' % datestr,
                       enter=True)

if __name__ == "__main__":
    t = TMux('localhost')
    t.ensure_window('1stsession:win1')
    t.ensure_window('1stsession:win2')
    t.send_keys('2ndsession:win1.4', 'ls -l', enter=True)
    t.send_ctrlc('2ndsession:win1.4')

    wid = t.list_panes()
    pprint(wid)
    #c = tmux_cmd('new-session', '-d', '-s', 'hurga', host="localhost")
    #print "RETURN: %d" % c.returncode
    #print "STDERR: %s" % c.stderr
    #print "STDOUT: %s" % c.stdout


