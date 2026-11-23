import ast
import os
import re
import signal
import shutil
import subprocess
import sys
import venv

RUNNING_PROCESSES = {}

PACKAGE_MAP = {
    "telebot": "pyTelegramBotAPI",
    "telegram": "python-telegram-bot",
    "discord": "discord.py",
    "pyrogram": "kurigram",
    "pytgcalls": "py-tgcalls",
    "famgateway": "famgateway",
    "telethon": "telethon",
    "aiogram": "aiogram",
    "aiohttp": "aiohttp",
    "qrcode": "qrcode[pil]",
    "PIL": "Pillow",
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "fitz": "PyMuPDF",
    "yt_dlp": "yt-dlp",
    "dotenv": "python-dotenv",
    "yaml": "PyYAML",
    "sklearn": "scikit-learn",
    "Crypto": "pycryptodome",
    "dateutil": "python-dateutil",
    "dns": "dnspython",
    "psycopg2": "psycopg2-binary",
    "mysql": "mysql-connector-python",
}

BLOCKED_PATTERNS = [
    r"(^|\s|;|&&|\|\|)rm\s+-rf\s+/(\s|$|\*)",
    r"(^|\s|;|&&|\|\|)mkfs\.",
    r"(^|\s|;|&&|\|\|)dd\s+if=",
    r":\(\)\{\s*:\|:\&\s*\};:",
    r"(^|\s|;|&&|\|\|)shutdown(\s|$)",
    r"(^|\s|;|&&|\|\|)reboot(\s|$)",
]


def get_bot_paths(bot_name):
    base_dir = os.path.abspath(os.path.join("hosted_bots", bot_name))
    venv_dir = os.path.join(base_dir, "venv")
    log_file = os.path.join(base_dir, "bot.log")
    if os.name == "nt":
        python_exe = os.path.join(venv_dir, "Scripts", "python.exe")
        pip_exe = os.path.join(venv_dir, "Scripts", "pip.exe")
        bin_dir = os.path.join(venv_dir, "Scripts")
    else:
        python_exe = os.path.join(venv_dir, "bin", "python")
        pip_exe = os.path.join(venv_dir, "bin", "pip")
        bin_dir = os.path.join(venv_dir, "bin")
    return base_dir, venv_dir, log_file, python_exe, pip_exe, bin_dir


def ensure_venv(bot_name):
    base_dir, venv_dir, _, python_exe, pip_exe, bin_dir = get_bot_paths(bot_name)
    os.makedirs(base_dir, exist_ok=True)
    if not os.path.exists(python_exe):
        venv.create(venv_dir, with_pip=True)
    return base_dir, venv_dir, python_exe, pip_exe, bin_dir


def get_local_modules(base_dir):
    local_mods = set()
    if os.path.exists(base_dir):
        for item in os.listdir(base_dir):
            if item.endswith(".py"):
                local_mods.add(os.path.splitext(item)[0])
            elif os.path.isdir(os.path.join(base_dir, item)) and item != "venv":
                local_mods.add(item)
    return local_mods


def get_required_packages(file_path, base_dir):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        tree = ast.parse(f.read(), filename=file_path)

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    stdlib = sys.stdlib_module_names
    local_mods = get_local_modules(base_dir)
    third_party = [pkg for pkg in imports if pkg not in stdlib and pkg not in local_mods]
    pip_packages = [PACKAGE_MAP.get(pkg, pkg) for pkg in third_party]
    return list(set(pip_packages))


def install_dependencies(bot_name, script_path):
    base_dir, _, _, pip_exe, _ = ensure_venv(bot_name)
    subprocess.run([pip_exe, "install", "--upgrade", "pip"], capture_output=True, text=True, timeout=180)

    req_file = os.path.join(base_dir, "requirements.txt")
    installed = []
    failed = []

    if os.path.exists(req_file):
        res = subprocess.run([pip_exe, "install", "-r", req_file], capture_output=True, text=True, timeout=300)
        if res.returncode == 0:
            installed.append("requirements.txt")
        else:
            failed.append("requirements.txt")

    packages = get_required_packages(script_path, base_dir)
    for pkg in packages:
        res = subprocess.run([pip_exe, "install", pkg], capture_output=True, text=True, timeout=300)
        if res.returncode == 0:
            installed.append(pkg)
        else:
            if pkg == "kurigram":
                res2 = subprocess.run([pip_exe, "install", "pyrogram"], capture_output=True, text=True, timeout=300)
                if res2.returncode == 0:
                    installed.append("pyrogram")
                    continue
            failed.append(pkg)

    return installed, failed


def run_in_venv(bot_name, command_str, timeout=240):
    """Kisi bhi specific bot ke isolated virtual environment ke andar pip ya command chalata hai."""
    cmd_clean = (command_str or "").strip()
    if not cmd_clean:
        return False, "Koi command khali nahi hona chahiye."

    for pat in BLOCKED_PATTERNS:
        if re.search(pat, cmd_clean):
            return False, "Safety Guard: Yeh destructive command block kar diya gaya hai."

    base_dir, venv_dir, _, _, _, bin_dir = ensure_venv(bot_name)

    env = os.environ.copy()
    env["VIRTUAL_ENV"] = venv_dir
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env.pop("PYTHONHOME", None)

    try:
        completed = subprocess.run(
            cmd_clean,
            shell=True,
            cwd=base_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        combined = (completed.stdout or "") + (
            f"\n[STDERR]\n{completed.stderr}" if completed.stderr else ""
        )
        combined = combined.strip() or "(Command completed with no output)"
        if len(combined) > 3300:
            combined = "...[truncated]\n" + combined[-3300:]

        ok = completed.returncode == 0
        header = f"Exit Code: `{completed.returncode}`"
        return ok, f"{header}\n```\n{combined}\n```"
    except subprocess.TimeoutExpired:
        return False, f"Command timeout ({timeout}s) exceed kar gaya."
    except Exception as e:
        return False, f"Execution error: `{e}`"


def is_pid_alive(pid):
    if not pid or pid <= 0:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def start_bot(bot_name, script_path):
    if is_running(bot_name):
        proc_info = RUNNING_PROCESSES.get(bot_name)
        pid = proc_info[0].pid if proc_info else "active"
        return False, f"Bot pehle se chal raha hai (PID: {pid})."

    base_dir, _, log_file, python_exe, _, _ = ensure_venv(bot_name)
    if not os.path.exists(script_path):
        return False, f"Entry script nahi mili: {script_path}"

    log_f = open(log_file, "a", encoding="utf-8")
    popen_kwargs = {
        "cwd": base_dir,
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
    }
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen([python_exe, os.path.abspath(script_path)], **popen_kwargs)
    RUNNING_PROCESSES[bot_name] = (process, log_f)
    return True, f"Bot start ho gaya! (PID: {process.pid})"


def stop_bot(bot_name, saved_pid=None):
    stopped = False
    if bot_name in RUNNING_PROCESSES:
        process, log_f = RUNNING_PROCESSES.pop(bot_name)
        try:
            if os.name != "nt":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                if os.name != "nt":
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
            except Exception:
                pass
        try:
            log_f.close()
        except Exception:
            pass
        stopped = True

    if not stopped and saved_pid and is_pid_alive(saved_pid):
        try:
            os.kill(int(saved_pid), signal.SIGTERM)
            stopped = True
        except Exception:
            pass

    if stopped:
        return True, "Bot stop kar diya gaya hai."
    return False, "Bot abhi run nahi ho raha."


def is_running(bot_name, saved_pid=None):
    if bot_name in RUNNING_PROCESSES:
        process, log_f = RUNNING_PROCESSES[bot_name]
        if process.poll() is None:
            return True
        RUNNING_PROCESSES.pop(bot_name, None)
        try:
            log_f.close()
        except Exception:
            pass
    if saved_pid and is_pid_alive(saved_pid):
        return True
    return False


def get_logs(bot_name, lines=40):
    _, _, log_file, _, _, _ = get_bot_paths(bot_name)
    if not os.path.exists(log_file):
        return "Abhi tak koi logs nahi hain."
    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.readlines()
    return "".join(content[-lines:]) or "Log file khali hai."


def get_log_file_path(bot_name):
    _, _, log_file, _, _, _ = get_bot_paths(bot_name)
    return log_file if os.path.exists(log_file) else None


def clear_logs(bot_name):
    _, _, log_file, _, _, _ = get_bot_paths(bot_name)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("")


def delete_bot_files(bot_name, saved_pid=None):
    stop_bot(bot_name, saved_pid=saved_pid)
    base_dir, _, _, _, _, _ = get_bot_paths(bot_name)
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir, ignore_errors=True)
