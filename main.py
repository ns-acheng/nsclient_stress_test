import sys
import os
import json
import logging
import platform
import shutil

# Ensure current dir is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from stress_test import StressTest, ITER_FILTER
from util_log import LogSetup
from util_validate import init_validator
from util_config import AgentConfigManager

TEMPLATE_DIRS = {
    "win": os.path.join("data", "template", "windows"),
    "mac": os.path.join("data", "template", "macos"),
    "linux": os.path.join("data", "template", "linux"),
}

def _list_templates():
    templates = []
    for prefix, folder in TEMPLATE_DIRS.items():
        if os.path.isdir(folder):
            for name in sorted(os.listdir(folder)):
                if name.endswith(".json"):
                    templates.append(f"{prefix}/{name[:-5]}")
    return templates

def _choose_template_interactive():
    templates = _list_templates()
    if not templates:
        print("No templates found.", file=sys.stderr)
        sys.exit(1)
    print("Available templates:")
    for i, t in enumerate(templates, 1):
        print(f"  [{i}] {t}")
    choice = input("Select template (number or name): ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(templates):
            return [templates[idx]]
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)
    if choice in templates:
        return [choice]
    print(f"Template '{choice}' not found.", file=sys.stderr)
    sys.exit(1)

def _parse_template_args():
    for arg in sys.argv[1:]:
        if arg == "--template":
            return _choose_template_interactive()
        if arg.startswith("--template="):
            val = arg[len("--template="):]
            ids = [t.strip() for t in val.split(",") if t.strip()]
            return ids if ids else _choose_template_interactive()
    return None

def _resolve_template_name(folder, name):
    exact = os.path.join(folder, f"{name}.json")
    if os.path.isfile(exact):
        return name
    matches = [
        f[:-5] for f in os.listdir(folder)
        if f.endswith(".json") and f[:-5].startswith(name)
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"Ambiguous template '{name}': {matches}", file=sys.stderr)
        sys.exit(1)
    return None

def _apply_template(template_id):
    parts = template_id.split("/", 1)
    if len(parts) != 2:
        print(f"Invalid template: '{template_id}'. Use 'win/<name>', 'mac/<name>', or 'linux/<name>'.", file=sys.stderr)
        sys.exit(1)
    prefix, name = parts
    folder = TEMPLATE_DIRS.get(prefix)
    if folder is None:
        print(f"Unknown prefix '{prefix}'. Use: {', '.join(TEMPLATE_DIRS)}", file=sys.stderr)
        sys.exit(1)
    resolved = _resolve_template_name(folder, name)
    if resolved is None:
        print(f"Template not found: '{template_id}'", file=sys.stderr)
        sys.exit(1)
    src = os.path.join(folder, f"{resolved}.json")
    dst = os.path.join("data", "config.json")
    shutil.copy(src, dst)
    print(f"Applied template '{prefix}/{resolved}' -> {dst}")

def get_factory():
    system = platform.system().lower()
    if system == "windows":
        from platforms.windows.factory import WindowsFactory
        return WindowsFactory()
    elif system == "darwin":
        from platforms.macos.factory import MacOSFactory
        return MacOSFactory()
    elif system == "linux":
        from platforms.linux.factory import LinuxFactory
        return LinuxFactory()
    else:
        raise NotImplementedError(f"OS {system} not supported")

def main():
    # 0. Setup CWD
    try:
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass

    # 1. Parse Args
    template_ids = _parse_template_args()  # list[str] or None

    is_continue_mode = False
    existing_log_dir = None
    if len(sys.argv) > 1 and "-continue" in sys.argv:
        is_continue_mode = True
        try:
            sys_path = os.path.join("data", "state.json")
            with open(sys_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                existing_log_dir = d.get("cur_log_dir", None)
        except Exception as e:
            print(f"Error reading state for continue mode: {e}", file=sys.stderr)

    # 2. Initialize Platform (once for all runs)
    try:
        factory = get_factory()
        power = factory.create_power_manager()
        service = factory.create_service_manager()
        system = factory.create_system_info()
        input_mon = factory.create_input_monitor()
        diag = factory.create_diagnostics()
        env = factory.create_environment()
        init_validator(env)
    except Exception as e:
        print(f"Failed to initialize platform components: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Run once per template (or once with no template)
    run_list = template_ids if template_ids else [None]
    interrupted = False
    for i, template_id in enumerate(run_list):
        if template_id is not None:
            _apply_template(template_id)

        log_suffix = template_id.split("/", 1)[-1] if template_id else None
        _existing = existing_log_dir if i == 0 else None
        _continue = is_continue_mode if i == 0 else False

        try:
            log_helper = LogSetup(_existing, suffix=log_suffix)
            log_helper.setup_logging()
            logger = logging.getLogger()
            logger.addFilter(ITER_FILTER)
            current_log_dir = log_helper.get_log_folder()

            try:
                config_src = os.path.join("data", "config.json")
                if os.path.exists(config_src):
                    shutil.copy(config_src, current_log_dir)
                    logger.info(f"Copied config.json to {current_log_dir}")
            except Exception as e:
                logger.warning(f"Failed to copy config.json to log folder: {e}")
        except Exception as e:
            print(f"Critical error during logging setup: {e}", file=sys.stderr)
            sys.exit(1)

        logger.info(f"Platform: {platform.system()} initialized.")
        if template_id:
            logger.info(f"Template applied: {template_id} -> data/config.json")

        config_mgr = AgentConfigManager(env)
        runner = StressTest(
            current_log_dir, power, service, system, input_mon, diag, config_mgr, _continue
        )

        if len(run_list) > 1:
            logger.info(f"[{i + 1}/{len(run_list)}] Running template: {template_id}")
        try:
            logger.info(f"Logging initialized: {current_log_dir}")
            setup_ok = runner.setup()
            if setup_ok is False:
                logger.error("Setup did not complete. Skipping run loop.")
            else:
                runner.run()
        except KeyboardInterrupt:
            logger.info("Stopped by user.")
            interrupted = True
        except Exception:
            logger.exception("Fatal error in main loop:")
        finally:
            runner.tear_down()

        if interrupted:
            break

    sys.exit(0)

if __name__ == "__main__":
    main()
