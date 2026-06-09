from interfaces.i_env import IEnvironment

class MacOSEnvironment(IEnvironment):
    @property
    def agent_data_dir(self) -> str:
        return "/Library/Application Support/Netskope/STAgent"

    @property
    def agent_log_file(self) -> str:
        return "/Library/Logs/Netskope/stAgent/nsdebuglog.log"

    @property
    def system_hosts_file(self) -> str:
        return "/etc/hosts"
