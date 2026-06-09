import os
from interfaces.i_env import IEnvironment

class WindowsEnvironment(IEnvironment):
    @property
    def agent_data_dir(self) -> str:
        prog_data = os.environ.get('ProgramData', 'C:\\ProgramData')
        return os.path.join(prog_data, 'netskope', 'stagent')

    @property
    def agent_log_file(self) -> str:
        return os.path.join(self.agent_data_dir, 'logs', 'nsdebuglog.log')

    @property
    def system_hosts_file(self) -> str:
        return r"C:\Windows\System32\drivers\etc\hosts"
