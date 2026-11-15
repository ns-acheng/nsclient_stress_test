#!/bin/bash
# Release stress suite runner (Linux VM).
#
# Run every template as root. Templates that start/stop stagentd must not
# run from a plain user session: 'systemctl start' from a non-root context
# is challenged by polkit, and with no one to answer the auth prompt (e.g.
# unattended runs, broken desktop polkit agent) every start times out —
# this invalidated stress08 and soak01 in the 144 cycle.
#
# Run inside a terminal or detached tmux session, e.g.:
#   sudo tmux new-session -d -s stress 'bash jithan_stress_test.sh'

cd "$(dirname "$0")"
PY="$(pwd)/venv/bin/python"

sudo "$PY" main.py --template=linux/stress01-connection-storm
sudo "$PY" main.py --template=linux/stress02-traffic-flood
sudo "$PY" main.py --template=linux/stress03-tunnel-flapping
sudo "$PY" main.py --template=linux/stress05-service-chaos
sudo "$PY" main.py --template=linux/stress08-toggle-disabling
sudo "$PY" main.py --template=linux/soak01-long-haul-memory-leak
