from subprocess import Popen, PIPE, list2cmdline
import os
import logging
import exc
import formats
from _compat import console_to_str

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
            print "use host"
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
        pass

    def tmux(self, *args):
        return tmux_cmd(*args, host=self.host)

    def has_session(self, session):
        t = self.tmux('has-session', '-t', session)
        if t.returncode > 0:
            raise exc.LibTmuxException('failed')
        return t.returncode == 0

    def ensure_session(self, session):
        if not self.has_session(session):
            self.tmux('new-session', '-d', '-s', session)

    def list_windows(self, session):
        wformats = ['session_name', 'session_id'] + formats.WINDOW_FORMATS
        tmux_formats = ['#{%s}' % format for format in wformats]
        t = self.tmux(
            'list-windows', '-t', session,
            '"-F%s"' % '\t'.join(tmux_formats)
            )
        logger.info(t.stdout)
        if t.returncode > 0:
            raise exc.LibTmuxException('failed')
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

        return win_ids

    def has_windows(self, window):
        pass

if __name__ == "__main__":
    t = TMux('localhost')
    t.ensure_session('hurga')
    wid = t.list_windows('hurga')
    print wid
    #c = tmux_cmd('new-session', '-d', '-s', 'hurga', host="localhost")
    #print "RETURN: %d" % c.returncode
    #print "STDERR: %s" % c.stderr
    #print "STDOUT: %s" % c.stdout


