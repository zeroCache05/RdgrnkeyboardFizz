#!/usr/bin/env bash
# Install everything the fizzctl GUI needs.
set -euo pipefail
cd "$(dirname "$0")"

# Install fizzctl as a command-line tool, using the versions in requirements.txt.
# uv is used because fizzctl needs Python 3.14, which uv downloads if missing.
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null; then
  echo "Installing uv (Python tool installer)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
FIZZ=$(grep -E '^fizzctl' requirements.txt)
uv tool install --force --with-requirements requirements.txt "$FIZZ"

# Let fizzctl reach the keyboard without root (one time).
if [ ! -e /etc/udev/rules.d/99-k617.rules ]; then
  echo "Installing udev rules (needs sudo)..."
  sudo "$(command -v fizzctl)" setup-udev
fi

echo
echo "Done. Start the GUI with:  python3 $(pwd)/server.py"
echo "Then open http://127.0.0.1:8617"
