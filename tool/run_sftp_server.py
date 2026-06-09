import argparse
import logging
import os
import posixpath
import socket
import stat
import threading
import sys
import paramiko
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from util_input import start_input_monitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logging.getLogger("paramiko").setLevel(logging.WARNING)
logger = logging.getLogger()


def _normalize_remote_path(path: str) -> str:
    if not path:
        return "/"
    norm = posixpath.normpath(path)
    if not norm.startswith("/"):
        norm = f"/{norm}"
    return norm


class BlackholeSFTPHandle(paramiko.SFTPHandle):
    def __init__(self, flags, path, record_size_cb=None):
        super().__init__(flags)
        self.path = path
        self.total_written = 0
        self._record_size_cb = record_size_cb

    def write(self, offset, data):
        data_len = len(data)
        self.total_written += data_len
        return paramiko.SFTP_OK

    def close(self):
        if self._record_size_cb:
            self._record_size_cb(self.path, self.total_written)
        logger.info(
            f"Upload completed: {self.path}, bytes={self.total_written}"
        )
        return paramiko.SFTP_OK


class StubSFTPServer(paramiko.SFTPServerInterface):
    _file_sizes = {}
    _file_sizes_lock = threading.Lock()

    def __init__(self, server, *largs, **kwargs):
        super(StubSFTPServer, self).__init__(server, *largs, **kwargs)

    @classmethod
    def _record_uploaded_size(cls, path: str, size: int) -> None:
        norm = _normalize_remote_path(path)
        with cls._file_sizes_lock:
            cls._file_sizes[norm] = size

    @classmethod
    def _get_uploaded_size(cls, path: str):
        norm = _normalize_remote_path(path)
        with cls._file_sizes_lock:
            return cls._file_sizes.get(norm)

    @classmethod
    def _delete_uploaded_path(cls, path: str) -> None:
        norm = _normalize_remote_path(path)
        with cls._file_sizes_lock:
            cls._file_sizes.pop(norm, None)

    @classmethod
    def _rename_uploaded_path(cls, oldpath: str, newpath: str) -> None:
        old_norm = _normalize_remote_path(oldpath)
        new_norm = _normalize_remote_path(newpath)
        with cls._file_sizes_lock:
            if old_norm in cls._file_sizes:
                cls._file_sizes[new_norm] = cls._file_sizes.pop(old_norm)

    def list_folder(self, path):
        return []

    def stat(self, path):
        norm = _normalize_remote_path(path)
        if norm in ["/", "/."]:
            return paramiko.SFTPAttributes.from_stat(os.stat("."))

        size = self._get_uploaded_size(norm)
        if size is None:
            return paramiko.SFTP_NO_SUCH_FILE

        attr = paramiko.SFTPAttributes()
        attr.st_mode = stat.S_IFREG | 0o644
        attr.st_size = size
        return attr

    def lstat(self, path):
        return self.stat(path)

    def open(self, path, flags, attr):
        is_write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
        if is_write:
            logger.info(f"STOR requested for {path}")
        else:
            logger.info(f"Client opened file: {path}")
        return BlackholeSFTPHandle(flags, path, self._record_uploaded_size)

    def remove(self, path):
        logger.info(f"Client removed file: {path}")
        self._delete_uploaded_path(path)
        return paramiko.SFTP_OK

    def rename(self, oldpath, newpath):
        self._rename_uploaded_path(oldpath, newpath)
        return paramiko.SFTP_OK

    def mkdir(self, path, attr):
        return paramiko.SFTP_OK

    def rmdir(self, path):
        return paramiko.SFTP_OK

    def chattr(self, path, attr):
        return paramiko.SFTP_OK

    def symlink(self, target_path, path):
        return paramiko.SFTP_OK

    def readlink(self, path):
        return paramiko.SFTP_OK

class StubServer(paramiko.ServerInterface):
    def __init__(self, user, password):
        self.user = user
        self.password = password

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_auth_password(self, username, password):
        if username == self.user and password == self.password:
            logger.info(f"SFTP auth success for user '{username}'")
            return paramiko.AUTH_SUCCESSFUL
        logger.warning(f"SFTP auth failed for user '{username}'")
        return paramiko.AUTH_FAILED

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_exec_request(self, channel, command):
        return True

    def check_channel_subsystem_request(self, channel, name):
        if name != "sftp":
            logger.warning(f"Rejected subsystem request: {name}")
            return False
        logger.info("Accepted subsystem request: sftp")
        return super().check_channel_subsystem_request(channel, name)

def handle_client(client_sock, args, host_key):
    client_sock.settimeout(20)
    transport = paramiko.Transport(client_sock)
    transport.add_server_key(host_key)
    server = StubServer(args.user, args.password)
    try:
        transport.set_subsystem_handler(
            "sftp", paramiko.SFTPServer, StubSFTPServer
        )
        transport.start_server(server=server)
        channel = transport.accept(20)
        if channel is None:
            logger.warning("SFTP session channel was not established before timeout")
            return

        logger.info("SFTP session channel established")

        while transport.is_active():
            time.sleep(0.1)
    except Exception as e:
        logger.error(f"Connection error: {e}")
    finally:
        transport.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=2222)
    parser.add_argument("--user", type=str, default="test")
    parser.add_argument("--password", type=str, default="password")
    parser.add_argument("--keyfile", type=str, default="host.key")
    args = parser.parse_args()

    if not os.path.exists(args.keyfile):
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file(args.keyfile)

    host_key = paramiko.RSAKey(filename=args.keyfile)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', args.port))
    sock.listen(10)
    sock.settimeout(1.0)

    logger.info(f"SFTP Server listening on {args.port}")
    logger.info("Press ESC to stop the server")

    stop_event = threading.Event()
    start_input_monitor(stop_event)

    while not stop_event.is_set():
        try:
            client, addr = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        logger.info(f"Connection from {addr}")
        t = threading.Thread(
            target=handle_client, args=(client, args, host_key)
        )
        t.daemon = True
        t.start()

    logger.info("Stopping SFTP server...")
    sock.close()

if __name__ == "__main__":
    main()
