#!/bin/bash
# Instala pacotes necessários em sistemas Debian/Ubuntu.
set -e
if [ "$EUID" -ne 0 ]; then
    echo "Este script deve ser executado como root. Use: sudo bash $0" >&2
    exit 1
fi
echo "[Install] Atualizando apt e instalando dependências..."
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-pip ffmpeg libsqlite3-dev python3-tk python3-gi-common git
echo "[Install] Dependências instaladas com sucesso."
