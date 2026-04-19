#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

[ "$EUID" -ne 0 ] && echo -e "${RED}Execute como root${NC}" && exit 1

ok()  { echo -e "  ${GREEN}✅${NC} $1"; }
fix() { echo -e "  ${BLUE}🔧${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC} $1"; }

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║        CLIPFUSION SETUP - CORE ONLY (SEM i3wm)                   ║"
echo "╚════════════════════════════════════════════════════════════════════╝"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 1. PACOTES ESSENCIAIS${NC}"

apt-get update -qq
apt-get install -y \
    firmware-misc-nonfree \
    intel-microcode \
    intel-media-va-driver-non-free \
    i965-va-driver-shaders \
    vainfo \
    intel-gpu-tools \
    ffmpeg \
    thermald \
    linux-cpupower \
    msr-tools \
    lm-sensors \
    htop \
    curl wget git \
    zram-tools \
    python3-pip \
    python3-venv

ok "Pacotes essenciais instalados"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 2. GRUPOS DO USUÁRIO${NC}"

getent group render >/dev/null || groupadd render
usermod -aG video,render highlander
ok "highlander nos grupos video e render"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 3. NVIDIA BLOQUEADA${NC}"

cat > /etc/modprobe.d/blacklist-nvidia.conf <<'EOF'
blacklist nouveau
blacklist nvidia
blacklist nvidia_drm
blacklist nvidia_modeset
options nouveau modeset=0
EOF

update-initramfs -u
ok "NVIDIA bloqueada permanentemente"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${blue}▶ 4. GRUB - Kernel params${NC}"

GRUB_LINE='GRUB_CMDLINE_LINUX_DEFAULT="quiet mitigations=off intel_pstate=active i915.enable_guc=3 i915.enable_fbc=1 i915.enable_psr=0 i915.fastboot=1 modprobe.blacklist=nouveau,nvidia,nvidia_drm,nvidia_modeset processor.max_cstate=1 intel_idle.max_cstate=1 nmi_watchdog=0 nowatchdog tsc=reliable clocksource=tsc hpet=disable audit=0"'

if grep -q '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub; then
    sed -i "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|${GRUB_LINE}|" /etc/default/grub
else
    echo "$GRUB_LINE" >> /etc/default/grub
fi

update-grub
ok "GRUB configurado (C-states limitados para overclock estável)"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 5. VA-API${NC}"

cat > /etc/environment <<'EOF'
LIBVA_DRIVER_NAME=iHD
LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
EOF

ok "VA-API iHD configurado"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 6. ZRAM - lz4 para ClipFusion${NC}"

cat > /etc/default/zramswap <<'EOF'
ALGO=lz4
SIZE=6144
PRIORITY=100
EOF

systemctl enable --now zramswap
ok "ZRAM: lz4, 6GB, prioridade 100"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 7. SWAPFILE SSD (rede de segurança)${NC}"

if [ ! -f /swap/swapfile ]; then
    mkdir -p /swap
    chattr +C /swap
    fix "Criando swapfile 2GB..."
    dd if=/dev/zero of=/swap/swapfile bs=1M count=2048 status=progress
    chmod 600 /swap/swapfile
    mkswap /swap/swapfile
fi

swapon -p 50 /swap/swapfile 2>/dev/null || true
grep -q '/swap/swapfile' /etc/fstab || \
    echo '/swap/swapfile none swap sw,pri=50 0 0' >> /etc/fstab

ok "Swapfile 2GB ativo (prioridade 50, abaixo do zRAM)"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 8. SYSCTL - Memória hierárquica${NC}"

cat > /etc/sysctl.d/99-clipfusion.conf <<'EOF'
# === MEMÓRIA HIERÁRQUICA (zRAM + Swap) ===
vm.swappiness=150
vm.vfs_cache_pressure=50
vm.dirty_ratio=30
vm.dirty_background_ratio=10
vm.min_free_kbytes=131072
vm.overcommit_memory=1

# === FILESYSTEM ===
fs.inotify.max_user_watches=1048576
fs.file-max=2097152
EOF

sysctl -p /etc/sysctl.d/99-clipfusion.conf >/dev/null
ok "Sysctl aplicado (swappiness 150, dirty_ratio 30)"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 9. OVERCLOCK + MEDIÇÃO${NC}"

# Script de overclock
cat > /usr/local/bin/oc-set.sh <<'EOF'
#!/bin/bash
# Overclock i5-6200U: PL1=20W, PL2=25W, Turbo=2.7GHz
[ "$EUID" -ne 0 ] && echo "Execute como root" && exit 1

modprobe msr 2>/dev/null || true

# Desbloqueia TDP
wrmsr -a 0x610 0x00dc8004dc8000 2>/dev/null && echo "PL1=20W, PL2=25W ativado"

# Turbo ratio (27x = 2.7GHz em todos cores)
wrmsr -a 0x1ad 0x1B1B1B1B1B1B1B1B 2>/dev/null && echo "Turbo 2.7GHz ativado"

# Desativa limitação térmica artificial
wrmsr -a 0x618 0x0 2>/dev/null && echo "Thermal limit desativado"

echo "Overclock aplicado. Temperatura máxima: 60°C (seu limite)"
EOF
chmod +x /usr/local/bin/oc-set.sh

# Script de medição/monitoramento
cat > /usr/local/bin/oc-mon.sh <<'EOF'
#!/bin/bash
# Monitor de overclock em tempo real

clear
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           CLIPFUSION - MONITOR DE HARDWARE                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Frequências
echo "📊 CPU Frequências:"
grep "MHz" /proc/cpuinfo 2>/dev/null | head -4 | while read line; do
    echo "  $line"
done

# Temperaturas
echo ""
echo "🌡️  Temperaturas:"
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    for zone in /sys/class/thermal/thermal_zone*/temp; do
        name=$(cat ${zone%/*}/type 2>/dev/null || echo "thermal")
        temp=$(cat $zone 2>/dev/null)
        temp_c=$((temp / 1000))
        if [ $temp_c -gt 55 ]; then
            echo "  $name: ${temp_c}°C ⚠️  (próximo do limite 60°C)"
        elif [ $temp_c -gt 45 ]; then
            echo "  $name: ${temp_c}°C 🟡 (aquecendo)"
        else
            echo "  $name: ${temp_c}°C 🟢 (ok)"
        fi
    done
fi

# TDP atual (se disponível)
echo ""
echo "⚡ TDP / Power:"
if [ -f /sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw ]; then
    pl1=$(cat /sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw 2>/dev/null)
    pl1_w=$((pl1 / 1000000))
    echo "  PL1 (sustentado): ${pl1_w}W (target: 20W)"
fi

# GPU
echo ""
echo "🎮 GPU Intel HD 520:"
if command -v intel_gpu_top >/dev/null 2>&1; then
    echo "  intel_gpu_top disponível (rode: sudo intel_gpu_top)"
else
    echo "  Freq: $(cat /sys/kernel/debug/dri/0/i915_frequency_info 2>/dev/null | grep "actual" | head -1 || echo "N/A")"
fi

# Memória
echo ""
echo "💾 Memória:"
free -h | grep -E "Mem|Swap"

# zRAM
echo ""
echo "🗜️  zRAM (lz4):"
if [ -f /sys/block/zram0/mm_stat ]; then
    orig=$(awk '{print $1}' /sys/block/zram0/mm_stat)
    comp=$(awk '{print $2}' /sys/block/zram0/mm_stat)
    orig_mb=$((orig / 1024 / 1024))
    comp_mb=$((comp / 1024 / 1024))
    ratio=$(awk "BEGIN {printf \"%.2f\", $orig/$comp}")
    echo "  Original: ${orig_mb}MB → Comprimido: ${comp_mb}MB (taxa: ${ratio}x)"
fi

echo ""
echo "Pressione Enter para sair..."
read
EOF
chmod +x /usr/local/bin/oc-mon.sh

# Serviço de overclock no boot
cat > /etc/systemd/system/oc-set.service <<'EOF'
[Unit]
Description=Overclock i5-6200U para ClipFusion
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/oc-set.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now oc-set.service 2>/dev/null || warn "Serviço OC criado, ativar após reboot"

ok "Overclock configurado: 20W/25W TDP, 2.7GHz Turbo"
ok "Monitor: sudo oc-mon.sh"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}▶ 10. ALIASES ÚTEIS${NC}"

BASHRC=/home/highlander/.bashrc

add_bashrc() {
    grep -qF "$1" "$BASHRC" 2>/dev/null || echo "$1" >> "$BASHRC"
}

add_bashrc "alias temps='for f in /sys/class/thermal/thermal_zone*/temp; do echo \"\$(cat \${f%/*}/type 2>/dev/null): \$(( \$(cat \$f) / 1000 ))°C\"; done'"
add_bashrc "alias oc='sudo /usr/local/bin/oc-set.sh'"
add_bashrc "alias mon='sudo /usr/local/bin/oc-mon.sh'"
add_bashrc "alias zram='cat /sys/block/zram0/mm_stat | awk \"{print \\\"Original: \\\" int(\\$1/1024/1024)\\\"MB, Comprimido: \\\" int(\\$2/1024/1024)\\\"MB\\\"}\"'"
add_bashrc "export LIBVA_DRIVER_NAME=iHD"

chown highlander:highlander "$BASHRC"
ok "Aliases: temps, oc, mon, zram"

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ SETUP CORE COMPLETO${NC}"
echo ""
echo "  Comandos úteis:"
echo "    sudo oc        → Aplicar overclock manualmente"
echo "    sudo mon       → Monitor completo (temp, freq, zRAM)"
echo "    temps          → Temperaturas rápido"
echo "    zram           → Status de compressão"
echo ""
echo "  Próximo passo: reboot"
echo "════════════════════════════════════════════════════════════════════"
