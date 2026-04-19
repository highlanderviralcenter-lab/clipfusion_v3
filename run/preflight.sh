#!/bin/bash
# Script de verificação de pré‑requisitos para o ClipFusion V3.
set -e
echo "[Preflight] Iniciando verificação de requisitos..."
fail=0
check_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[ERRO] Comando '$cmd' não encontrado." >&2
        fail=1
    else
        echo "[OK]  $cmd encontrado."
    fi
}
check_cmd python3
if command -v ffmpeg >/dev/null 2>&1; then
    echo "[OK]  ffmpeg encontrado."
else
    echo "[AVISO] ffmpeg não encontrado; algumas funcionalidades de vídeo poderão ser limitadas."
fi
# Checa espaço livre (512MB)
avail=$(df --output=avail "$PWD" | tail -n1)
if [ "$avail" -lt 524288 ]; then
    echo "[ERRO] Espaço em disco insuficiente (<500MB)" >&2
    fail=1
else
    echo "[OK]  Espaço em disco suficiente."
fi
# Checa permissão de escrita
if ! touch "$PWD/.clipfusion_preflight_test" 2>/dev/null; then
    echo "[ERRO] Sem permissão de escrita no diretório atual." >&2
    fail=1
else
    rm -f "$PWD/.clipfusion_preflight_test"
fi
if [ "$fail" -ne 0 ]; then
    echo "Preflight falhou. Corrija os erros acima e execute novamente."
    exit 1
fi
echo "Preflight concluído com sucesso."
