#!/usr/bin/env python3
"""Minimal paramiko SSH runner for the hermes VPS."""
import sys, os, paramiko

HOST = os.environ.get("HG_HOST", "168.107.44.230")
USER = os.environ.get("HG_USER", "root")
PASSWORDS = [p for p in os.environ.get("HG_PASS", "Zrx431225,@Zrx431225").split(",") if p]


def connect():
    last = None
    for pw in PASSWORDS:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(HOST, port=int(os.environ.get("HG_PORT", "22")), username=USER,
                      password=pw, timeout=20, banner_timeout=25, auth_timeout=25,
                      allow_agent=False, look_for_keys=False)
            return c, pw
        except Exception as e:  # noqa
            last = e
    raise SystemExit(f"auth failed: {last}")


def main():
    script = sys.stdin.read() if len(sys.argv) < 2 or sys.argv[1] == "-" else sys.argv[1]
    c, _ = connect()
    stdin, stdout, stderr = c.exec_command(script, timeout=300)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write("\n--- stderr ---\n" + err)
    sys.stdout.write(f"\n[exit {rc}]\n")
    c.close()


if __name__ == "__main__":
    main()
