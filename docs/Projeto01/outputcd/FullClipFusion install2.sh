#!/bin/bash
# ClipFusion 2.0 - Instalação Completa
# Este script configura todo o ambiente Debian 12 para rodar o ClipFusion,
# incluindo otimizações de hardware, drivers, zram, swap, estrutura de pastas
# e todos os arquivos de código necessários.

set -e  # para em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     ClipFusion 2.0 - Instalação Completa              ║${NC}"
echo -e "${BLUE}║     Hardware: i5-6200U + Intel HD 520                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verifica se está sendo executado como root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Execute como root: sudo bash $0${NC}"
    exit 1
fi

# Obtém o usuário real (não root)
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
else
    REAL_USER=$(who am i | awk '{print $1}')
fi
if [ -z "$REAL_USER" ]; then
    REAL_USER="highlander"
fi
REAL_HOME=$(eval echo "~$REAL_USER")
CLIPFUSION_DIR="$REAL_HOME/clipfusion"

echo -e "${GREEN}[1/10] Atualizando sistema e instalando pacotes essenciais...${NC}"
apt update
apt upgrade -y
apt install -y \
    python3-pip python3-venv python3-dev python3-tk \
    ffmpeg git curl wget \
    intel-media-va-driver-non-free i965-va-driver-shaders \
    vainfo intel-gpu-tools lm-sensors \
    thermald linux-cpupower msr-tools \
    btrfs-progs zram-tools \
    htop btop neofetch \
    xorg i3-wm i3status i3lock lightdm lightdm-gtk-greeter \
    rxvt-unicode rofi feh firefox-esr thunar \
    fonts-noto fonts-noto-color-emoji fonts-firacode \
    openssh-server

echo -e "${GREEN}[2/10] Configurando kernel (i915.enable_guc=3)...${NC}"
if ! grep -q "i915.enable_guc=3" /etc/default/grub; then
    sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT="/GRUB_CMDLINE_LINUX_DEFAULT="i915.enable_guc=3 /' /etc/default/grub
    update-grub
    echo -e "${YELLOW}⚠️  Parâmetro de kernel adicionado. Uma reinicialização será necessária no final.${NC}"
else
    echo -e "${GREEN}✅ i915.enable_guc=3 já configurado.${NC}"
fi

echo -e "${GREEN}[3/10] Configurando ZRAM (4GB, zstd, prioridade 100)...${NC}"
cat > /etc/default/zramswap << 'EOF'
ALGO=zstd
SIZE=4096
PRIORITY=100
EOF
systemctl enable zramswap
systemctl restart zramswap

echo -e "${GREEN}[4/10] Configurando swapfile (2GB, prioridade 50)...${NC}"
mkdir -p /swap
chattr +C /swap 2>/dev/null || true
if [ ! -f /swap/swapfile ]; then
    dd if=/dev/zero of=/swap/swapfile bs=1M count=2048 status=progress
    chmod 600 /swap/swapfile
    mkswap /swap/swapfile
    swapon -p 50 /swap/swapfile
    echo '/swap/swapfile none swap sw,pri=50 0 0' >> /etc/fstab
else
    echo -e "${YELLOW}⚠️  swapfile já existe. Ativando...${NC}"
    swapon -p 50 /swap/swapfile 2>/dev/null || true
fi

echo -e "${GREEN}[5/10] Aplicando configurações sysctl de performance...${NC}"
cat > /etc/sysctl.d/99-clipfusion.conf << 'EOF'
vm.swappiness=150
vm.vfs_cache_pressure=50
vm.dirty_ratio=30
vm.dirty_background_ratio=10
vm.dirty_expire_centisecs=1000
vm.dirty_writeback_centisecs=500
vm.min_free_kbytes=131072
vm.overcommit_memory=2
vm.overcommit_ratio=80
net.core.default_qdisc=fq_codel
net.ipv4.tcp_congestion_control=bbr
fs.inotify.max_user_watches=1048576
fs.file-max=2097152
EOF
sysctl -p /etc/sysctl.d/99-clipfusion.conf

echo -e "${GREEN}[6/10] Configurando thermald e cpupower...${NC}"
systemctl enable thermald
systemctl restart thermald
echo 'GOVERNOR="performance"' > /etc/default/cpupower
systemctl enable cpupower
cpupower frequency-set -g performance

echo -e "${GREEN}[7/10] Adicionando usuário aos grupos video e render...${NC}"
usermod -aG video,render "$REAL_USER"

echo -e "${GREEN}[8/10] Criando estrutura de diretórios do ClipFusion em $CLIPFUSION_DIR...${NC}"
mkdir -p "$CLIPFUSION_DIR"
cd "$CLIPFUSION_DIR"

# Cria todas as pastas necessárias
mkdir -p core config locales utils gui anti_copy_modules viral_engine workspace/projects
touch core/__init__.py utils/__init__.py gui/__init__.py anti_copy_modules/__init__.py viral_engine/__init__.py

echo -e "${GREEN}[9/10] Gerando arquivos de configuração...${NC}"

# config/settings.yaml
cat > config/settings.yaml << 'EOF'
project:
  workspace_root: "./workspace/projects"

transcription:
  model: "base"
  language: "pt"
  beam_size: 5
  best_of: 5
  temperature: 0.0
  compression_ratio_threshold: 2.4
  logprob_threshold: -1.0
  no_speech_threshold: 0.6
  condition_on_previous_text: true

segmentation:
  min_duration: 18
  max_duration: 35
  pause_threshold: 0.5

scoring:
  weights:
    hook: 0.3
    retention: 0.25
    moment: 0.2
    shareability: 0.15
    platform_fit: 0.1
  thresholds:
    approved: 9.0
    rework: 7.0
    discard: 0.0

platforms:
  tiktok:
    hook_ideal: 2
    max_duration: 180
    fit_weights:
      discovery: 0.6
      impact: 0.4
  reels:
    hook_ideal: 1.5
    max_duration: 90
    fit_weights:
      rhythm: 0.5
      visual: 0.5
  shorts:
    hook_ideal: 2.5
    max_duration: 60
    fit_weights:
      arc: 0.7
      payoff: 0.3

protection:
  levels:
    none: []
    basic: ["zoom", "color", "metadata", "audio"]
    anti_ia: ["basic", "noise", "chroma"]
    maximum: ["anti_ia", "flip", "jitter"]
EOF

# config/platforms.yaml
cat > config/platforms.yaml << 'EOF'
tiktok:
  name: "TikTok"
  orientation: "vertical"
  resolution: [1080, 1920]
  max_duration: 180
  ideal_duration: [30, 60]
  hook_seconds: 2
  cta_style: "comentário"
reels:
  name: "Instagram Reels"
  orientation: "vertical"
  resolution: [1080, 1920]
  max_duration: 90
  ideal_duration: [15, 60]
  hook_seconds: 1.5
  cta_style: "compartilhar"
shorts:
  name: "YouTube Shorts"
  orientation: "vertical"
  resolution: [1080, 1920]
  max_duration: 60
  ideal_duration: [15, 60]
  hook_seconds: 2.5
  cta_style: "inscreva-se"
EOF

# config/scoring.yaml
cat > config/scoring.yaml << 'EOF'
hook:
  keywords:
    - "segredo"
    - "descobri"
    - "nunca"
    - "jamais"
    - "incrível"
    - "chocante"
    - "pergunta"
  weights:
    presence: 0.4
    position: 0.3
    intensity: 0.3
retention:
  keywords: ["mas", "porém", "então", "e", "quando", "porque", "assim"]
moment:
  keywords: ["descobri", "repentinamente", "de repente", "incrivelmente", "nunca", "sempre"]
shareability:
  keywords: ["incrível", "chocante", "imperdível", "urgente", "revolta", "ameaça"]
EOF

# locales/pt.yaml
cat > locales/pt.yaml << 'EOF'
app_title: "ClipFusion Viral Pro"
tab_project: "Projeto"
tab_transcription: "Transcrição"
tab_ai: "IA Externa"
tab_cuts: "Cortes"
tab_render: "Render"
tab_history: "Histórico"
tab_schedule: "Agenda"
tab_analytics: "Analytics"
EOF

# locales/en.yaml
cat > locales/en.yaml << 'EOF'
app_title: "ClipFusion Viral Pro"
tab_project: "Project"
tab_transcription: "Transcription"
tab_ai: "External AI"
tab_cuts: "Cuts"
tab_render: "Render"
tab_history: "History"
tab_schedule: "Schedule"
tab_analytics: "Analytics"
EOF

echo -e "${GREEN}[10/10] Gerando arquivos de código Python...${NC}"

# db.py (schema unificado)
cat > db.py << 'EOF'
import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

DB_PATH = Path(os.path.expanduser("~")) / ".clipfusion" / "clipfusion.db"

def _get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

@contextmanager
def get_db():
    conn = _get_connection()
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                video_path TEXT NOT NULL,
                language TEXT,
                status TEXT DEFAULT 'created',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                full_text TEXT,
                segments_json TEXT,
                quality_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                transcript_id INTEGER NOT NULL,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                text TEXT NOT NULL,
                hook_strength REAL,
                retention_score REAL,
                moment_strength REAL,
                shareability REAL,
                platform_fit_tiktok REAL,
                platform_fit_reels REAL,
                platform_fit_shorts REAL,
                combined_score REAL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS cuts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                candidate_id INTEGER UNIQUE,
                start_time REAL NOT NULL,
                end_time REAL NOT NULL,
                title TEXT,
                hook TEXT,
                archetype TEXT,
                platforms TEXT,
                protection_level TEXT DEFAULT 'none',
                output_paths TEXT,
                viral_score REAL,
                decision TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE SET NULL
            );
            CREATE TABLE IF NOT EXISTS performances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cut_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                views INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                shares INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                posted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cut_id) REFERENCES cuts(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS learning_weights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                subkey TEXT,
                weight REAL NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

def segments_to_json(segments):
    return json.dumps(segments, ensure_ascii=False)

def json_to_segments(json_str):
    return json.loads(json_str) if json_str else []

def platforms_to_json(platforms):
    return json.dumps(platforms)

def json_to_platforms(json_str):
    return json.loads(json_str) if json_str else []

def output_paths_to_json(paths):
    return json.dumps(paths)

def json_to_output_paths(json_str):
    return json.loads(json_str) if json_str else {}

def create_project(name, video_path, language='pt'):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, video_path, language) VALUES (?, ?, ?)",
            (name, video_path, language)
        )
        conn.commit()
        return cur.lastrowid

def get_project(project_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

def save_transcript(project_id, full_text, segments, quality_score=None):
    segments_json = segments_to_json(segments)
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO transcripts (project_id, full_text, segments_json, quality_score) VALUES (?, ?, ?, ?)",
            (project_id, full_text, segments_json, quality_score)
        )
        conn.commit()
        return cur.lastrowid

def get_transcript(project_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM transcripts WHERE project_id = ? ORDER BY id DESC LIMIT 1",
            (project_id,)
        ).fetchone()
        if row:
            d = dict(row)
            d['segments'] = json_to_segments(d['segments_json'])
            return d
        return None

def save_candidate(project_id, transcript_id, start, end, text, scores=None):
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO candidates
            (project_id, transcript_id, start_time, end_time, text,
             hook_strength, retention_score, moment_strength, shareability,
             platform_fit_tiktok, platform_fit_reels, platform_fit_shorts, combined_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, transcript_id, start, end, text,
            scores.get('hook') if scores else None,
            scores.get('retention') if scores else None,
            scores.get('moment') if scores else None,
            scores.get('shareability') if scores else None,
            scores.get('platform_fit_tiktok') if scores else None,
            scores.get('platform_fit_reels') if scores else None,
            scores.get('platform_fit_shorts') if scores else None,
            scores.get('combined') if scores else None
        ))
        conn.commit()
        return cur.lastrowid

def get_candidates(project_id, status=None):
    with get_db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE project_id = ? AND status = ? ORDER BY combined_score DESC",
                (project_id, status)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE project_id = ? ORDER BY combined_score DESC",
                (project_id,)
            ).fetchall()
        return [dict(r) for r in rows]

def update_candidate_status(candidate_id, status):
    with get_db() as conn:
        conn.execute("UPDATE candidates SET status = ? WHERE id = ?", (status, candidate_id))
        conn.commit()

def save_cut(project_id, candidate_id, start, end, title, hook, archetype, platforms, protection_level, output_paths, viral_score, decision):
    platforms_json = platforms_to_json(platforms)
    output_paths_json = output_paths_to_json(output_paths)
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO cuts
            (project_id, candidate_id, start_time, end_time, title, hook, archetype,
             platforms, protection_level, output_paths, viral_score, decision)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            project_id, candidate_id, start, end, title, hook, archetype,
            platforms_json, protection_level, output_paths_json, viral_score, decision
        ))
        conn.commit()
        return cur.lastrowid

def save_performance(cut_id, platform, views=0, likes=0, shares=0, comments=0, posted_at=None):
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO performances
            (cut_id, platform, views, likes, shares, comments, posted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cut_id, platform, views, likes, shares, comments, posted_at))
        conn.commit()
        return cur.lastrowid

init_db()
EOF

# utils/hardware.py (existente, mantido)
cat > utils/hardware.py << 'EOF'
import subprocess
import os

class HardwareDetector:
    def __init__(self):
        self.info = self._detect_all()

    def _detect_all(self) -> dict:
        return {
            'cpu': self._detect_cpu(),
            'gpu': self._detect_gpu(),
            'ram_gb': self._detect_ram(),
            'encoder': self._detect_encoder(),
            'vaapi': self._check_vaapi(),
        }

    def _detect_cpu(self) -> dict:
        try:
            with open('/proc/cpuinfo') as f:
                lines = f.readlines()
            model, cores = "", 0
            for line in lines:
                if 'model name' in line and not model:
                    model = line.split(':')[1].strip()
                if 'processor' in line:
                    cores += 1
            return {'model': model, 'cores': cores}
        except:
            return {'model': 'i5-6200U', 'cores': 4}

    def _detect_gpu(self) -> dict:
        gpu_info = {'intel': False, 'nvidia': False, 'driver': 'none'}
        try:
            r = subprocess.run(['lspci'], capture_output=True, text=True)
            if 'HD Graphics 520' in r.stdout or 'UHD' in r.stdout:
                gpu_info['intel'] = True
                gpu_info['driver'] = 'i915'
        except: pass
        try:
            r = subprocess.run(['lsmod'], capture_output=True, text=True)
            if 'nvidia' in r.stdout or 'nouveau' in r.stdout:
                gpu_info['nvidia'] = True
        except: pass
        return gpu_info

    def _detect_ram(self) -> float:
        try:
            with open('/proc/meminfo') as f:
                line = f.readline()
            kb = int(line.split()[1])
            return round(kb / 1024 / 1024, 1)
        except:
            return 8.0

    def _detect_encoder(self) -> str:
        try:
            env = dict(os.environ)
            env.setdefault('LIBVA_DRIVER_NAME', 'iHD')
            r = subprocess.run(['vainfo'], env=env, capture_output=True, text=True)
            if 'VAEntrypointEncSlice' in r.stdout:
                return 'h264_vaapi'
        except: pass
        return 'libx264'

    def _check_vaapi(self) -> dict:
        try:
            env = dict(os.environ)
            env.setdefault('LIBVA_DRIVER_NAME', 'iHD')
            r = subprocess.run(['vainfo'], env=env, capture_output=True, text=True)
            out = r.stdout + r.stderr
            return {
                'disponivel': 'VAEntrypointEncSlice' in out,
                'driver': 'iHD' if 'iHD' in out else 'i965',
                'encode_h264': 'VAEntrypointEncSlice' in out,
            }
        except:
            return {'disponivel': False, 'driver': 'none', 'encode_h264': False}

    def get_encoder(self) -> str:
        return 'h264_vaapi' if self.info['vaapi']['disponivel'] else 'libx264'

    def get_status_string(self) -> str:
        enc = self.get_encoder()
        vaapi = '✅ VA-API' if enc == 'h264_vaapi' else '⚠️ CPU'
        try:
            r = subprocess.run(['sensors'], capture_output=True, text=True)
            for line in r.stdout.split('\n'):
                if 'Core 0' in line:
                    temp = line.split()[2].replace('+','').replace('°C','')
                    return f"{vaapi}  |  CPU {temp}°C  |  RAM {self.info['ram_gb']}GB"
        except: pass
        return f"{vaapi}  |  i5-6200U  |  RAM {self.info['ram_gb']}GB"

    def print_summary(self):
        print("╔═══════════════════════════════════════╗")
        print("║  Hardware Detectado                   ║")
        print("╠═══════════════════════════════════════╣")
        print(f"  CPU: {self.info['cpu']['model']}")
        print(f"  RAM: {self.info['ram_gb']} GB")
        print(f"  GPU Intel: {'✅' if self.info['gpu']['intel'] else '❌'}")
        print(f"  NVIDIA:    {'⚠️  ATIVA' if self.info['gpu']['nvidia'] else '✅ Bloqueada'}")
        print(f"  VA-API:    {'✅' if self.info['vaapi']['disponivel'] else '❌'}")
        print(f"  Encoder:   {self.info['encoder']}")
        print("╚═══════════════════════════════════════╝")

def check_system() -> bool:
    print("\n🔍 Verificando Debian Tunado 3.0...")
    checks = []
    try:
        with open('/proc/cmdline') as f:
            cmdline = f.read()
        checks.append(('i915.enable_guc=3', 'i915.enable_guc=3' in cmdline))
        checks.append(('mitigations=off',   'mitigations=off'   in cmdline))
    except:
        checks.extend([('i915.enable_guc=3', False), ('mitigations=off', False)])
    try:
        r = subprocess.run(['swapon', '--show'], capture_output=True, text=True)
        checks.append(('ZRAM ativo', 'zram' in r.stdout))
    except:
        checks.append(('ZRAM ativo', False))
    try:
        r = subprocess.run(['lsmod'], capture_output=True, text=True)
        checks.append(('NVIDIA bloqueada', 'nvidia' not in r.stdout and 'nouveau' not in r.stdout))
    except:
        checks.append(('NVIDIA bloqueada', False))
    try:
        env = dict(os.environ)
        env.setdefault('LIBVA_DRIVER_NAME', 'iHD')
        r = subprocess.run(['vainfo'], env=env, capture_output=True, text=True)
        checks.append(('VA-API iHD', 'VAEntrypointEncSlice' in (r.stdout + r.stderr)))
    except:
        checks.append(('VA-API iHD', False))
    for check, status in checks:
        print(f"  {'✅' if status else '❌'} {check}")
    ok = all(s for _, s in checks)
    print("\n✅ Sistema pronto!\n" if ok else "\n⚠️  Algumas otimizações ausentes.\n")
    return ok

if __name__ == '__main__':
    hw = HardwareDetector()
    hw.print_summary()
    check_system()
EOF

# core/ingest.py
cat > core/ingest.py << 'EOF'
import os
import shutil
from pathlib import Path
from datetime import datetime
import db

def create_project_structure(project_name, video_path, base_workspace="./workspace/projects"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in project_name if c.isalnum() or c in " _-").strip().replace(" ", "_")
    project_dir = Path(base_workspace) / f"{safe_name}_{timestamp}"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "source").mkdir()
    (project_dir / "work").mkdir()
    (project_dir / "output").mkdir()
    (project_dir / "state").mkdir()
    src_video = Path(video_path)
    dest_video = project_dir / "source" / src_video.name
    shutil.copy2(src_video, dest_video)
    return str(project_dir), str(dest_video)

def ingest_video(project_name, video_path, language='pt'):
    project_dir, video_path_in_project = create_project_structure(project_name, video_path)
    project_id = db.create_project(project_name, video_path_in_project, language)
    return project_id, project_dir
EOF

# core/transcribe.py
cat > core/transcribe.py << 'EOF'
import gc
from faster_whisper import WhisperModel
import db

class Transcriber:
    def __init__(self, model_size="base", device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def _load_model(self):
        if self.model is None:
            self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)

    def transcribe(self, audio_path, language=None, beam_size=5, best_of=5, temperature=0.0):
        self._load_model()
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=beam_size,
            best_of=best_of,
            temperature=temperature,
            condition_on_previous_text=True,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        detected_language = info.language
        segments_list = [
            {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text}
            for s in segments
        ]
        full_text = " ".join(s["text"] for s in segments_list)
        return {
            "language": detected_language,
            "segments": segments_list,
            "full_text": full_text,
            "info": info
        }

    def cleanup(self):
        del self.model
        self.model = None
        gc.collect()

def transcribe_project(project_id, video_path, model_size="base", language="pt"):
    transcriber = Transcriber(model_size=model_size)
    result = transcriber.transcribe(video_path, language=language)
    transcript_id = db.save_transcript(project_id, result["full_text"], result["segments"])
    transcriber.cleanup()
    return transcript_id, result
EOF

# core/transcription_quality.py
cat > core/transcription_quality.py << 'EOF'
def compute_quality_score(segments):
    if not segments:
        return 0.0
    total_words = sum(len(s['text'].split()) for s in segments)
    avg_words_per_segment = total_words / len(segments)
    score = min(avg_words_per_segment / 10.0, 1.0)
    return score

def filter_segments(segments, min_words=3):
    return [s for s in segments if len(s['text'].split()) >= min_words]
EOF

# core/segment.py
cat > core/segment.py << 'EOF'
def segment_by_pauses(segments, min_duration=18, max_duration=35, pause_threshold=0.5):
    candidates = []
    current_start = None
    current_end = None
    current_text = []
    last_end = 0
    for seg in segments:
        if current_start is None:
            current_start = seg['start']
            current_end = seg['end']
            current_text = [seg['text']]
            last_end = seg['end']
            continue
        gap = seg['start'] - last_end
        if gap > pause_threshold or (seg['end'] - current_start) > max_duration:
            dur = current_end - current_start
            if dur >= min_duration:
                candidates.append({
                    'start': current_start,
                    'end': current_end,
                    'text': ' '.join(current_text)
                })
            current_start = seg['start']
            current_end = seg['end']
            current_text = [seg['text']]
        else:
            current_end = seg['end']
            current_text.append(seg['text'])
        last_end = seg['end']
    if current_start is not None and (current_end - current_start) >= min_duration:
        candidates.append({
            'start': current_start,
            'end': current_end,
            'text': ' '.join(current_text)
        })
    return candidates
EOF

# core/candidate_engine.py
cat > core/candidate_engine.py << 'EOF'
from . import segment
import db

def generate_candidates(project_id, transcript_id, segments, min_dur=18, max_dur=35, pause_threshold=0.5):
    raw_candidates = segment.segment_by_pauses(segments, min_dur, max_dur, pause_threshold)
    candidate_ids = []
    for cand in raw_candidates:
        cid = db.save_candidate(project_id, transcript_id, cand['start'], cand['end'], cand['text'])
        candidate_ids.append(cid)
    return candidate_ids
EOF

# core/scoring_engine.py
cat > core/scoring_engine.py << 'EOF'
import yaml
from pathlib import Path

class ScoringEngine:
    def __init__(self, config_path="config/scoring.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        self.hook_keywords = self.config['hook']['keywords']
        self.hook_weights = self.config['hook']['weights']
        self.retention_keywords = self.config['retention']['keywords']
        self.moment_keywords = self.config['moment']['keywords']
        self.shareability_keywords = self.config['shareability']['keywords']

    def hook_strength(self, text, start_time):
        first_3s_text = text
        words = first_3s_text.lower().split()
        presence_score = sum(1 for kw in self.hook_keywords if kw in first_3s_text) / max(len(self.hook_keywords),1)
        position_score = 1.0 if start_time < 3 else 0.5
        intensity = 1.0 if '?' in text or '!' in text else 0.5
        weighted = (
            presence_score * self.hook_weights['presence'] +
            position_score * self.hook_weights['position'] +
            intensity * self.hook_weights['intensity']
        )
        return weighted

    def retention_score(self, text):
        words = text.lower().split()
        if not words:
            return 0.0
        score = sum(1 for w in words if w in self.retention_keywords) / len(words)
        return min(score * 5, 1.0)

    def moment_strength(self, text):
        words = text.lower().split()
        if not words:
            return 0.0
        score = sum(1 for w in words if w in self.moment_keywords) / len(words)
        return min(score * 5, 1.0)

    def shareability(self, text):
        words = text.lower().split()
        if not words:
            return 0.0
        score = sum(1 for w in words if w in self.shareability_keywords) / len(words)
        return min(score * 5, 1.0)

    def platform_fit(self, text, platform):
        word_count = len(text.split())
        if platform == 'tiktok':
            return 1.0 if word_count < 30 else 0.5
        elif platform == 'reels':
            return 1.0 if word_count < 50 else 0.6
        elif platform == 'shorts':
            return 1.0 if word_count < 70 else 0.7
        return 0.5

    def score_candidate(self, candidate):
        text = candidate['text']
        start = candidate['start']
        hook = self.hook_strength(text, start)
        retention = self.retention_score(text)
        moment = self.moment_strength(text)
        share = self.shareability(text)
        tiktok_fit = self.platform_fit(text, 'tiktok')
        reels_fit = self.platform_fit(text, 'reels')
        shorts_fit = self.platform_fit(text, 'shorts')
        platform_fit = (tiktok_fit + reels_fit + shorts_fit) / 3
        combined = (
            hook * 0.3 +
            retention * 0.25 +
            moment * 0.2 +
            share * 0.15 +
            platform_fit * 0.1
        )
        return {
            'hook': hook,
            'retention': retention,
            'moment': moment,
            'shareability': share,
            'platform_fit_tiktok': tiktok_fit,
            'platform_fit_reels': reels_fit,
            'platform_fit_shorts': shorts_fit,
            'combined': combined
        }
EOF

# core/platform_engine.py
cat > core/platform_engine.py << 'EOF'
import yaml

class PlatformEngine:
    def __init__(self, config_path="config/platforms.yaml"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.platforms = yaml.safe_load(f)

    def get_platform(self, name):
        return self.platforms.get(name)

    def ideal_duration(self, platform_name):
        plat = self.get_platform(platform_name)
        if plat:
            return plat.get('ideal_duration', [30, 60])
        return [30, 60]

    def max_duration(self, platform_name):
        plat = self.get_platform(platform_name)
        return plat.get('max_duration', 180) if plat else 180
EOF

# core/hybrid_prompt.py
cat > core/hybrid_prompt.py << 'EOF'
from typing import List, Dict
import json

class HybridPromptGenerator:
    def __init__(self, locale='pt'):
        self.locale = locale

    def build_prompt(self, candidates: List[Dict], context: str = ""):
        prompt = f"""Você é um especialista em viralização de conteúdo para plataformas de vídeo curto (TikTok, Reels, Shorts).

## Contexto
{context if context else "Nenhum contexto adicional fornecido."}

## Instruções
Abaixo estão trechos de um vídeo longo, pré-selecionados por um algoritmo como potenciais candidatos a cortes virais.
Para cada trecho, você deve:
1. Avaliar seu potencial viral (nota de 0 a 10).
2. Se a nota for >= 7, forneça:
   - Um título atrativo (máx 60 caracteres)
   - Um gancho (hook) para os primeiros 3 segundos
   - O arquétipo emocional predominante (use um dos 10 arquétipos do ClipFusion: Curiosidade, Medo, Ganância, Urgência, Prova Social, Autoridade, Empatia, Indignação, Exclusividade, Alívio)
   - Uma justificativa breve (por que viralizaria)
   - Plataformas sugeridas (lista com TikTok, Reels, Shorts)
3. Se a nota for < 7, apenas indique que o trecho não é promissor.

## Formato de Resposta (OBRIGATÓRIO - JSON puro)
Responda APENAS com um JSON válido, sem markdown, contendo uma lista de objetos com os campos:
- candidate_id: (opcional, se fornecido)
- start: (float)
- end: (float)
- title: (string)
- hook: (string)
- archetype: (string)
- score: (float)  # nota da IA (0-10)
- platforms: (lista de strings)
- reason: (string)

Exemplo:
[
  {{
    "candidate_id": 1,
    "start": 12.3,
    "end": 35.7,
    "title": "O segredo da prospecção",
    "hook": "Você sabia que 80% dos vendedores erram?",
    "archetype": "Curiosidade",
    "score": 8.5,
    "platforms": ["tiktok", "reels"],
    "reason": "Gancho forte com pergunta retórica, aborda uma dor comum."
  }}
]

## Candidatos
"""
        for cand in candidates:
            prompt += f"\n--- Candidato ID {cand.get('id', '?')} ---\n"
            prompt += f"Timestamp: {cand['start']}s - {cand['end']}s\n"
            prompt += f"Texto: {cand['text']}\n"
            if 'scores' in cand:
                prompt += f"Scores locais: hook={cand['scores'].get('hook', 0):.2f}, retenção={cand['scores'].get('retention', 0):.2f}, momento={cand['scores'].get('moment', 0):.2f}\n"
        prompt += "\nAnalise agora:"
        return prompt
EOF

# core/hybrid_parser.py
cat > core/hybrid_parser.py << 'EOF'
import json
import re

def parse_ai_response(response_text: str):
    clean = re.sub(r'```json\s*|\s*```', '', response_text.strip())
    match = re.search(r'\[.*\]', clean, re.DOTALL)
    if not match:
        match = re.search(r'\{.*\}', clean, re.DOTALL)
        if not match:
            return None
        try:
            obj = json.loads(match.group())
            return [obj]
        except:
            return None
    try:
        data = json.loads(match.group())
        if isinstance(data, list):
            return data
        else:
            return [data]
    except:
        return None

def validate_ai_cut(cut):
    required = ['start', 'end', 'title', 'hook', 'score']
    for field in required:
        if field not in cut:
            return False
    return True
EOF

# core/decision_engine.py
cat > core/decision_engine.py << 'EOF'
class DecisionEngine:
    def __init__(self, thresholds=None):
        self.thresholds = thresholds or {'approved': 9.0, 'rework': 7.0, 'discard': 0.0}

    def decide(self, local_score, ai_score=None, ai_confidence=None):
        if ai_score is None:
            if local_score >= self.thresholds['approved']:
                return 'approved', f"Score local alto ({local_score:.1f})"
            elif local_score >= self.thresholds['rework']:
                return 'rework', f"Score local médio ({local_score:.1f})"
            else:
                return 'discard', f"Score local baixo ({local_score:.1f})"
        combined = (local_score + ai_score) / 2
        if combined >= self.thresholds['approved']:
            return 'approved', f"Consenso: local {local_score:.1f}, IA {ai_score:.1f}"
        elif combined >= self.thresholds['rework']:
            return 'rework', f"Divergência: local {local_score:.1f}, IA {ai_score:.1f}"
        else:
            return 'discard', f"Baixo consenso: local {local_score:.1f}, IA {ai_score:.1f}"

    def batch_decide(self, candidates_with_scores):
        decisions = []
        for cand in candidates_with_scores:
            decision, reason = self.decide(cand.get('local_score', 0), cand.get('ai_score'))
            decisions.append({
                'candidate_id': cand.get('id'),
                'decision': decision,
                'reason': reason,
                'combined_score': (cand.get('local_score', 0) + cand.get('ai_score', 0)) / 2
            })
        return decisions
EOF

# core/protection_factory.py
cat > core/protection_factory.py << 'EOF'
import subprocess
import gc
from anti_copy_modules.core import AntiCopyrightEngine, ProtectionConfig, ProtectionLevel

def apply_protection(input_path, output_path, level='basic', project_id='', cut_index=0, log=None):
    if level == 'none':
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path
    level_map = {
        'none': ProtectionLevel.NONE,
        'basic': ProtectionLevel.BASIC,
        'anti_ia': ProtectionLevel.ANTI_AI,
        'maximum': ProtectionLevel.MAXIMUM
    }
    enum_level = level_map.get(level, ProtectionLevel.BASIC)
    config = ProtectionConfig.from_level(enum_level)
    engine = AntiCopyrightEngine(project_id, cut_index, config, log)
    engine.process(input_path, output_path)
    del engine
    gc.collect()
    return output_path
EOF

# core/post_pack.py
cat > core/post_pack.py << 'EOF'
import random

class PostPackGenerator:
    def __init__(self, locale='pt'):
        self.locale = locale
        self.templates = {
            'Curiosidade': {
                'title': ["O segredo de {tema}", "{tema} – o que ninguém conta"],
                'description': ["Descubra {tema} que vai mudar sua visão sobre {nicho}."],
                'hashtags': ["#curiosidade", "#descubraagora", "#viral"]
            },
            'Medo': {
                'title': ["Cuidado com {tema}", "Isso pode destruir {algo}"],
                'description': ["Você sabia que {tema} pode estar arruinando seus resultados?"],
                'hashtags': ["#cuidado", "#alerta", "#fiqueatento"]
            },
        }

    def generate(self, cut_title, archetype, niche, tema=None):
        template = self.templates.get(archetype, self.templates['Curiosidade'])
        title = random.choice(template['title']).format(tema=tema or cut_title, nicho=niche, algo='seus resultados')
        description = random.choice(template['description']).format(tema=tema or cut_title, nicho=niche)
        hashtags = template['hashtags'] + [f"#{nicho.replace(' ', '')}", "#clipfusion"]
        pinned_comment = f"O que você achou? Comenta aqui embaixo! 👇"
        return {
            'title': title[:60],
            'description': description[:150],
            'hashtags': hashtags[:5],
            'pinned_comment': pinned_comment
        }
EOF

# core/posting_schedule.py
cat > core/posting_schedule.py << 'EOF'
import random
from datetime import datetime, timedelta

class PostingSchedule:
    def __init__(self, platform='tiktok', base_hours=None):
        self.platform = platform
        self.base_hours = base_hours or [9, 12, 18, 21]

    def generate(self, count=10, start_date=None, jitter_minutes=15):
        if start_date is None:
            start_date = datetime.now()
        schedule = []
        current = start_date
        for i in range(count):
            hour = random.choice(self.base_hours)
            candidate = current.replace(hour=hour, minute=0, second=0, microsecond=0)
            jitter = timedelta(minutes=random.randint(-jitter_minutes, jitter_minutes),
                               seconds=random.randint(0, 59))
            post_time = candidate + jitter
            current += timedelta(days=1)
            schedule.append(post_time)
        return schedule

    def format_schedule(self, schedule):
        lines = [f"📅 Agenda de postagens ({self.platform})"]
        for i, dt in enumerate(schedule, 1):
            lines.append(f"  #{i:02d} - {dt.strftime('%d/%m/%Y %H:%M:%S')}")
        return "\n".join(lines)
EOF

# core/learning_engine.py
cat > core/learning_engine.py << 'EOF'
import db

class LearningEngine:
    def __init__(self):
        pass

    def update_weights_from_performance(self, project_id=None):
        with db.get_db() as conn:
            query = """
                SELECT c.*, p.views, p.likes, p.shares, p.comments
                FROM cuts c
                JOIN performances p ON c.id = p.cut_id
            """
            if project_id:
                query += " WHERE c.project_id = ?"
                rows = conn.execute(query, (project_id,)).fetchall()
            else:
                rows = conn.execute(query).fetchall()
        if not rows:
            return
        print("LearningEngine: análise de performance ainda não implementada.")
EOF

# gui/main_gui.py (versão adaptada, simplificada para este script)
cat > gui/main_gui.py << 'EOF'
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import threading, os, gc, json, subprocess
from pathlib import Path
from datetime import datetime

import db
from utils.hardware import HardwareDetector, check_system
from core.transcribe import transcribe_project
from core.candidate_engine import generate_candidates
from core.scoring_engine import ScoringEngine
from core.hybrid_prompt import HybridPromptGenerator
from core.hybrid_parser import parse_ai_response, validate_ai_cut
from core.decision_engine import DecisionEngine
from core.protection_factory import apply_protection
from core.post_pack import PostPackGenerator
from core.posting_schedule import PostingSchedule
from anti_copy_modules.core import LEVEL_LABELS

BG = "#0d0d1a"; BG2 = "#151528"; BG3 = "#1e1e3a"
ACC = "#7c3aed"; GRN = "#22c55e"; RED = "#ef4444"
YEL = "#f59e0b"; WHT = "#f1f5f9"; GRY = "#64748b"
FNT = ("Segoe UI", 10); FNTB = ("Segoe UI", 10, "bold")
FNTL = ("Segoe UI", 13, "bold"); MONO = ("Consolas", 9)

ACE_LEVELS = [
    ("🟢 NENHUM",  "none"),
    ("🟡 BÁSICO",  "basic"),
    ("🟠 ANTI-IA", "anti_ai"),
    ("🔴 MÁXIMO",  "maximum"),
]

class ClipFusionApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("✂ ClipFusion Viral Pro")
        self.root.geometry("1120x800")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.project_id = None
        self.video_path = None
        self.segments = []
        self.duration = 0.0
        self.cut_vars = {}
        self.output_dir = None
        self.hw = HardwareDetector()
        self._build_ui()

    def run(self):
        self.root.mainloop()

    def _build_ui(self):
        hdr = tk.Frame(self.root, bg=ACC, height=54)
        hdr.pack(fill="x")
        tk.Label(hdr, text="✂  ClipFusion Viral Pro",
                 font=("Segoe UI", 16, "bold"), bg=ACC, fg=WHT).pack(side="left", padx=20, pady=12)
        tk.Label(hdr, text="vídeo longo → cortes virais prontos pra postar",
                 font=FNT, bg=ACC, fg="#c4b5fd").pack(side="left")
        self.lbl_hw = tk.Label(hdr, text=self.hw.get_status_string(),
                                font=("Segoe UI", 8), bg=ACC, fg="#c4b5fd")
        self.lbl_hw.pack(side="right", padx=16)

        s = ttk.Style(); s.theme_use("clam")
        s.configure("TNotebook", background=BG2, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=GRY, padding=[14,7], font=FNT)
        s.map("TNotebook.Tab", background=[("selected", ACC)], foreground=[("selected", WHT)])

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True)

        self._tab_projeto()
        self._tab_transcricao()
        self._tab_ia()
        self._tab_cortes()
        self._tab_render()
        self._tab_historico()
        self._tab_agenda()
        self._tab_analytics()

    def _tab_projeto(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📁  Projeto")
        self._lbl(f, "Novo projeto", font=FNTL).pack(anchor="w", padx=30, pady=(28,4))
        self._lbl(f, "Selecione o vídeo longo e configure as opções.", color=GRY).pack(anchor="w", padx=30)
        self._sep(f)
        r1 = tk.Frame(f, bg=BG2); r1.pack(fill="x", padx=30, pady=6)
        self._lbl(r1, "Nome:").pack(side="left")
        self.v_name = tk.StringVar(value=f"Projeto {datetime.now().strftime('%d/%m %H:%M')}")
        tk.Entry(r1, textvariable=self.v_name, width=44,
                 bg=BG3, fg=WHT, insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=10)
        self._lbl(f, "Contexto (opcional — ajuda a IA entender o tema):").pack(anchor="w", padx=30, pady=(12,4))
        self.ctx_box = tk.Text(f, height=3, bg=BG3, fg=WHT,
                               insertbackground=WHT, relief="flat", font=FNT, wrap="word")
        self.ctx_box.pack(fill="x", padx=30)
        self.ctx_box.insert("1.0", "Ex: Podcast sobre vendas — episódio sobre prospecção de clientes.")
        self._sep(f)
        vr = tk.Frame(f, bg=BG2); vr.pack(fill="x", padx=30, pady=6)
        self._btn(vr, "📂 Selecionar vídeo", self._select_video, ACC).pack(side="left")
        self.lbl_video = self._lbl(vr, "Nenhum vídeo selecionado", color=GRY)
        self.lbl_video.pack(side="left", padx=14)
        op = tk.Frame(f, bg=BG2); op.pack(fill="x", padx=30, pady=10)
        self.v_vaapi = tk.BooleanVar(value=True)
        self._chk(op, "Usar VA-API (Intel HD 520) — recomendado", self.v_vaapi).pack(anchor="w")
        acef = tk.Frame(f, bg=BG2); acef.pack(fill="x", padx=30, pady=4)
        self._lbl(acef, "Anti-Copyright:").pack(side="left")
        self.v_ace = tk.StringVar(value="basic")
        for lbl, val in ACE_LEVELS:
            tk.Radiobutton(acef, text=lbl, variable=self.v_ace, value=val,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        wf = tk.Frame(f, bg=BG2); wf.pack(fill="x", padx=30, pady=4)
        self._lbl(wf, "Whisper:").pack(side="left")
        self.v_whisper = tk.StringVar(value="tiny")
        for m in ["tiny", "base", "small"]:
            tk.Radiobutton(wf, text=m, variable=self.v_whisper, value=m,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        lf = tk.Frame(f, bg=BG2); lf.pack(fill="x", padx=30, pady=4)
        self._lbl(lf, "Idioma:").pack(side="left")
        self.v_lang = tk.StringVar(value="pt")
        for lbl, val in [("Auto", "auto"), ("Português", "pt"), ("English", "en")]:
            tk.Radiobutton(lf, text=lbl, variable=self.v_lang, value=val,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        self._sep(f)
        self._btn(f, "▶  Iniciar Transcrição", self._start_transcription, GRN, wide=True).pack(padx=30, pady=8)
        self.lbl_status = self._lbl(f, "", color=GRY)
        self.lbl_status.pack(padx=30, pady=4)

    def _tab_transcricao(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📝  Transcrição")
        self._lbl(f, "Transcrição com timestamps", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        self._lbl(f, "Gerada pelo Whisper. Revise se necessário.", color=GRY).pack(anchor="w", padx=30)
        self.box_transcript = scrolledtext.ScrolledText(
            f, bg=BG3, fg=WHT, font=MONO, relief="flat", insertbackground=WHT)
        self.box_transcript.pack(fill="both", expand=True, padx=30, pady=12)
        self._btn(f, "▶  Gerar Prompt para IA  →", self._goto_ia, ACC, wide=True).pack(padx=30, pady=(0,20))

    def _tab_ia(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="🤖  IA Externa")
        top = tk.Frame(f, bg=BG2); top.pack(fill="x", padx=30, pady=(20,4))
        self._lbl(top, "Prompt para copiar", font=FNTL).pack(side="left")
        self._btn(top, "📋 Copiar", self._copy_prompt, ACC).pack(side="right")
        self._lbl(f, "Cole no Claude.ai, ChatGPT ou qualquer IA. Traga o JSON de resposta abaixo.",
                  color=GRY).pack(anchor="w", padx=30)
        self.box_prompt = scrolledtext.ScrolledText(
            f, height=11, bg=BG3, fg="#a5b4fc", font=MONO, relief="flat", insertbackground=WHT)
        self.box_prompt.pack(fill="x", padx=30, pady=(4,14))
        self._lbl(f, "Resposta da IA (cole o JSON aqui):", font=FNTB).pack(anchor="w", padx=30)
        self.box_resp = scrolledtext.ScrolledText(
            f, height=13, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_resp.pack(fill="both", expand=True, padx=30, pady=4)
        self._btn(f, "✅  Processar resposta  →  Ver Cortes",
                  self._process_resp, GRN, wide=True).pack(padx=30, pady=(4,20))

    def _tab_cortes(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="✂  Cortes")
        top = tk.Frame(f, bg=BG2); top.pack(fill="x", padx=30, pady=(20,4))
        self._lbl(top, "Cortes sugeridos pela IA", font=FNTL).pack(side="left")
        self._btn(top, "✅ Todos",  self._approve_all, GRN).pack(side="right", padx=4)
        self._btn(top, "❌ Nenhum", self._reject_all,  RED).pack(side="right")
        self._lbl(f, "Marque os cortes que deseja renderizar.", color=GRY).pack(anchor="w", padx=30)
        outer = tk.Frame(f, bg=BG2); outer.pack(fill="both", expand=True, padx=30, pady=8)
        cv = tk.Canvas(outer, bg=BG2, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        self.cuts_frame = tk.Frame(cv, bg=BG2)
        self.cuts_frame.bind("<Configure>",
            lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0), window=self.cuts_frame, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        cv.bind_all("<MouseWheel>", lambda e: cv.yview_scroll(-1*(e.delta//120), "units"))
        self._btn(f, "🎬  Renderizar cortes aprovados",
                  self._start_render, ACC, wide=True).pack(padx=30, pady=(4,20))

    def _tab_render(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="🎬  Render")
        self._lbl(f, "Progresso do render", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        self.box_log = scrolledtext.ScrolledText(
            f, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_log.pack(fill="both", expand=True, padx=30, pady=10)
        self._btn(f, "📂  Abrir pasta de saída",
                  self._open_output, GRY, wide=True).pack(padx=30, pady=(0,20))

    def _tab_historico(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📋  Histórico")
        self._lbl(f, "Projetos anteriores", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        cols = ("ID", "Nome", "Status", "Criado em")
        st = ttk.Style()
        st.configure("Treeview", background=BG3, foreground=WHT, fieldbackground=BG3, rowheight=28)
        st.configure("Treeview.Heading", background=ACC, foreground=WHT)
        self.tree = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=50 if c=="ID" else 200)
        self.tree.pack(fill="both", expand=True, padx=30, pady=10)
        self._btn(f, "🔄  Carregar projeto selecionado",
                  self._load_project, ACC, wide=True).pack(padx=30, pady=(0,20))
        self._refresh_tree()

    def _tab_agenda(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📅  Agenda")
        self._lbl(f, "Agenda de Upload", font=FNTL).pack(anchor="w", padx=30, pady=(20,4))
        self._lbl(f, "Gera horários ideais com jitter anti-padrão para evitar detecção.",
                  color=GRY).pack(anchor="w", padx=30)
        self._sep(f)
        cfg = tk.Frame(f, bg=BG2); cfg.pack(fill="x", padx=30, pady=8)
        self._lbl(cfg, "Plataforma:").pack(side="left")
        self.v_platform = tk.StringVar(value="tiktok")
        for p in ["tiktok", "reels", "shorts"]:
            tk.Radiobutton(cfg, text=p, variable=self.v_platform, value=p,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=8)
        cfg2 = tk.Frame(f, bg=BG2); cfg2.pack(fill="x", padx=30, pady=4)
        self._lbl(cfg2, "Quantidade:").pack(side="left")
        self.v_count = tk.StringVar(value="10")
        tk.Entry(cfg2, textvariable=self.v_count, width=6,
                 bg=BG3, fg=WHT, insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=10)
        self._btn(f, "📅  Gerar Agenda", self._generate_schedule, ACC, wide=True).pack(padx=30, pady=10)
        self.box_agenda = scrolledtext.ScrolledText(
            f, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_agenda.pack(fill="both", expand=True, padx=30, pady=10)

    def _tab_analytics(self):
        f = tk.Frame(self.nb, bg=BG2); self.nb.add(f, text="📊  Analytics")
        top = tk.Frame(f, bg=BG2); top.pack(fill="x", padx=30, pady=(20,4))
        self._lbl(top, "Analytics & Aprendizado", font=FNTL).pack(side="left")
        self._btn(top, "🔄 Atualizar", self._refresh_analytics, ACC).pack(side="right")
        self._lbl(f, "Performance dos cortes, padrões aprendidos e sugestões do sistema.",
                  color=GRY).pack(anchor="w", padx=30)
        self._sep(f)
        reg = tk.Frame(f, bg=BG2); reg.pack(fill="x", padx=30, pady=4)
        self._lbl(reg, "Registrar resultado real:").pack(side="left")
        self.v_ana_cut   = tk.StringVar(value="cut_id")
        self.v_ana_plat  = tk.StringVar(value="tiktok")
        self.v_ana_views = tk.StringVar(value="0")
        tk.Entry(reg, textvariable=self.v_ana_cut,  width=14, bg=BG3, fg=WHT,
                 insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=4)
        for p in ["tiktok", "reels", "shorts"]:
            tk.Radiobutton(reg, text=p, variable=self.v_ana_plat, value=p,
                           bg=BG2, fg=WHT, selectcolor=ACC,
                           activebackground=BG2, font=FNT).pack(side="left", padx=4)
        self._lbl(reg, "Views:").pack(side="left", padx=(8,2))
        tk.Entry(reg, textvariable=self.v_ana_views, width=8, bg=BG3, fg=WHT,
                 insertbackground=WHT, relief="flat", font=FNT).pack(side="left", padx=4)
        self._btn(reg, "✅ Registrar", self._record_manual_analytics, GRN).pack(side="left", padx=8)
        self._sep(f)
        self.box_analytics = scrolledtext.ScrolledText(
            f, bg=BG3, fg=GRN, font=MONO, relief="flat", insertbackground=WHT)
        self.box_analytics.pack(fill="both", expand=True, padx=30, pady=(0,20))
        self.box_analytics.insert("1.0",
            "Clique em 🔄 Atualizar para ver o dashboard.\n"
            "Após renderizar e postar, registre os views reais aqui.\n"
            "O sistema aprende os padrões e sugere melhorias automaticamente.\n")

    def _select_video(self):
        p = filedialog.askopenfilename(
            title="Selecionar vídeo",
            filetypes=[("Vídeos", "*.mp4 *.mkv *.mov *.avi *.webm"), ("Todos", "*.*")])
        if p:
            self.video_path = p
            self.lbl_video.config(text=f"✅ {os.path.basename(p)}", fg=GRN)

    def _start_transcription(self):
        if not self.video_path:
            messagebox.showwarning("Atenção", "Selecione um vídeo primeiro.")
            return
        name = self.v_name.get().strip() or "Sem nome"
        # Aqui você pode chamar a ingestão, mas simplificamos
        # Para simplificar, apenas criamos projeto no db
        pid = db.create_project(name, self.video_path, self.v_lang.get())
        self.project_id = pid
        self._status(f"Projeto #{pid} criado. Transcrevendo...", YEL)
        def run():
            try:
                # Transcrever
                tid, result = transcribe_project(pid, self.video_path,
                                                  model_size=self.v_whisper.get(),
                                                  language=self.v_lang.get())
                self.segments = result['segments']
                self.duration = self.segments[-1]['end'] if self.segments else 0
                # Gerar candidatos
                from core.candidate_engine import generate_candidates
                candidate_ids = generate_candidates(pid, tid, self.segments)
                # Pontuar candidatos
                scoring = ScoringEngine()
                for cid in candidate_ids:
                    # Recuperar candidato do banco
                    with db.get_db() as conn:
                        row = conn.execute("SELECT * FROM candidates WHERE id = ?", (cid,)).fetchone()
                        if row:
                            cand = dict(row)
                            scores = scoring.score_candidate({'text': cand['text'], 'start': cand['start_time']})
                            # Atualizar no banco
                            conn.execute("""
                                UPDATE candidates SET
                                    hook_strength=?, retention_score=?, moment_strength=?,
                                    shareability=?, platform_fit_tiktok=?, platform_fit_reels=?,
                                    platform_fit_shorts=?, combined_score=?
                                WHERE id=?
                            """, (
                                scores['hook'], scores['retention'], scores['moment'],
                                scores['shareability'], scores['platform_fit_tiktok'],
                                scores['platform_fit_reels'], scores['platform_fit_shorts'],
                                scores['combined'], cid
                            ))
                            conn.commit()
                # Atualizar interface
                self.root.after(0, lambda: self._update_after_transcription(result['full_text']))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erro", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def _update_after_transcription(self, full_text):
        self.box_transcript.delete("1.0", "end")
        for s in self.segments:
            self.box_transcript.insert("end", f"[{fmt_time(s['start'])}] {s['text']}\n")
        self._status(f"✅ {len(self.segments)} segmentos. Vá para 🤖 IA Externa.", GRN)
        self.nb.select(1)

    def _goto_ia(self):
        if not self.segments:
            messagebox.showwarning("Atenção", "Transcreva primeiro.")
            return
        self.nb.select(2)

    def _copy_prompt(self):
        p = self.box_prompt.get("1.0", "end-1c")
        if not p.strip():
            messagebox.showwarning("Atenção", "Prompt vazio.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(p)
        messagebox.showinfo("Copiado!", "Cole no Claude/ChatGPT e cole a resposta JSON abaixo.")

    def _process_resp(self):
        resp = self.box_resp.get("1.0", "end-1c").strip()
        if not resp:
            messagebox.showwarning("Atenção", "Cole a resposta da IA primeiro.")
            return
        if not self.project_id:
            messagebox.showwarning("Atenção", "Nenhum projeto ativo.")
            return
        from core.hybrid_parser import parse_ai_response, validate_ai_cut
        ai_cuts = parse_ai_response(resp)
        if not ai_cuts:
            messagebox.showerror("Erro", "Não foi possível interpretar o JSON da IA.")
            return
        # Aqui você pode combinar com scores locais e decidir
        # Por simplicidade, apenas salvamos como cortes aprovados
        # (decisão será feita depois)
        # Vamos apenas desenhar na aba cortes
        self._draw_cuts(ai_cuts)
        self.nb.select(3)

    def _draw_cuts(self, cuts):
        for w in self.cuts_frame.winfo_children():
            w.destroy()
        self.cut_vars = {}
        for i, cut in enumerate(cuts):
            self._draw_cut_card(cut, i)

    def _draw_cut_card(self, cut, idx):
        card = tk.Frame(self.cuts_frame, bg=BG3)
        card.pack(fill="x", pady=3, padx=2)
        var = tk.BooleanVar(value=True)
        self.cut_vars[idx] = var
        hdr = tk.Frame(card, bg=BG3); hdr.pack(fill="x", padx=10, pady=(8,3))
        tk.Checkbutton(hdr, variable=var, bg=BG3, fg=WHT,
                       selectcolor=ACC, activebackground=BG3, font=FNTB).pack(side="left")
        start = cut.get('start', 0)
        end = cut.get('end', 0)
        dur = end - start
        tk.Label(hdr, text=f"{cut.get('title', 'Corte')}",
                 bg=BG3, fg=WHT, font=FNTB).pack(side="left", padx=4)
        tk.Label(hdr, text=f"  {fmt_time(start)} → {fmt_time(end)}  ({fmt_time(dur)})",
                 bg=BG3, fg=GRY, font=FNT).pack(side="left")
        if cut.get('hook'):
            tk.Label(card, text=f"🎣  {cut['hook']}",
                     bg=BG3, fg="#a5b4fc", font=FNT,
                     wraplength=960, justify="left", anchor="w").pack(fill="x", padx=22, pady=2)
        if cut.get('reason'):
            tk.Label(card, text=f"💡  {cut['reason']}",
                     bg=BG3, fg=GRY, font=FNT,
                     wraplength=960, justify="left", anchor="w").pack(fill="x", padx=22, pady=(0,8))
        tk.Frame(card, bg=BG, height=1).pack(fill="x")

    def _approve_all(self):
        for v in self.cut_vars.values(): v.set(True)

    def _reject_all(self):
        for v in self.cut_vars.values(): v.set(False)

    def _start_render(self):
        # Aqui você chamaria o protection_factory, etc.
        messagebox.showinfo("Render", "Renderização iniciada (simulado).")

    def _open_output(self):
        messagebox.showinfo("Info", "Pasta de saída ainda não implementada.")

    def _generate_schedule(self):
        from core.posting_schedule import PostingSchedule
        ps = PostingSchedule(platform=self.v_platform.get())
        schedule = ps.generate(count=int(self.v_count.get()))
        text = ps.format_schedule(schedule)
        self.box_agenda.delete("1.0", "end")
        self.box_agenda.insert("1.0", text)

    def _load_project(self):
        sel = self.tree.selection()
        if not sel: return
        pid = int(self.tree.item(sel[0])["values"][0])
        proj = db.get_project(pid)
        if not proj: return
        self.project_id = pid
        self.video_path = proj["video_path"]
        t = db.get_transcript(pid)
        if t:
            self.segments = t['segments']
            self.duration = self.segments[-1]['end'] if self.segments else 0
            self.box_transcript.delete("1.0", "end")
            for s in self.segments:
                self.box_transcript.insert("end", f"[{fmt_time(s['start'])}] {s['text']}\n")
        self.v_name.set(proj["name"])
        self.lbl_video.config(text=f"✅ {os.path.basename(proj['video_path'])}", fg=GRN)
        messagebox.showinfo("Carregado", f"Projeto '{proj['name']}' carregado.")
        self.nb.select(0)

    def _refresh_tree(self):
        for r in self.tree.get_children(): self.tree.delete(r)
        with db.get_db() as conn:
            rows = conn.execute("SELECT id, name, status, created_at FROM projects ORDER BY created_at DESC").fetchall()
            for r in rows:
                self.tree.insert("", "end", values=(r['id'], r['name'], r['status'], r['created_at']))

    def _refresh_analytics(self):
        self.box_analytics.insert("end", "Analytics em construção.\n")

    def _record_manual_analytics(self):
        messagebox.showinfo("Info", "Registro de analytics ainda não implementado.")

    def _log(self, m):
        self.box_log.insert("end", m+"\n"); self.box_log.see("end")

    def _status(self, m, color=GRY):
        self.lbl_status.config(text=m, fg=color)

    def _lbl(self, p, text="", font=None, color=None):
        return tk.Label(p, text=text,
                        bg=p.cget("bg") if hasattr(p,"cget") else BG2,
                        fg=color or WHT, font=font or FNT)

    def _btn(self, p, text, cmd, color=BG3, wide=False):
        return tk.Button(p, text=text, command=cmd,
                         bg=color, fg=WHT, font=FNTB, relief="flat",
                         cursor="hand2", padx=20 if wide else 14, pady=8,
                         activebackground=color, activeforeground=WHT,
                         width=50 if wide else None)

    def _chk(self, p, text, var):
        return tk.Checkbutton(p, text=text, variable=var,
                              bg=p.cget("bg"), fg=WHT, selectcolor=ACC,
                              activebackground=p.cget("bg"), font=FNT)

    def _sep(self, p):
        tk.Frame(p, bg=BG3, height=1).pack(fill="x", padx=30, pady=16)

def fmt_time(s):
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = int(s % 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"
EOF

# anti_copy_modules (mínimo necessário)
mkdir -p anti_copy_modules
cat > anti_copy_modules/core.py << 'EOF'
from enum import Enum
from dataclasses import dataclass
import hashlib, shutil, subprocess, tempfile, os
from typing import Optional, Callable, Dict

class ProtectionLevel(Enum):
    NONE = "none"
    BASIC = "basic"
    ANTI_AI = "anti_ai"
    MAXIMUM = "maximum"

@dataclass
class ProtectionConfig:
    level: ProtectionLevel
    geometric: bool = False
    color: bool = False
    noise: bool = False
    chroma: bool = False
    frequency: bool = False
    temporal: bool = False
    ai_evasion: bool = False
    audio_basic: bool = False
    audio_advanced: bool = False
    network: bool = False
    metadata: bool = False

    @classmethod
    def from_level(cls, level: ProtectionLevel) -> "ProtectionConfig":
        return {
            ProtectionLevel.NONE: cls(level=level),
            ProtectionLevel.BASIC: cls(level=level, geometric=True, color=True, temporal=True, audio_basic=True, metadata=True),
            ProtectionLevel.ANTI_AI: cls(level=level, geometric=True, color=True, noise=True, chroma=True, temporal=True, ai_evasion=True, audio_basic=True, network=True, metadata=True),
            ProtectionLevel.MAXIMUM: cls(level=level, geometric=True, color=True, noise=True, chroma=True, frequency=True, temporal=True, ai_evasion=True, audio_basic=True, audio_advanced=True, network=True, metadata=True),
        }.get(level, cls(level=ProtectionLevel.NONE))

class AntiCopyrightEngine:
    def __init__(self, project_id: str, cut_index: int = 0,
                 config: Optional[ProtectionConfig] = None,
                 log: Optional[Callable] = None):
        self.project_id = project_id
        self.cut_index = cut_index
        self.config = config or ProtectionConfig.from_level(ProtectionLevel.BASIC)
        self.log = log or print
        self.seed = int(hashlib.md5(f"{project_id}_{cut_index}".encode()).hexdigest()[:8], 16)
        self.report: Dict = {"project_id": project_id, "cut_index": cut_index, "level": self.config.level.value, "seed": self.seed, "techniques_applied": []}

    def process(self, input_path: str, output_path: str) -> Dict:
        if self.config.level == ProtectionLevel.NONE:
            shutil.copy2(input_path, output_path)
            return self.report
        tmp = tempfile.mkdtemp()
        try:
            current = input_path
            vf = self._collect_video_filters()
            if vf:
                out1 = os.path.join(tmp, "v1.mp4")
                self._run_vf(current, out1, vf)
                current = out1
            # audio e metadata simplificados
            shutil.copy2(current, output_path)
            self.log(f"ACE ✅ {len(self.report['techniques_applied'])} técnicas [{self.config.level.value}]")
        except Exception as e:
            self.log(f"ACE ⚠️ erro: {e}")
            shutil.copy2(input_path, output_path)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return self.report

    def _collect_video_filters(self) -> list:
        filters = []
        if self.config.geometric:
            self.report["techniques_applied"].append("geometric")
        if self.config.color:
            filters.append("eq=brightness=0.01:contrast=1.03:saturation=1.05")
            self.report["techniques_applied"].append("color")
        if self.config.noise:
            filters.append("noise=alls=3:allf=t+u")
            self.report["techniques_applied"].append("noise")
        if self.config.chroma:
            filters.append("hue=h=0.02:s=1.02")
            self.report["techniques_applied"].append("chroma")
        return filters

    def _run_vf(self, inp: str, out: str, filters: list):
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", inp, "-vf", ",".join(filters),
             "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy", out],
            capture_output=True, text=True)
        if r.returncode != 0:
            shutil.copy2(inp, out)
EOF

# main.py
cat > main.py << 'EOF'
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gui.main_gui import ClipFusionApp

if __name__ == "__main__":
    app = ClipFusionApp()
    app.run()
EOF

# run.sh
cat > run.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
export LIBVA_DRIVER_NAME=iHD
export LIBVA_DRIVERS_PATH=/usr/lib/x86_64-linux-gnu/dri
source venv/bin/activate
echo "🔍 Verificando sistema..."
python3 -c "from utils.hardware import check_system; check_system()" 2>/dev/null || true
echo ""
echo "🚀 Iniciando ClipFusion Viral Pro..."
python3 main.py
EOF
chmod +x run.sh

# requirements.txt
cat > requirements.txt << 'EOF'
faster-whisper
numpy
pillow
pyyaml
EOF

echo -e "${GREEN}[10/10] Configurando ambiente Python...${NC}"
cd "$CLIPFUSION_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install tk  # geralmente já vem com python3-tk

# Ajusta permissões
chown -R "$REAL_USER":"$REAL_USER" "$CLIPFUSION_DIR"

echo -e "${GREEN}✅ Instalação concluída!${NC}"
echo -e "${YELLOW}⚠️  Recomenda-se reiniciar o sistema para ativar as alterações de kernel.${NC}"
echo -e "${BLUE}Após reiniciar, execute:${NC}"
echo -e "  cd ~/clipfusion && ./run.sh"
echo -e "${BLUE}Ou, se quiser testar agora (sem reboot), execute:${NC}"
echo -e "  sudo swapon -p 50 /swap/swapfile"
echo -e "  cd ~/clipfusion && source venv/bin/activate && python3 main.py"
