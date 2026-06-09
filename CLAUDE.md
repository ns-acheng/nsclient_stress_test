# Project Coding Standards

This document defines the coding standards and conventions for the `stress_test` project. All contributors must follow these guidelines when writing or modifying code.

## Project Overview

A cross-platform (Windows/macOS/Linux/Android/iOS) service stress testing and resource monitoring tool for the Netskope Client (`stAgentSvc`) and Driver (`stadrv`). The tool simulates user activity while cycling service states and monitoring for crashes.

**Platform Support Status**:
- ✅ Windows - Complete
- ✅ macOS - Complete
- 🔨 Linux - In Development
- 📋 Android - Planned
- 📋 iOS - Planned

## Python Requirements

- **Minimum Version**: Python 3.10+
- **CI Testing**: Python 3.11, 3.12, 3.13
- **Platform Support**: Windows, macOS, and Linux

## Architecture Principles

### Interface-Based Design

- Use Abstract Base Classes (ABC) for all platform-agnostic interfaces
- Place interfaces in `interfaces/` directory
- Prefix interface names with `I` (e.g., `IPowerManager`, `IServiceManager`)
- All interfaces must use `@abstractmethod` decorators

### Factory Pattern

- Use the factory pattern for all platform-specific implementations
- Factory classes: `WindowsFactory`, `MacOSFactory`, `LinuxFactory`
- Each factory creates platform-specific instances of all required interfaces
- All factories must implement the `IPlatformFactory` interface

### Platform Separation

- Platform-specific code goes in `platforms/<platform_name>/` directories
- Supported platforms: `windows/`, `macos/`, `linux/`
- Each platform implements all required interfaces
- Shared utilities stay in root directory with `util_` prefix

## File and Directory Organization

```
interfaces/          # Abstract interfaces (ABC)
platforms/           # Platform-specific implementations
  windows/           # Windows implementations
  macos/             # macOS implementations
  linux/             # Linux implementations
tool/                # Helper scripts and servers
test/                # Unit tests
  test_interfaces/   # Interface tests
data/                # Configuration and data files
  template/          # Config templates
    windows/         # Windows templates
    macos/           # macOS templates
log/                 # Log output (timestamped folders)
```

## Naming Conventions

### Files and Modules
- **Utility files**: `util_<name>.py` (e.g., `util_log.py`, `util_config.py`)
- **Test files**: `test_<name>.py` (e.g., `test_util_log.py`)
- **Interface files**: `i_<name>.py` (e.g., `i_power.py`, `i_service.py`)
- Use snake_case for all file names

### Classes
- **PascalCase**: All class names (e.g., `StressTest`, `LogSetup`)
- **Interfaces**: Prefix with `I` (e.g., `IPowerManager`, `ISystemInfo`)
- **Platform classes**: Include platform name (e.g., `WindowsPowerManager`, `MacOSServiceManager`)
- **Manager pattern**: Suffix with `Manager` (e.g., `AgentConfigManager`)

### Functions and Variables
- **snake_case**: All functions and variables
- **Private methods**: Prefix with single underscore `_` (e.g., `_apply_template`, `_resolve_template_name`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `TINY_SEC`, `BATCH_SIZE`, `ITER_FILTER`)

## Code Style

### Import Organization

Organize imports in three groups with blank lines between:

```python
# 1. Standard library
import sys
import os
import json
import logging

# 2. Third-party packages
import pytest
from unittest.mock import MagicMock

# 3. Local modules
from interfaces.i_power import IPowerManager
from util_log import LogSetup
```

### Type Hints

- Use type hints for all interface methods
- Use type hints for function parameters and return types
- Import types from appropriate modules

```python
def create_power_manager(self) -> IPowerManager:
    pass

def setup_logging(self, existing_log_dir: str = None) -> logging.Logger:
    pass
```

### Line Length and Code Organization

- **Line Length**: Limit each line to 110 characters. Use shorter variable names or wrap lines when necessary
- **Simplicity**: Keep `main.py` and `stress_test.py` as simple as possible. Move complex logic into utilities or specialized modules

### Documentation

- Add docstrings for public classes and non-trivial methods
- Use comments for complex logic that isn't self-evident
- Document platform-specific behavior
- Keep comments concise and relevant

## Logging

### Logging Setup

- Use Python's `logging` module exclusively
- Configure logging via `LogSetup` class
- Log to both file and console
- Timestamped log folders: `log/YYYYMMDD-HHMMSS-<suffix>/`

### Logging Best Practices

- **Levels**:
  - INFO: Normal operations and significant events
  - WARNING: Issues that don't prevent operation
  - ERROR: Failures and exceptions
- **Format**: `'%(asctime)s - %(levelname)s - %(message)s'`
- **Security**: Never log passwords, credentials, or sensitive data
- **Third-party Libraries**: Set verbose loggers to WARNING level:

```python
logging.getLogger("paramiko").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
```

## Configuration

### Configuration Files

- **Main config**: `data/config.json` (JSON format)
- **State file**: `data/state.json` (persistent state)
- **Templates**: `data/template/<platform>/<name>.json`

### Configuration Management

- Use `ToolConfig` class for reading configuration files
- Use `AgentConfigManager` for managing agent-specific configurations
- Validate all configuration values on load
- Automatically copy configuration to log folder on each run for audit trail

## Testing

### Test Framework

- **Framework**: pytest
- **Coverage**: Use pytest-cov
- **Mocking**: Use pytest-mock and unittest.mock

### Test Organization

- Place all tests in `test/` directory
- Name test files: `test_<module_name>.py`
- Use descriptive test names: `test_<functionality>_<scenario>`
- Group related tests in classes

### Test Requirements

- **Mock I/O Operations**: Mock all file system, network, and OS calls
- **No Admin Privileges**: Tests must run as a regular user without elevated privileges
- **No Real Services**: Mock all service interactions; never start/stop real services
- **Leverage Fixtures**: Use shared fixtures from `conftest.py` for consistency
- **Temporary Files**: Use pytest's `tmp_path` fixture for any file system operations

### Shared Fixtures (from conftest.py)

```python
stop_event        # Threading event
mock_env          # IEnvironment mock
mock_svc_mgr      # IServiceManager mock
mock_power_mgr    # IPowerManager mock
mock_sys_info     # ISystemInfo mock
mock_input_mon    # IInputMonitor mock
mock_diag         # IDiagnostics mock
sample_urls       # Sample URL list
minimal_config    # Minimal config dict
full_config       # Full config dict
tmp_config_dir    # Temp config directory
```

### Running Tests

```bash
# Run all tests
python -m pytest test/ -v

# Run specific test file
python -m pytest test/test_util_time.py -v

# Run with coverage
python -m pytest test/ --cov=. --cov-report=term-missing
```

## Error Handling

### Exception Handling

- Wrap I/O operations and external calls in try-except blocks
- Use `logger.exception()` to log exceptions with full stack traces
- Provide clear, actionable error messages
- Always clean up resources in `finally` blocks

### Admin Privilege Requirements

- The tool requires admin/root privileges for service control
- Verify privileges early during startup
- Display clear error messages when privileges are insufficient

## Cross-Platform Considerations

### Platform Detection

```python
import sys
import platform

if sys.platform.startswith('win'):
    # Windows-specific code
elif sys.platform.startswith('darwin'):
    # macOS-specific code
elif sys.platform.startswith('linux'):
    # Linux-specific code

system = platform.system().lower()  # 'windows', 'darwin', 'linux'
```

### Shell Commands

- Use Unix shell syntax in bash shell (configured for Windows)
- Use `/dev/null` not `NUL`
- Use forward slashes in paths

### Platform-Specific Naming

- Service names differ by platform
- Process names differ by platform
- Store platform-specific values in class initialization

## Security Considerations

- **Credentials**: Never log passwords, tokens, or credentials
- **Input Validation**: Validate all user inputs and configuration values
- **Command Injection**: Use safe file operations; avoid shell command injection
- **Logging Levels**: Set appropriate levels for modules handling sensitive data
- **Version Control**: Never commit secrets, credentials, or sensitive configuration to the repository

## Git Workflow

### Branch Strategy

- Main branch: `master`
- Create feature branches for new work
- Submit pull requests for review

### Commit Messages

- Use clear, descriptive commit messages
- Reference issue numbers when applicable
- Follow conventional commit format when possible

### CI/CD

- Tests run automatically on pull requests and pushes to `master`
- All tests must pass before merging
- CI matrix: Python 3.11, 3.12, 3.13 on supported platforms

## Code Review Checklist

When reviewing code, verify:

- ✓ Interface contracts are properly followed
- ✓ Platform-specific code is in the correct directory structure
- ✓ All I/O operations are mocked in tests
- ✓ Type hints are present for all public APIs
- ✓ Logging doesn't expose passwords or sensitive data
- ✓ Error handling is appropriate and comprehensive
- ✓ Code follows project naming conventions
- ✓ Tests are included for all new functionality
- ✓ No hardcoded paths, credentials, or platform assumptions
- ✓ Line length stays within 110 characters

## Multi-Platform Testing

### Test Organization

Tests are organized to maximize code reuse across platforms:

- **Shared Interface Tests** (`test/test_interfaces/`) - 90% of tests
  - Written once, run on all platforms via pytest parametrization
  - Validate interface contracts (behavior same across platforms)
  - Examples: `test_i_service_manager.py`, `test_i_power_manager.py`

- **Platform-Specific Tests** (`test/test_platforms/`) - 10% of tests
  - Only test platform-specific implementation details
  - Validate exact commands, OS-specific features
  - Examples: `test_linux_commands.py`, `test_windows_commands.py`

### Adding New Platform Support

When implementing a new platform (e.g., Linux, Android, iOS):

1. **Implement interfaces** in `platforms/<platform>/`
   - Create factory, service, power, system, input, diag, env modules
   - Follow interface contracts from `interfaces/`

2. **Shared tests run automatically**
   - All `test_interfaces/` tests will test your new platform
   - No new tests needed for shared behavior

3. **Add platform-specific tests**
   - Create `test/test_platforms/test_<platform>_commands.py`
   - Test exact command strings and platform features (~10-20 tests)

4. **Run tests during development**
   - All tests can run on Windows via mocking
   - Validate on real platform later (optional)

**Platform-Specific Considerations**:
- **Power Management**: Windows-only feature. Other platforms implement stubs returning False
- **Testing**: All platforms developed and tested on any OS using mocks
- **Documentation**: See [test.md](test.md) for complete testing guide
