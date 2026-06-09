# Testing

This project uses [pytest](https://docs.pytest.org/) with support for multiple platforms (Windows, macOS, Linux, Android, iOS).

## Test Structure

### Shared Interface Tests (90%)
**Location**: `test/test_interfaces/`

Tests that validate **interface contracts** across ALL platforms using pytest parametrization. Written once, runs on Windows, Linux, Android, iOS automatically.

**Files**: `test_i_service_manager.py`, `test_i_power_manager.py`, `test_i_system_info.py`, `test_i_input_monitor.py`, `test_i_diagnostics.py`, `test_i_environment.py`

### Platform-Specific Tests (10%)
**Location**: `test/test_platforms/`

Tests that validate **platform-specific commands** and OS-specific behavior.

**Files**: `test_windows_power.py`, `test_linux_commands.py`, `test_android_commands.py`, `test_ios_commands.py`

## Platform Markers

- `@pytest.mark.windows` - Windows-specific tests
- `@pytest.mark.linux` - Linux-specific tests
- `@pytest.mark.macos` - macOS-specific tests
- `@pytest.mark.android` - Android-specific tests
- `@pytest.mark.ios` - iOS-specific tests
- `@pytest.mark.unit` - Pure unit tests (fully mocked)

## Quick Start

```bash
# Install dependencies
pip install -r requirement.txt

# Run all tests
pytest test/ -v

# Run platform-only tests
pytest test/ -v -m windows
pytest test/ -v -m linux

# Run with coverage
pytest test/ --cov=. --cov-report=term-missing
```

## Common Commands

```bash
# All tests (current platform)
pytest test/ -v

# Exclude other platforms (recommended for CI)
pytest test/ -v -m "not (linux or android or ios)"  # Windows
pytest test/ -v -m "not (windows or android or ios)"  # Linux

# Specific test directory
pytest test/test_interfaces/ -v  # Shared tests
pytest test/test_platforms/ -v   # Platform-specific tests

# Specific file
pytest test/test_platforms/test_windows_power.py -v

# With coverage
pytest test/ --cov=. --cov-report=term-missing

# Short error output
pytest test/ -v --tb=short
```

## Test Examples

### Shared Interface Test

Tests interface contract (runs on all platforms):

```python
# test/test_interfaces/test_i_service_manager.py
@pytest.fixture(params=[
    pytest.param("windows", marks=pytest.mark.windows),
    pytest.param("linux", marks=pytest.mark.linux),
])
def service_manager(request, platform_factory):
    factory = platform_factory(request.param)
    return factory.create_service_manager()

def test_start_returns_bool(service_manager):
    result = service_manager.start_service("test")
    assert isinstance(result, bool)  # Runs on all platforms
```

### Platform-Specific Test

Tests exact commands for a specific platform:

```python
# test/test_platforms/test_windows_power.py
@pytest.mark.windows
@patch("platforms.windows.power.subprocess.run")
def test_powercfg_command(mock_run):
    mgr = WindowsPowerManager()
    mgr.enable_wake_timers()

    # Verify exact Windows command
    mock_run.assert_called_with(
        ["powercfg", "/change", ...],
        capture_output=True
    )
```

## Writing Tests

### Shared Tests (`test_interfaces/`)
**When**: Testing behavior same across all platforms
- Use parametrized fixtures
- Test return types, error handling, interface contracts
- No platform-specific commands

### Platform Tests (`test_platforms/`)
**When**: Testing platform-specific implementation
- Use `@pytest.mark.<platform>` markers
- Mock subprocess, verify exact commands
- Test OS-specific flags and features

### Guidelines
- **Mock all I/O**: File system, network, OS calls
- **No admin required**: Tests run as regular user
- **No real services**: Mock service interactions
- **Use fixtures**: From `conftest.py`
- **Verify commands**: Test exact strings in platform tests

## Shared Fixtures

**`test/conftest.py`**: `stop_event`, `mock_env`, `mock_svc_mgr`, `mock_power_mgr`, `mock_sys_info`, `mock_input_mon`, `mock_diag`, `minimal_config`, `full_config`, `tmp_config_dir`

**`test/test_platforms/conftest.py`**: `current_platform`, `platform_factory`, `mock_power_mgr_platform_aware`

**`test/test_interfaces/conftest.py`**: `service_manager`, `power_manager`, `system_info`, `environment` (parametrized for all platforms)

## Platform Support

| Platform | Status | Shared Tests | Platform Tests |
|----------|--------|--------------|----------------|
| Windows | ✅ Complete | ✅ Pass | ✅ Pass (32 tests) |
| macOS | ✅ Complete | ✅ Pass | ✅ Pass |
| Linux | 🔨 In Development | ✅ Pass (mocked) | 🔨 Implementing |
| Android | 📋 Planned | ✅ Ready | 📋 Not started |
| iOS | 📋 Planned | ✅ Ready | 📋 Not started |

**Current total**: 295 tests (263 platform-agnostic, 32 Windows-specific)

## CI/CD

Tests run on every PR and push to `master` via [`.github/workflows/test.yml`](.github/workflows/test.yml).
- **Python**: 3.11, 3.12, 3.13
- **Platforms**: Windows, Linux (Ubuntu), macOS

## Troubleshooting

**Import errors**: Ensure you're in project root and ran `pip install -r requirement.txt`

**Platform tests skip**: Expected! Platform tests auto-skip or mock on wrong OS. Use mocks to develop on any OS.

**Test on real Linux**: Use WSL2, Docker, or real Linux machine. Same tests run with real systemctl instead of mocks.
