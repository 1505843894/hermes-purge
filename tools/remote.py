#!/usr/bin/env python3
"""Remote helper for the hermes VPS: run / put / get over paramiko.

    python remote.py run "<shell command>"
    python remote.py put <local-dir-or-file> <remote-path>
    python remote.py get <remote-path> <local-path>
"""
from __future__ import annotations

import os
import posixpath
import shutil
import sys

import paramiko

HOST = os.environ.get("HG_HOST", "168.107.44.230")
USER = os.environ.get("HG_USER", "root")
PASSWORDS = [p for p in os.environ.get("HG_PASS", "Zrx431225,@Zrx431225").split(",") if p]

ENV_PREFIX = "export LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONIOENCODING=utf-8; "


def connect():
    last = None
    for pw in PASSWORDS:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            c.connect(HOST, port=int(os.environ.get("HG_PORT", "22")), username=USER,
                      password=pw, timeout=20, banner_timeout=25, auth_timeout=25,
                      allow_agent=False, look_for_keys=False)
            return c
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise SystemExit(f"auth failed: {last}")


def run(cmd: str) -> int:
    c = connect()
    _, stdout, stderr = c.exec_command(ENV_PREFIX + cmd, timeout=1800)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    rc = stdout.channel.recv_exit_status()
    c.close()
    buf = out.encode("utf-8", "replace")
    if err.strip():
        buf += bytes(chr(10) + "--- stderr ---" + chr(10) + err, "utf-8", "replace")
    buf += bytes(chr(10) + "[exit " + str(rc) + "]" + chr(10), "utf-8")
    sys.stdout.buffer.write(buf)
    sys.stdout.flush()
    return 0 if rc == 0 else rc


def _mkdirs(sftp, remote_dir: str) -> None:
    cur = ""
    for part in remote_dir.strip("/").split("/"):
        if not part:
            continue
        cur += "/" + part
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def _send(sftp, src: str, dst: str) -> None:
    with open(src, "rb") as fh, sftp.open(dst, "wb") as rh:
        try:
            rh.set_pipelined(True)
        except Exception:
            pass
        shutil.copyfileobj(fh, rh, 65536)
    print(f"  put {dst} ({os.path.getsize(src)} bytes)")


def put(local: str, remote: str) -> int:
    c = connect()
    sftp = c.open_sftp()
    local = os.path.abspath(local)
    remote = remote.replace("\\", "/").rstrip("/")
    if os.path.isdir(local):
        _mkdirs(sftp, remote)
        for root, dirs, files in os.walk(local):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache")]
            rel = os.path.relpath(root, local)
            rdir = remote if rel == "." else posixpath.join(remote, rel.replace(os.sep, "/"))
            _mkdirs(sftp, rdir)
            for f in sorted(files):
                if f.endswith(".pyc"):
                    continue
                _send(sftp, os.path.join(root, f), posixpath.join(rdir, f))
    else:
        parent = posixpath.dirname(remote) or "/"
        try:
            sftp.stat(parent)
        except IOError:
            _mkdirs(sftp, parent)
        _send(sftp, local, remote)
    sftp.close()
    c.close()
    return 0


def get(remote: str, local: str) -> int:
    c = connect()
    sftp = c.open_sftp()
    os.makedirs(os.path.dirname(os.path.abspath(local)) or ".", exist_ok=True)
    with sftp.open(remote, "rb") as rh, open(local, "wb") as fh:
        shutil.copyfileobj(rh, fh, 65536)
    size = sftp.stat(remote).st_size
    sftp.close()
    c.close()
    print(f"  get {remote} ({size} bytes) -> {local}")
    return 0


def push(local: str, remote: str) -> int:
    """走 exec 通道的 stdin 原始字节上传单文件（SFTP 在本机偶发 ENOENT，不用它）。"""
    data = open(os.path.abspath(local), "rb").read()
    c = connect()
    chan = c.get_transport().open_session()
    chan.exec_command(f"cat > {remote}")
    view = memoryview(data)
    for i in range(0, len(data), 16384):
        chan.sendall(view[i:i + 16384])
    chan.shutdown_write()
    err = chan.makefile_stderr("rb").read().decode("utf-8", "replace")
    rc = chan.recv_exit_status()
    c.close()
    if rc != 0:
        raise SystemExit(f"push failed rc={rc}: {err[:300]}")
    print(f"  push {remote} ({len(data)} bytes)")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    action = sys.argv[1]
    if action == "run":
        cmd = sys.argv[2] if len(sys.argv) > 2 else sys.stdin.read()
        return run(cmd)
    if action == "push" and len(sys.argv) == 4:
        return push(sys.argv[2], sys.argv[3])
    if action == "put" and len(sys.argv) == 4:
        return put(sys.argv[2], sys.argv[3])
    if action == "get" and len(sys.argv) == 4:
        return get(sys.argv[2], sys.argv[3])
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
