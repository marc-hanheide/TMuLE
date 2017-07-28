# TMuLE - TMux Launch Engine

## What is TMuLE for?

To simply control [tmux](https://github.com/tmux/tmux/wiki) sessions to deploy pre-configured software system very easily. All it needs is a configuration file (in JSON) and different sub-systems (defined as different windows in a joint tmux sessions) can be launch and stopped conveniently.

## Concepts

[tmux](https://github.com/tmux/tmux/wiki) features *windows* which can have different *panes*. In *TMuLE* windows correspond to sub-systems that can be launch and stopped independently of others, but always are launched or stopped together. Each pane in a window runs one of a set of commands belonging to one sub-system.

## Configuration File

The configuration file uses JSON format.

* an `init_cmd` can be defined which is executed in each *pane before* the actual command is run.
* the `windows` are a list of individual windows that will be created in the tmux session. Each corresponds to one sub-system. 
* Each window is given a `name`, and a list of `panes`
* the entries in the `panes` list, are shell scripts commands that are executed *as is* in the tmux session shell (i.e. *bash*)

Here is an example `sample.json`:   

```json
{
  "init_cmd": "source ~/spqrel/spqrel_launch/setup.bash; source ~/spqrel/spqrel_launch/worktree/spqrel_tools/setup-dev.bash /opt/naoqi; sleep 3",
  "windows": [
    {
      "name": "bash",
      "panes": [
        "bash"
      ]
    },
    {
      "name": "htop",
      "panes": [
        "htop"
      ]
    },
    {
      "name": "navigation",
      "panes": [
        "pepper_localizer",
        "pepper_planner"
      ]
    }
  ]
}
```

## Usage

Just run `tmux.py -h`, output whould be something like this:


```
usage: tmux.py [-h] [--config CONFIG] [--init INIT] [--session SESSION]
               {list,launch,stop,relaunch,terminate,server,pids,running} ...

positional arguments:
  {list,launch,stop,relaunch,terminate,server,pids,running}
                        sub-command help
    list                show windows
    launch              launch window(s)
    stop                stop windows(s)
    relaunch            relaunch windows(s)
    terminate           kill window(s)
    server              run web server
    pids                pids of processes
    running             returns true of there is a process running in the
                        window

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG       JSON config file. see sample-config.json. Default:
                        spqrel-pepper-config.json
  --init INIT           Should tmux be initialised? Default: True
  --session SESSION     The session that is controlled. Default: spqrel```

### Typical usage (corresponding to the `sample.json` file above)

Note: If you are using the default config file, you can obviously skip using the `--config` option below.

* list the windows in the tmux session:

  `tmux --config sample.json list`

  If the `init` option is not explicitly set to `False` this will create (or attach to) the default (`spqrel`) tmux session, and will make sure that all the windows that are configured and required panes are created. 

* launch one specific window (sub-system):

  `tmux -config sample.json launch -w navigation`

  This will launch all the configured commands in the `navigation` window in their two respective panes.

* stop the processes of a window (sub-system):

	`tmux -config sample.json stop -w navigation`

	This command will send `Ctrl-C` to all the panes of the `navigation` window, and hence stop all the processes in there. 

* kill the processes of a window (sub-system):

	`tmux -config sample.json kill -w navigation`

	This command will send `Ctrl-C` to all the panes of the `navigation` window just like `stop` would do, but follows this with a proper `kill -9` for all child processes to make sure everything is sure and properly gone. It will also close the respective window in the session. 

* if in any of the above commands, now window is specified (no `-w` or `--window` option given), the command will apply to *ALL* configured windows (sub-systems), e.g.

	`tmux -config sample.json launch`

	will launch all processes

	`tmux -config sample.json kill`

	will shut everything down and in fact close the tmux session

* Manual interaction with the tmux session:

	`tmux a -t sqprel`

	This will attach to the default TMuLE session, allwoing manual inspection and interaction with the session (e.g. watching the output of the individual processes, or even starting and stopping them manually)

	Use `Ctrl-b d` to detach from the session again, or `Ctrl-b w` to switch between different windows. 
