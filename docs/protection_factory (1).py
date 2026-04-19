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
