"""ClipFusion — Hook Engine. Gerador de ganchos virais por arquétipo."""
import random
from viral_engine.archetypes import ARCHETYPES
from viral_engine.audience_analyzer import AudienceAnalyzer
from viral_engine.secondary_group import SecondaryGroupStrategy
from viral_engine.platform_optimizer import PlatformOptimizer


class ViralHookEngine:
    def __init__(self):
        self.analyzer  = AudienceAnalyzer()
        self.secondary = SecondaryGroupStrategy()

    def generate(self, tema: str, nicho: str, platform: str, archetype_id: str = None) -> dict:
        audience     = self.analyzer.analyze(nicho, platform)
        archetype_id = archetype_id or list(ARCHETYPES.keys())[0]
        archetype    = ARCHETYPES[archetype_id]
        perfil       = audience["perfil_primario"]
        template     = random.choice(archetype["hook_template"])
        hook_base    = template.format(
            tema=tema, publico=perfil.get("faixa_etaria","público"),
            problema=tema, resultado="sucesso",
            estado_negativo="dificuldades", estado_positivo="resultados",
            tempo="6 meses", consequencia="perder oportunidades",
            algo="seu futuro", industria="o mercado",
            numero="milhares de", esforco="muito", injustica="não consegue avançar",
        )
        enhanced = self.secondary.dual_hook(hook_base, nicho, audience["grupo_secundario"])
        final    = PlatformOptimizer.optimize(enhanced, platform)
        return {
            "gancho_final": final, "gancho_original": hook_base, "archetype": archetype,
            "publico": perfil, "expansao": audience["grupo_secundario"],
            "timing": audience["timing_otimo"], "hashtags": audience["hashtags_sugeridas"],
            "cta": archetype["cta"], "cores": archetype["cores"],
            "musica": archetype["musica"], "duracao": archetype["duracao_ideal"],
        }
