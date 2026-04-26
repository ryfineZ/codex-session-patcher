#!/bin/bash
# Shared helpers for Web UI launch scripts.

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FRONTEND_DIR="${FRONTEND_DIR:-$PROJECT_DIR/web/frontend}"
FRONTEND_DIST_DIR="${FRONTEND_DIST_DIR:-$FRONTEND_DIR/dist}"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=8

web_list_python_candidates() {
    {
        if [ -n "${WEB_PYTHON_BIN:-}" ]; then
            printf '%s\n' "$WEB_PYTHON_BIN"
        fi

        for name in python3 python python3.13 python3.12 python3.11 python3.10 python3.9 python3.8; do
            if command -v "$name" >/dev/null 2>&1; then
                command -v "$name"
            fi
        done

        if command -v py >/dev/null 2>&1 && py -3 - <<'PY' >/dev/null 2>&1
import sys

raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
PY
        then
            printf '%s\n' "$(web_py_launcher_path)"
        fi

        for path in \
            /opt/homebrew/bin/python3 \
            /usr/local/bin/python3 \
            /Library/Frameworks/Python.framework/Versions/Current/bin/python3
        do
            if [ -x "$path" ]; then
                printf '%s\n' "$path"
            fi
        done

    } | awk 'NF && !seen[$0]++'
}

web_py_launcher_path() {
    local state_dir wrapper_path

    state_dir="$(web_state_dir)"
    wrapper_path="$state_dir/python-launcher.sh"
    mkdir -p "$state_dir"

    if [ ! -f "$wrapper_path" ]; then
        cat > "$wrapper_path" <<'EOF'
#!/bin/sh
exec py -3 "$@"
EOF
        chmod +x "$wrapper_path"
    fi

    printf '%s\n' "$wrapper_path"
}

web_python_is_supported() {
    "$1" - <<'PY' >/dev/null 2>&1
import sys

raise SystemExit(0 if sys.version_info >= (3, 8) else 1)
PY
}

web_python_version_string() {
    "$1" - <<'PY'
import sys

print(".".join(map(str, sys.version_info[:3])))
PY
}

web_pick_python_bin() {
    local candidate

    while IFS= read -r candidate; do
        if web_python_is_supported "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done < <(web_list_python_candidates)

    return 1
}

web_ensure_pip_available() {
    local python_bin="$1"

    if "$python_bin" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    if "$python_bin" -m ensurepip --upgrade >/dev/null 2>&1 && "$python_bin" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    return 1
}

web_state_dir() {
    local git_dir

    if [ -n "${WEB_STATE_DIR:-}" ]; then
        printf '%s\n' "$WEB_STATE_DIR"
    elif [ -d "$PROJECT_DIR/.git" ]; then
        printf '%s\n' "$PROJECT_DIR/.git/web-runtime"
    elif [ -f "$PROJECT_DIR/.git" ]; then
        git_dir="$(sed -n 's/^gitdir: //p' "$PROJECT_DIR/.git" | head -n 1)"
        if [ -n "$git_dir" ]; then
            git_dir="${git_dir%$'\r'}"
            case "$git_dir" in
                /*) ;;
                *) git_dir="$PROJECT_DIR/$git_dir" ;;
            esac
            printf '%s\n' "$git_dir/web-runtime"
        elif [ -n "${XDG_STATE_HOME:-}" ]; then
            printf '%s\n' "$XDG_STATE_HOME/codex-session-patcher"
        else
            printf '%s\n' "$PROJECT_DIR/.codex-session-patcher-state"
        fi
    elif [ -n "${XDG_STATE_HOME:-}" ]; then
        printf '%s\n' "$XDG_STATE_HOME/codex-session-patcher"
    else
        printf '%s\n' "$PROJECT_DIR/.codex-session-patcher-state"
    fi
}

web_python_deps_stamp() {
    printf '%s\n' "$(web_state_dir)/python-web-deps.stamp"
}

web_frontend_deps_stamp() {
    printf '%s\n' "$(web_state_dir)/frontend-deps.stamp"
}

web_mark_python_deps_installed() {
    local state_dir

    state_dir="$(web_state_dir)"
    mkdir -p "$state_dir"
    : > "$(web_python_deps_stamp)"
}

web_mark_frontend_deps_installed() {
    local state_dir

    state_dir="$(web_state_dir)"
    mkdir -p "$state_dir"
    : > "$(web_frontend_deps_stamp)"
}

web_python_deps_ready() {
    local python_bin="$1"
    PROJECT_DIR="$PROJECT_DIR" WEB_PYTHON_IMPORT_CHECK="${WEB_PYTHON_IMPORT_CHECK:-}" "$python_bin" - <<'PY' >/dev/null 2>&1
import os
import sys

project_dir = os.environ["PROJECT_DIR"]
sys.path.insert(0, project_dir)

snippet = os.environ.get("WEB_PYTHON_IMPORT_CHECK")
if snippet:
    exec(snippet, {})
else:
    import fastapi  # noqa: F401
    import httpx  # noqa: F401
    import pydantic  # noqa: F401
    import uvicorn  # noqa: F401
    import websockets  # noqa: F401
    import web.backend.main  # noqa: F401
PY
}

web_python_deps_need_install() {
    local python_bin="$1"
    local stamp_file

    stamp_file="$(web_python_deps_stamp)"

    if [ "${WEB_FORCE_PYTHON_DEPS_INSTALL:-0}" = "1" ]; then
        return 0
    fi

    if [ ! -f "$stamp_file" ]; then
        if web_python_deps_ready "$python_bin"; then
            web_mark_python_deps_installed
            return 1
        fi
        return 0
    fi

    if [ "$PROJECT_DIR/pyproject.toml" -nt "$stamp_file" ]; then
        return 0
    fi

    if ! web_python_deps_ready "$python_bin"; then
        return 0
    fi

    return 1
}

web_frontend_deps_need_install() {
    local python_bin="${1:-${PYTHON_BIN:-}}"
    local stamp_file

    if [ -z "$python_bin" ]; then
        python_bin="$(web_pick_python_bin || true)"
    fi

    stamp_file="$(web_frontend_deps_stamp)"

    if [ "${WEB_FORCE_FRONTEND_DEPS_INSTALL:-0}" = "1" ]; then
        return 0
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        return 0
    fi

    if [ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]; then
        return 0
    fi

    if [ -n "$python_bin" ] && ! FRONTEND_DIR="$FRONTEND_DIR" "$python_bin" - <<'PY' >/dev/null 2>&1
import json
import os
import sys

frontend_dir = os.environ["FRONTEND_DIR"]
package_json_path = os.path.join(frontend_dir, "package.json")

with open(package_json_path, encoding="utf-8") as handle:
    package_json = json.load(handle)

for section in ("dependencies", "devDependencies"):
    for package_name in package_json.get(section, {}):
        package_path = os.path.join(frontend_dir, "node_modules", *package_name.split("/"), "package.json")
        if not os.path.isfile(package_path):
            raise SystemExit(1)
PY
    then
        return 0
    fi

    if [ -f "$stamp_file" ]; then
        if [ "$FRONTEND_DIR/package.json" -nt "$stamp_file" ]; then
            return 0
        fi

        if [ -f "$FRONTEND_DIR/package-lock.json" ] && [ "$FRONTEND_DIR/package-lock.json" -nt "$stamp_file" ]; then
            return 0
        fi

        return 1
    fi

    if [ "$FRONTEND_DIR/package.json" -nt "$FRONTEND_DIR/node_modules" ]; then
        return 0
    fi

    if [ -f "$FRONTEND_DIR/package-lock.json" ] && [ "$FRONTEND_DIR/package-lock.json" -nt "$FRONTEND_DIR/node_modules" ]; then
        return 0
    fi

    web_mark_frontend_deps_installed
    return 1
}

web_frontend_sources_newer_than_dist() {
    local dist_entry="$FRONTEND_DIST_DIR/index.html"
    local source_dir
    local source_path

    for source_path in \
        "$FRONTEND_DIR/index.html" \
        "$FRONTEND_DIR/package.json" \
        "$FRONTEND_DIR/package-lock.json" \
        "$FRONTEND_DIR/vite.config.js"
    do
        if [ -f "$source_path" ] && [ "$source_path" -nt "$dist_entry" ]; then
            return 0
        fi
    done

    for source_dir in "$FRONTEND_DIR/src" "$FRONTEND_DIR/public"; do
        if [ -d "$source_dir" ] && [ "$source_dir" -nt "$dist_entry" ]; then
            return 0
        fi

        if [ -d "$source_dir" ] && find "$source_dir" -type f -newer "$dist_entry" -print -quit | grep -q .; then
            return 0
        fi
    done

    return 1
}

web_frontend_dist_ready() {
    local python_bin="${1:-${PYTHON_BIN:-}}"

    if [ ! -f "$FRONTEND_DIST_DIR/index.html" ]; then
        return 1
    fi

    if [ -z "$python_bin" ]; then
        python_bin="$(web_pick_python_bin || true)"
    fi

    if [ -z "$python_bin" ]; then
        return 1
    fi

    FRONTEND_DIST_DIR="$FRONTEND_DIST_DIR" "$python_bin" - <<'PY' >/dev/null 2>&1
import html.parser
import os
import sys

dist_dir = os.environ["FRONTEND_DIST_DIR"]
index_path = os.path.join(dist_dir, "index.html")

if not os.path.isfile(index_path):
    raise SystemExit(1)

class AssetParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("src", "href"):
            value = attrs.get(key)
            if not value:
                continue
            if value.startswith(("http://", "https://", "data:", "//", "#")):
                continue
            self.paths.append(value)

parser = AssetParser()
with open(index_path, encoding="utf-8") as handle:
    parser.feed(handle.read())

for path in parser.paths:
    relative = path.lstrip("/")
    if not relative:
        continue
    if not os.path.isfile(os.path.join(dist_dir, relative)):
        raise SystemExit(1)
PY
}

web_frontend_build_need_run() {
    local python_bin="${1:-${PYTHON_BIN:-}}"

    if [ "${WEB_FORCE_FRONTEND_BUILD:-0}" = "1" ]; then
        return 0
    fi

    if ! web_frontend_dist_ready "$python_bin"; then
        return 0
    fi

    if web_frontend_sources_newer_than_dist; then
        return 0
    fi

    return 1
}

web_port_in_use() {
    local port="$1"
    local host="$2"
    local python_bin="$3"

    "$python_bin" - "$host" "$port" <<'PY'
import errno
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

try:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
except socket.gaierror as exc:
    print(f"Cannot resolve {host}:{port}: {exc}", file=sys.stderr)
    raise SystemExit(2)

seen = set()
had_bindable_target = False
last_error = None

for family, socktype, proto, _canonname, sockaddr in infos:
    key = (family, sockaddr[0], sockaddr[1])
    if key in seen:
        continue
    seen.add(key)

    try:
        sock = socket.socket(family, socktype, proto)
    except OSError as exc:
        last_error = exc
        continue

    try:
        sock.bind(sockaddr)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise SystemExit(0)
        last_error = exc
        continue
    else:
        had_bindable_target = True
    finally:
        sock.close()

if had_bindable_target:
    raise SystemExit(1)

message = "host is not bindable"
if last_error is not None:
    message = last_error.strerror or str(last_error)

print(f"Cannot bind to {host}:{port}: {message}", file=sys.stderr)
raise SystemExit(2)
PY
}

web_find_available_port() {
    local port="$1"
    local host="$2"
    local python_bin="$3"
    local status

    while true; do
        if web_port_in_use "$port" "$host" "$python_bin"; then
            status=0
        else
            status=$?
        fi

        case "$status" in
            0)
                port=$((port + 1))
                ;;
            1)
                printf '%s\n' "$port"
                return 0
                ;;
            *)
                return "$status"
                ;;
        esac
    done
}
