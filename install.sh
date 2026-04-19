#!/bin/bash
set -e
if [ "$EUID" -ne 0 ]; then echo "Execute como root: sudo bash $0"; exit 1; fi

REAL_USER="${SUDO_USER:-highlander}"
REAL_HOME=$(eval echo "~$REAL_USER")

echo "[1/5] Instalando pacotes..."
apt update
apt install -y python3-pip python3-venv python3-tk ffmpeg intel-media-va-driver-non-free vainfo zram-tools

echo "[2/5] Configurando ZRAM..."
cat > /etc/default/zramswap << 'EOF'
ALGO=zstd
SIZE=6144
PRIORITY=100
EOF
systemctl enable zramswap
systemctl restart zramswap

echo "[3/5] Criando ambiente Python..."
cd "$REAL_HOME/clipfusion_v3"
python3 -m venv venv
source venv/bin/activate
pip install faster-whisper opencv-python numpy pillow pyyaml librosa soundfile

echo "[4/5] Permissões..."
chown -R "$REAL_USER":"$REAL_USER" "$REAL_HOME/clipfusion_v3"

echo "[5/5] Concluído! Reinicie: sudo reboot"
