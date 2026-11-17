# K617 Fizz web GUI

A browser control panel for the Redragon K617 Fizz keyboard on Linux.
It runs on your own computer and uses [fizzctl](https://pypi.org/project/fizzctl/) to change the keyboard.

## Requirements

- Linux (tested on Ubuntu)
- `python3` and `curl` (preinstalled on Ubuntu)
- `sudo` access, once, to let fizzctl reach the keyboard

You don't need to install fizzctl or Python 3.14 yourself. The setup script does it.

## Install

1. Plug in the keyboard.
2. Get this folder onto your computer, then run:

   ```
   cd fizzctl-gui
   ./setup.sh
   ```

   This will:
   - install [uv](https://docs.astral.sh/uv/) if you don't have it
   - install fizzctl and hidapi (versions in `requirements.txt`), with Python 3.14 if needed
   - ask for your password once to set up keyboard access (`fizzctl setup-udev`)

3. If setup prints a udev warning, unplug and replug the keyboard.

## Run

```
python3 server.py
```

Open http://127.0.0.1:8617 in your browser. Press Ctrl+C in the terminal to stop.

## Notes

- Most settings are saved on the keyboard and stay after unplugging. Animations run on your computer and stop when the server or computer stops.
- The page is only reachable from your own computer.
- If the page says the keyboard isn't reachable: check it's plugged in, then run `sudo ~/.local/bin/fizzctl setup-udev` and replug it.

## Uninstall

```
uv tool uninstall fizzctl
sudo rm /etc/udev/rules.d/99-k617.rules
```
