from interfaces.i_env import IEnvironment

class LinuxEnvironment(IEnvironment):
    @property
    def agent_data_dir(self) -> str:
        return "/opt/netskope/stagent/data"

    @property
    def agent_log_file(self) -> str:
        return "/var/log/netskope/stagent/nsdebuglog.log"

    @property
    def system_hosts_file(self) -> str:
        return "/etc/hosts"
