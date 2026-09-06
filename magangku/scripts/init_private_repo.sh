#!/usr/bin/env bash
#
# Menjadikan folder `magangku/` sebagai repo Git mandiri lalu mendorongnya
# ke repositori PRIVATE milik Anda sendiri.
#
# Pakai:
#   bash scripts/init_private_repo.sh <nama-repo> [--owner USER] [--public]
#
# Contoh:
#   bash scripts/init_private_repo.sh magangku-autoapply
#
# Prasyarat: git, dan (opsional tapi disarankan) GitHub CLI `gh` yang
# sudah login dengan akun pribadi Anda: `gh auth login`
#
set -euo pipefail

REPO_NAME="${1:-magangku-autoapply}"
shift || true

OWNER=""
VISIBILITY="--private"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner) OWNER="$2"; shift 2 ;;
    --public) VISIBILITY="--public"; shift ;;
    *) echo "Opsi tidak dikenal: $1" >&2; exit 1 ;;
  esac
done

# Selalu bekerja dari root folder magangku/
cd "$(dirname "$0")/.."
SRC="$(pwd)"
STAGE="$(mktemp -d)/${REPO_NAME}"

echo "==> Menyiapkan salinan bersih di: ${STAGE}"
mkdir -p "${STAGE}"

# Salin hanya yang perlu; buang artefak, rahasia, dan data pribadi.
tar -c \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache' \
  --exclude='.git' \
  --exclude='out' \
  --exclude='data/raw' \
  --exclude='*.db' \
  --exclude='.env' \
  --exclude='profile.yml' \
  --exclude='cv.txt' \
  . | tar -x -C "${STAGE}"

cd "${STAGE}"

# Pengaman: pastikan tidak ada rahasia yang ikut terbawa.
for secret in .env profile.yml cv.txt magangku.db; do
  if [[ -e "${secret}" ]]; then
    echo "!! Menghapus berkas sensitif yang lolos: ${secret}"
    rm -rf "${secret}"
  fi
done

git init -q
git add -A
git -c user.email="${GIT_AUTHOR_EMAIL:-you@example.com}" \
    -c user.name="${GIT_AUTHOR_NAME:-MagangKu}" \
    commit -q -m "feat: MagangKu - sistem pencari & pencocok lowongan magang MagangHub

Alur end-to-end: scrape -> normalize -> store -> match -> surat -> apply (assisted).
Termasuk CLI, dashboard web, notifikasi, tracker lamaran, dan 45 tes."

echo "==> Commit awal dibuat."

if command -v gh >/dev/null 2>&1; then
  TARGET="${REPO_NAME}"
  [[ -n "${OWNER}" ]] && TARGET="${OWNER}/${REPO_NAME}"
  echo "==> Membuat repo GitHub (${VISIBILITY#--}): ${TARGET}"
  if gh repo create "${TARGET}" ${VISIBILITY} --source=. --remote=origin --push; then
    echo
    echo "SELESAI. Repo Anda siap:"
    gh repo view "${TARGET}" --json url --jq .url
    exit 0
  fi
  echo "!! gh gagal membuat repo (mungkin nama sudah dipakai atau belum login)."
fi

cat <<EOF

------------------------------------------------------------------
Repo lokal siap di:
  ${STAGE}

Langkah manual berikutnya:
  1) Buat repo PRIVATE baru di https://github.com/new  (nama: ${REPO_NAME})
  2) Jalankan:

     cd "${STAGE}"
     git remote add origin git@github.com:<USERNAME>/${REPO_NAME}.git
     git branch -M main
     git push -u origin main
------------------------------------------------------------------
EOF
