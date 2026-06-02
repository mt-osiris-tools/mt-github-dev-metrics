#!/usr/bin/env bash
set -euo pipefail

REPO_URL_DEFAULT="https://github.com/mt-osiris-tools/mt-github-dev-metrics.git"
BRANCH_DEFAULT="main"
INSTALL_ROOT_DEFAULT="${XDG_DATA_HOME:-$HOME/.local/share}/github-dev-metrics"
BIN_DIR_DEFAULT="${XDG_BIN_HOME:-$HOME/.local/bin}"

repo_url="${REPO_URL:-$REPO_URL_DEFAULT}"
branch="${BRANCH:-$BRANCH_DEFAULT}"
install_root="${INSTALL_ROOT:-$INSTALL_ROOT_DEFAULT}"
bin_dir="${BIN_DIR:-$BIN_DIR_DEFAULT}"
update_only=false

usage() {
  cat <<EOF
Usage: install.sh [--update] [--repo-url URL] [--branch NAME] [--install-root PATH] [--bin-dir PATH]

Environment overrides:
  REPO_URL, BRANCH, INSTALL_ROOT, BIN_DIR
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-url)
      repo_url="$2"
      shift 2
      ;;
    --branch)
      branch="$2"
      shift 2
      ;;
    --install-root)
      install_root="$2"
      shift 2
      ;;
    --bin-dir)
      bin_dir="$2"
      shift 2
      ;;
    --update)
      update_only=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v git >/dev/null 2>&1 || {
  echo "git is required for installation" >&2
  exit 1
}
command -v python3 >/dev/null 2>&1 || {
  echo "python3 is required for installation" >&2
  exit 1
}
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("python3 3.11 or newer is required")
PY

mkdir -p "$bin_dir"

if [[ "$update_only" == true ]]; then
  if [[ ! -d "$install_root/.git" ]]; then
    echo "Cannot update: $install_root is not an existing git checkout" >&2
    exit 1
  fi
  git -C "$install_root" remote set-url origin "$repo_url"
  git -C "$install_root" pull --ff-only origin "$branch"
else
  mkdir -p "$install_root"
  if [[ ! -d "$install_root/.git" ]]; then
    git clone --branch "$branch" --single-branch "$repo_url" "$install_root"
  else
    git -C "$install_root" remote set-url origin "$repo_url"
    git -C "$install_root" pull --ff-only origin "$branch"
  fi
fi

venv_dir="$install_root/.venv"
venv_py="$venv_dir/bin/python"

if [[ ! -x "$venv_py" ]]; then
  python3 -m venv "$venv_dir"
fi

"$venv_py" "$install_root/scripts/bootstrap_venv.py" --project-root "$install_root"

cat > "$bin_dir/github-dev-metrics" <<EOF
#!/usr/bin/env bash
exec "$install_root/.venv/bin/python" -m github_dev_metrics.cli "\$@"
EOF
chmod +x "$bin_dir/github-dev-metrics"

if [[ "$update_only" == true ]]; then
  echo "Updated github-dev-metrics in $install_root"
else
  echo "Installed github-dev-metrics to $bin_dir/github-dev-metrics"
  echo "Add $bin_dir to PATH if it is not already present."
fi
