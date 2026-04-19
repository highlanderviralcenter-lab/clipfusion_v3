"""
Motor de criação de ganchos virais.

O método generate gera diferentes estilos de hooks com base no
arquétipo fornecido e no texto do segmento.
"""
from typing import Dict
from .archetypes import ARCHETYPES

class ViralHookEngine:
    def generate(self, archetype: str, segment_text: str) -> Dict[str, str]:
        desc = ARCHETYPES.get(archetype, '')
        snippet = segment_text.strip()[:40] or 'este assunto'
        return {
            'hook_direct': f'{desc} {snippet}',
            'hook_question': f'Você já se perguntou por que {snippet}?',
            'hook_challenge': f'Desafie-se a entender {snippet} de verdade!',
        }
