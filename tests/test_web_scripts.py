import os
import shutil
import shlex
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_COMMON = REPO_ROOT / "scripts" / "web-common.sh"
FRONTEND_DIR = REPO_ROOT / "web" / "frontend"


def run_bash(script: str, *, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", "-c", f"set -euo pipefail\n{script}"],
        cwd=REPO_ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


def vite_proxy_test_ready(*, frontend_dir: Path = FRONTEND_DIR, node_bin: str | None = None) -> bool:
    node_bin = node_bin or shutil.which("node")
    if not node_bin:
        return False

    required_packages = (
        frontend_dir / "node_modules" / "vite" / "package.json",
        frontend_dir / "node_modules" / "@vitejs" / "plugin-vue" / "package.json",
    )
    return all(path.exists() for path in required_packages)


def link_host_tool(fake_bin: Path, tool: str):
    tool_path = shutil.which(tool)
    if not tool_path:
        pytest.skip(f"{tool} is required for this test")

    (fake_bin / tool).symlink_to(tool_path)


def find_non_loopback_ipv4() -> str | None:
    candidates: list[str] = []

    for remote in ("8.8.8.8", "1.1.1.1"):
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect((remote, 80))
            candidates.append(probe.getsockname()[0])
        except OSError:
            pass
        finally:
            probe.close()

    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    except OSError:
        infos = []

    for info in infos:
        addr = info[4][0]
        candidates.append(addr)

    for candidate in candidates:
        if candidate and not candidate.startswith("127."):
            return candidate

    return None


def test_vite_proxy_test_ready_requires_frontend_deps(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()

    assert not vite_proxy_test_ready(frontend_dir=frontend_dir, node_bin="/usr/bin/node")


def test_vite_proxy_test_ready_accepts_installed_frontend_deps(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    (frontend_dir / "node_modules" / "vite").mkdir(parents=True)
    (frontend_dir / "node_modules" / "@vitejs" / "plugin-vue").mkdir(parents=True)
    (frontend_dir / "node_modules" / "vite" / "package.json").write_text("{}", encoding="utf-8")
    (frontend_dir / "node_modules" / "@vitejs" / "plugin-vue" / "package.json").write_text("{}", encoding="utf-8")

    assert vite_proxy_test_ready(frontend_dir=frontend_dir, node_bin="/usr/bin/node")


def test_find_available_port_checks_requested_host_without_lsof(tmp_path: Path):
    host = find_non_loopback_ipv4()
    if not host:
        pytest.skip("non-loopback IPv4 address is required for this test")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    for tool in ("awk", "dirname"):
        link_host_tool(fake_bin, tool)

    python_bin = fake_bin / "python3"
    python_bin.symlink_to(Path(sys.executable))

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind((host, 0))
    listener.listen()
    port = listener.getsockname()[1]

    try:
        result = run_bash(
            "\n".join(
                [
                    f"source {shlex.quote(str(WEB_COMMON))}",
                    f'PYTHON_BIN={shlex.quote(str(python_bin))}',
                    f'PORT=$(web_find_available_port "{port}" "0.0.0.0" "$PYTHON_BIN")',
                    'printf "%s\\n" "$PORT"',
                ]
            ),
            env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
        )
    finally:
        listener.close()

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(port + 1)


def test_find_available_port_fails_fast_for_non_bindable_host():
    script = "\n".join(
        [
            f"source {shlex.quote(str(WEB_COMMON))}",
            f'PYTHON_BIN={shlex.quote(sys.executable)}',
            'web_find_available_port "39019" "203.0.113.10" "$PYTHON_BIN"',
        ]
    )

    try:
        result = subprocess.run(
            ["bash", "-c", f"set -euo pipefail\n{script}"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=2,
        )
    except subprocess.TimeoutExpired as exc:
        pytest.fail(f"web_find_available_port hung for a non-bindable host: {exc}")

    assert result.returncode != 0
    assert "203.0.113.10" in result.stderr


def test_find_available_port_checks_localhost_across_address_families():
    listener = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    try:
        listener.bind(("::1", 0))
    except OSError:
        listener.close()
        pytest.skip("IPv6 localhost listener is required for this test")

    listener.listen()
    port = listener.getsockname()[1]

    try:
        result = run_bash(
            "\n".join(
                [
                    f"source {shlex.quote(str(WEB_COMMON))}",
                    f'PYTHON_BIN={shlex.quote(sys.executable)}',
                    f'PORT=$(web_find_available_port "{port}" "localhost" "$PYTHON_BIN")',
                    'printf "%s\\n" "$PORT"',
                ]
            )
        )
    finally:
        listener.close()

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(port + 1)


def test_pick_python_bin_supports_versioned_interpreter_names(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    for tool in ("awk", "dirname"):
        link_host_tool(fake_bin, tool)

    versioned_python = fake_bin / "python3.13"
    versioned_python.symlink_to(Path(sys.executable))

    result = run_bash(
        f"source {shlex.quote(str(WEB_COMMON))}; web_pick_python_bin",
        env={"PATH": f"{fake_bin}:/bin"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(versioned_python)


def test_pick_python_bin_prefers_generic_launchers_before_versioned_fallbacks(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()

    generic_python = fake_bin / "python3"
    generic_python.symlink_to(Path(sys.executable))

    versioned_python = fake_bin / "python3.13"
    versioned_python.symlink_to(Path(sys.executable))

    result = run_bash(
        f"source {shlex.quote(str(WEB_COMMON))}; web_pick_python_bin",
        env={"PATH": f"{fake_bin}:/usr/bin:/bin"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(generic_python)


def test_pick_python_bin_supports_py_launcher(tmp_path: Path):
    fake_bin = tmp_path / "bin"
    state_dir = tmp_path / "state"
    fake_bin.mkdir()
    state_dir.mkdir()

    for tool in ("awk", "dirname"):
        link_host_tool(fake_bin, tool)

    py_launcher = fake_bin / "py"
    py_launcher.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'if [ \"$1\" = \"-3\" ]; then',
                "  shift",
                "fi",
                f'exec {shlex.quote(sys.executable)} \"$@\"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    py_launcher.chmod(py_launcher.stat().st_mode | stat.S_IXUSR)

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f"WEB_STATE_DIR={shlex.quote(str(state_dir))}",
                "python_bin=$(web_pick_python_bin)",
                'printf "%s\\n" "$python_bin"',
                '"$python_bin" - <<\'PY\'',
                "print('ok')",
                "PY",
            ]
        ),
        env={"PATH": f"{fake_bin}:/bin"},
    )

    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) >= 2
    assert lines[0].endswith("python-launcher.sh")
    assert lines[1] == "ok"


def test_python_deps_install_is_skipped_when_stamp_is_fresh(tmp_path: Path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    stamp = state_dir / "python-web-deps.stamp"
    stamp.write_text("ok", encoding="utf-8")

    now = time.time()
    os.utime(stamp, (now, now))

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f"PROJECT_DIR={shlex.quote(str(REPO_ROOT))}",
                f"WEB_STATE_DIR={shlex.quote(str(state_dir))}",
                f"WEB_PYTHON_IMPORT_CHECK={shlex.quote('import sys')}",
                f'PYTHON_BIN={shlex.quote(sys.executable)}',
                'if web_python_deps_need_install "$PYTHON_BIN"; then echo install; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "skip"


def test_python_deps_install_is_skipped_when_imports_are_ready_without_stamp(tmp_path: Path):
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f"PROJECT_DIR={shlex.quote(str(REPO_ROOT))}",
                f"WEB_STATE_DIR={shlex.quote(str(state_dir))}",
                f"WEB_PYTHON_IMPORT_CHECK={shlex.quote('import sys')}",
                f'PYTHON_BIN={shlex.quote(sys.executable)}',
                'if web_python_deps_need_install "$PYTHON_BIN"; then echo install; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "skip"
    assert (state_dir / "python-web-deps.stamp").exists()


def test_frontend_install_required_when_package_lock_is_newer(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    node_modules = frontend_dir / "node_modules"
    node_modules.mkdir()
    vite_bin = node_modules / ".bin"
    vite_bin.mkdir()
    vite_file = vite_bin / "vite"
    vite_file.write_text("#!/bin/sh\n", encoding="utf-8")
    vite_file.chmod(vite_file.stat().st_mode | stat.S_IXUSR)

    npm_lock_copy = node_modules / ".package-lock.json"
    npm_lock_copy.write_text("old", encoding="utf-8")
    package_lock = frontend_dir / "package-lock.json"
    package_lock.write_text("new", encoding="utf-8")

    old = time.time() - 60
    new = time.time()
    os.utime(node_modules, (old, old))
    os.utime(npm_lock_copy, (old, old))
    os.utime(package_lock, (new, new))

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f'PYTHON_BIN={shlex.quote(sys.executable)}',
                f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}",
                'if web_frontend_deps_need_install "$PYTHON_BIN"; then echo install; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "install"


def test_frontend_install_is_skipped_without_npm_hidden_lock_when_tree_is_current(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    state_dir = tmp_path / "state"
    frontend_dir.mkdir()
    state_dir.mkdir()

    node_modules = frontend_dir / "node_modules"
    node_modules.mkdir()
    vite_bin = node_modules / ".bin"
    vite_bin.mkdir()
    vite_file = vite_bin / "vite"
    vite_file.write_text("#!/bin/sh\n", encoding="utf-8")
    vite_file.chmod(vite_file.stat().st_mode | stat.S_IXUSR)

    package_json = frontend_dir / "package.json"
    package_lock = frontend_dir / "package-lock.json"
    package_json.write_text("{}", encoding="utf-8")
    package_lock.write_text("{}", encoding="utf-8")

    old = time.time() - 60
    new = time.time()
    os.utime(package_json, (old, old))
    os.utime(package_lock, (old, old))
    os.utime(node_modules, (new, new))

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f'PYTHON_BIN={shlex.quote(sys.executable)}',
                f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}",
                f"WEB_STATE_DIR={shlex.quote(str(state_dir))}",
                'if web_frontend_deps_need_install "$PYTHON_BIN"; then echo install; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "skip"


def test_frontend_install_required_when_runtime_packages_are_missing_despite_fresh_stamp(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    state_dir = tmp_path / "state"
    frontend_dir.mkdir()
    state_dir.mkdir()

    node_modules = frontend_dir / "node_modules"
    (node_modules / ".bin").mkdir(parents=True)
    (node_modules / "vite").mkdir(parents=True)
    (node_modules / "@vitejs" / "plugin-vue").mkdir(parents=True)

    vite_file = node_modules / ".bin" / "vite"
    vite_file.write_text("#!/bin/sh\n", encoding="utf-8")
    vite_file.chmod(vite_file.stat().st_mode | stat.S_IXUSR)
    (node_modules / "vite" / "package.json").write_text("{}", encoding="utf-8")
    (node_modules / "@vitejs" / "plugin-vue" / "package.json").write_text("{}", encoding="utf-8")

    package_json = frontend_dir / "package.json"
    package_lock = frontend_dir / "package-lock.json"
    package_json.write_text((FRONTEND_DIR / "package.json").read_text(encoding="utf-8"), encoding="utf-8")
    package_lock.write_text("{}", encoding="utf-8")

    stamp = state_dir / "frontend-deps.stamp"
    stamp.write_text("ok", encoding="utf-8")

    old = time.time() - 60
    new = time.time()
    os.utime(package_json, (old, old))
    os.utime(package_lock, (old, old))
    os.utime(stamp, (new, new))

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f'PYTHON_BIN={shlex.quote(sys.executable)}',
                f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}",
                f"WEB_STATE_DIR={shlex.quote(str(state_dir))}",
                'if web_frontend_deps_need_install "$PYTHON_BIN"; then echo install; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "install"


def test_frontend_build_is_skipped_when_dist_is_current(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    dist_dir = frontend_dir / "dist"
    src_dir = frontend_dir / "src"
    public_dir = frontend_dir / "public"
    dist_dir.mkdir(parents=True)
    src_dir.mkdir()
    public_dir.mkdir()

    files = [
        frontend_dir / "index.html",
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
        frontend_dir / "vite.config.js",
        src_dir / "main.js",
        public_dir / "logo.svg",
    ]
    for path in files:
        path.write_text("content", encoding="utf-8")

    dist_entry = dist_dir / "index.html"
    dist_entry.write_text("dist", encoding="utf-8")

    old = time.time() - 60
    new = time.time()
    for path in files:
        os.utime(path, (old, old))
    os.utime(dist_entry, (new, new))

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}",
                f"FRONTEND_DIST_DIR={shlex.quote(str(dist_dir))}",
                'if web_frontend_build_need_run; then echo build; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "skip"


def test_frontend_build_runs_when_source_file_is_deleted_after_dist(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    dist_dir = frontend_dir / "dist"
    src_dir = frontend_dir / "src"
    dist_dir.mkdir(parents=True)
    src_dir.mkdir()

    tracked_paths = [
        frontend_dir / "index.html",
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
        frontend_dir / "vite.config.js",
        src_dir / "main.js",
    ]
    for path in tracked_paths:
        path.write_text("content", encoding="utf-8")

    dist_entry = dist_dir / "index.html"
    dist_entry.write_text("dist", encoding="utf-8")

    old = time.time() - 60
    new = time.time()
    for path in tracked_paths:
        os.utime(path, (old, old))
    os.utime(dist_entry, (new, new))

    (src_dir / "main.js").unlink()
    os.utime(src_dir, (new + 5, new + 5))

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}",
                f"FRONTEND_DIST_DIR={shlex.quote(str(dist_dir))}",
                'if web_frontend_build_need_run; then echo build; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "build"


def test_frontend_build_runs_when_dist_assets_are_missing(tmp_path: Path):
    frontend_dir = tmp_path / "frontend"
    dist_dir = frontend_dir / "dist"
    assets_dir = dist_dir / "assets"
    src_dir = frontend_dir / "src"
    dist_dir.mkdir(parents=True)
    assets_dir.mkdir()
    src_dir.mkdir()

    for path in [
        frontend_dir / "index.html",
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
        frontend_dir / "vite.config.js",
        src_dir / "main.js",
    ]:
        path.write_text("content", encoding="utf-8")

    asset_file = assets_dir / "app.js"
    asset_file.write_text("console.log('ok')", encoding="utf-8")
    dist_entry = dist_dir / "index.html"
    dist_entry.write_text('<script type="module" src="/assets/app.js"></script>', encoding="utf-8")

    old = time.time() - 60
    new = time.time()
    for path in [
        frontend_dir / "index.html",
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
        frontend_dir / "vite.config.js",
        src_dir / "main.js",
    ]:
        os.utime(path, (old, old))
    os.utime(asset_file, (new, new))
    os.utime(dist_entry, (new, new))

    asset_file.unlink()

    result = run_bash(
        "\n".join(
            [
                f"source {shlex.quote(str(WEB_COMMON))}",
                f"FRONTEND_DIR={shlex.quote(str(frontend_dir))}",
                f"FRONTEND_DIST_DIR={shlex.quote(str(dist_dir))}",
                'if web_frontend_build_need_run; then echo build; else echo skip; fi',
            ]
        )
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "build"


def test_start_web_skips_node_requirement_when_frontend_assets_are_current(tmp_path: Path):
    project_dir = tmp_path / "project"
    scripts_dir = project_dir / "scripts"
    frontend_dir = project_dir / "web" / "frontend"
    dist_dir = frontend_dir / "dist"
    node_modules_dir = frontend_dir / "node_modules" / ".bin"
    state_dir = tmp_path / "state"
    fake_bin = tmp_path / "bin"

    scripts_dir.mkdir(parents=True)
    dist_dir.mkdir(parents=True)
    node_modules_dir.mkdir(parents=True)
    state_dir.mkdir()
    fake_bin.mkdir()

    shutil.copy2(REPO_ROOT / "scripts" / "start-web.sh", scripts_dir / "start-web.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "web-common.sh", scripts_dir / "web-common.sh")

    (project_dir / "pyproject.toml").write_text("[build-system]\nrequires = []\n", encoding="utf-8")
    (frontend_dir / "index.html").write_text("frontend", encoding="utf-8")
    (frontend_dir / "package.json").write_text("{}", encoding="utf-8")
    (frontend_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    (dist_dir / "index.html").write_text("built", encoding="utf-8")
    vite_file = node_modules_dir / "vite"
    vite_file.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    vite_file.chmod(vite_file.stat().st_mode | stat.S_IXUSR)

    old = time.time() - 60
    new = time.time()
    for path in [
        frontend_dir / "index.html",
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
    ]:
        os.utime(path, (old, old))
    os.utime(frontend_dir / "node_modules", (new, new))
    os.utime(dist_dir / "index.html", (new, new))

    fake_python = fake_bin / "python3"
    fake_python.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'if [ \"$1\" = \"-m\" ] && [ \"$2\" = \"uvicorn\" ]; then',
                "  echo fake-uvicorn",
                "  exit 0",
                "fi",
                f'exec {shlex.quote(sys.executable)} \"$@\"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(scripts_dir / "start-web.sh")],
        cwd=project_dir,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "WEB_STATE_DIR": str(state_dir),
            "WEB_PYTHON_IMPORT_CHECK": "import sys",
            "HOST": "127.0.0.1",
            "PORT": "0",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "跳过前端依赖安装" in result.stdout
    assert "前端构建产物已是最新，跳过构建" in result.stdout
    assert "fake-uvicorn" in result.stdout


def test_start_web_skips_frontend_install_when_dist_is_current_without_node_modules(tmp_path: Path):
    project_dir = tmp_path / "project"
    scripts_dir = project_dir / "scripts"
    frontend_dir = project_dir / "web" / "frontend"
    dist_dir = frontend_dir / "dist"
    state_dir = tmp_path / "state"
    fake_bin = tmp_path / "bin"

    scripts_dir.mkdir(parents=True)
    dist_dir.mkdir(parents=True)
    state_dir.mkdir()
    fake_bin.mkdir()

    shutil.copy2(REPO_ROOT / "scripts" / "start-web.sh", scripts_dir / "start-web.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "web-common.sh", scripts_dir / "web-common.sh")

    (project_dir / "pyproject.toml").write_text("[build-system]\nrequires = []\n", encoding="utf-8")
    (frontend_dir / "index.html").write_text("frontend", encoding="utf-8")
    (frontend_dir / "package.json").write_text("{}", encoding="utf-8")
    (frontend_dir / "package-lock.json").write_text("{}", encoding="utf-8")
    (dist_dir / "index.html").write_text("built", encoding="utf-8")

    old = time.time() - 60
    new = time.time()
    for path in [
        frontend_dir / "index.html",
        frontend_dir / "package.json",
        frontend_dir / "package-lock.json",
    ]:
        os.utime(path, (old, old))
    os.utime(dist_dir / "index.html", (new, new))

    fake_python = fake_bin / "python3"
    fake_python.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'if [ \"$1\" = \"-m\" ] && [ \"$2\" = \"uvicorn\" ]; then',
                "  echo fake-uvicorn",
                "  exit 0",
                "fi",
                f'exec {shlex.quote(sys.executable)} \"$@\"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

    result = subprocess.run(
        ["bash", str(scripts_dir / "start-web.sh")],
        cwd=project_dir,
        env={
            **os.environ,
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "WEB_STATE_DIR": str(state_dir),
            "WEB_PYTHON_IMPORT_CHECK": "import sys",
            "HOST": "127.0.0.1",
            "PORT": "0",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "跳过前端依赖安装" in result.stdout
    assert "前端构建产物已是最新，跳过构建" in result.stdout
    assert "fake-uvicorn" in result.stdout


@pytest.mark.skipif(
    not vite_proxy_test_ready(),
    reason="node and frontend deps are required for vite config test",
)
def test_vite_proxy_uses_backend_env_overrides():
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            (
                "const config = (await import('./web/frontend/vite.config.js')).default;"
                "console.log(config.server.proxy['/api'].target);"
            ),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "BACKEND_HOST": "0.0.0.0", "BACKEND_PORT": "9090"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "http://0.0.0.0:9090"


@pytest.mark.skipif(
    not vite_proxy_test_ready(),
    reason="node and frontend deps are required for vite config test",
)
def test_vite_proxy_wraps_ipv6_backend_host():
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            (
                "const config = (await import('./web/frontend/vite.config.js')).default;"
                "console.log(config.server.proxy['/api'].target);"
            ),
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "BACKEND_HOST": "::1", "BACKEND_PORT": "9090"},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "http://[::1]:9090"


def test_install_script_creates_working_wrapper_with_py_launcher(tmp_path: Path):
    project_dir = tmp_path / "project"
    scripts_dir = project_dir / "scripts"
    package_dir = project_dir / "codex_session_patcher"
    home_dir = tmp_path / "home"
    state_dir = tmp_path / "state"
    fake_bin = tmp_path / "bin"

    scripts_dir.mkdir(parents=True)
    package_dir.mkdir()
    home_dir.mkdir()
    state_dir.mkdir()
    fake_bin.mkdir()

    shutil.copy2(REPO_ROOT / "scripts" / "install.sh", scripts_dir / "install.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "web-common.sh", scripts_dir / "web-common.sh")

    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "cli.py").write_text(
        "\n".join(
            [
                "import sys",
                "print('wrapper-ok', *sys.argv[1:])",
                "",
            ]
        ),
        encoding="utf-8",
    )

    for tool in ("awk", "dirname"):
        link_host_tool(fake_bin, tool)

    py_launcher = fake_bin / "py"
    py_launcher.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                'if [ \"$1\" = \"-3\" ]; then',
                "  shift",
                "fi",
                f'exec {shlex.quote(sys.executable)} \"$@\"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    py_launcher.chmod(py_launcher.stat().st_mode | stat.S_IXUSR)

    install_result = subprocess.run(
        ["bash", str(scripts_dir / "install.sh")],
        cwd=project_dir,
        env={
            **os.environ,
            "HOME": str(home_dir),
            "WEB_STATE_DIR": str(state_dir),
            "PATH": f"{fake_bin}:/bin",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert install_result.returncode == 0, install_result.stderr

    wrapper_path = home_dir / ".local" / "bin" / "codex-patcher"
    assert wrapper_path.exists()
    wrapper_contents = wrapper_path.read_text(encoding="utf-8")
    assert "web-common.sh" in wrapper_contents
    assert "-m codex_session_patcher.cli" in wrapper_contents

    wrapper_run = subprocess.run(
        [str(wrapper_path), "abc"],
        cwd=project_dir,
        env={
            **os.environ,
            "HOME": str(home_dir),
            "WEB_STATE_DIR": str(state_dir),
            "PATH": f"{fake_bin}:/bin",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert wrapper_run.returncode == 0, wrapper_run.stderr
    assert wrapper_run.stdout.strip() == "wrapper-ok abc"


def test_install_script_wrapper_supports_spaces_in_project_path(tmp_path: Path):
    project_dir = tmp_path / "project with spaces"
    scripts_dir = project_dir / "scripts"
    package_dir = project_dir / "codex_session_patcher"
    home_dir = tmp_path / "home"

    scripts_dir.mkdir(parents=True)
    package_dir.mkdir()
    home_dir.mkdir()

    shutil.copy2(REPO_ROOT / "scripts" / "install.sh", scripts_dir / "install.sh")
    shutil.copy2(REPO_ROOT / "scripts" / "web-common.sh", scripts_dir / "web-common.sh")

    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "cli.py").write_text(
        "\n".join(
            [
                "import sys",
                "print('space-ok', *sys.argv[1:])",
                "",
            ]
        ),
        encoding="utf-8",
    )

    install_result = subprocess.run(
        ["bash", str(scripts_dir / "install.sh")],
        cwd=project_dir,
        env={
            **os.environ,
            "HOME": str(home_dir),
            "PATH": os.environ["PATH"],
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert install_result.returncode == 0, install_result.stderr

    wrapper_path = home_dir / ".local" / "bin" / "codex-patcher"
    wrapper_run = subprocess.run(
        [str(wrapper_path), "abc"],
        cwd=project_dir,
        env={
            **os.environ,
            "HOME": str(home_dir),
            "PATH": os.environ["PATH"],
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert wrapper_run.returncode == 0, wrapper_run.stderr
    assert wrapper_run.stdout.strip() == "space-ok abc"


def test_web_state_dir_uses_gitdir_for_worktree_checkout(tmp_path: Path):
    project_dir = tmp_path / "project"
    scripts_dir = project_dir / "scripts"
    git_dir = tmp_path / "git-store" / "worktrees" / "demo"

    scripts_dir.mkdir(parents=True)
    git_dir.mkdir(parents=True)

    shutil.copy2(REPO_ROOT / "scripts" / "web-common.sh", scripts_dir / "web-common.sh")
    (project_dir / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", "-c", "source scripts/web-common.sh && web_state_dir"],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(git_dir / "web-runtime")


def test_web_state_dir_trims_carriage_return_from_worktree_gitdir(tmp_path: Path):
    project_dir = tmp_path / "project"
    scripts_dir = project_dir / "scripts"
    git_dir = tmp_path / "git-store" / "worktrees" / "demo"

    scripts_dir.mkdir(parents=True)
    git_dir.mkdir(parents=True)

    shutil.copy2(REPO_ROOT / "scripts" / "web-common.sh", scripts_dir / "web-common.sh")
    (project_dir / ".git").write_text(f"gitdir: {git_dir}\r\n", encoding="utf-8", newline="")

    result = subprocess.run(
        ["bash", "-c", "source scripts/web-common.sh && web_state_dir"],
        cwd=project_dir,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(git_dir / "web-runtime")
