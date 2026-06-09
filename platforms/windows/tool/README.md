# Power Test Tools Setup

For advanced power state testing (Modern Standby S0, Hibernate S4), this toolset leverages `PwrTest.exe` from the Windows Driver Kit.

## Installation Requirements

To use the power testing features fully, please follow these steps to install the necessary Microsoft WDK components:

1. **Install Windows SDK 19041**:
   [Download Windows SDK](https://go.microsoft.com/fwlink/?linkid=2311805)

2. **Install WDK 19041**:
   [Download WDK](https://go.microsoft.com/fwlink/?linkid=2342425)

3. **Install WDTF Runtime Libraries**:
   To enable the "Virtual Power Button Driver" required for automated sleep transitions, install the WDTF runtime:
   * Navigate to: `C:\Program Files (x86)\Windows Kits\10\Testing\Runtimes`
   * Run: `Windows Driver Testing Framework (WDTF) Runtime Libraries-x64_en-us.msi`

4. **Environment Setup**:
   Add the tools directory to your system `%PATH%` environment variable:
   `C:\Program Files (x86)\Windows Kits\10\Tools\x64\`

## Usage

Once installed, ensure `pwrtest.exe` is accessible. The stress test tool checks for `pwrtest.exe` in this `tool/` directory or via the system PATH.
