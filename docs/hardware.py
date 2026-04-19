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
