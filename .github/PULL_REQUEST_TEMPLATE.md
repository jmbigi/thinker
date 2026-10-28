# Pull request

## Qué cambia y por qué

<!-- Un cambio por razón. Si corrige un defecto, enlaza la reproducción. -->

## Checklist de gates (obligatorio)

- [ ] `make check` en verde (lint, preflight, docs-check, tests, secretos, CI local, hook)
- [ ] Tests nuevos si cambia comportamiento; sin aserciones triviales
- [ ] Cifras de estado actualizadas en TODOS los sitios que las citan (regla 11 / `make docs-check`)
- [ ] Sin secretos, claves ni datos personales en código, tests, docs ni este PR (P0.6/P0.9)
- [ ] Sin fallbacks silenciosos ni `except: pass` nuevos (P1.19/P1.26)
- [ ] Lecciones aprendidas añadidas si hubo hallazgo (P1.20)
- [ ] Dogfooding declarado: qué componente de thinker se usó y qué evidencia aportó (regla 14)
- [ ] Sin CLI `gh` ni GitHub Releases como parte del flujo (regla 12)

## Declaración de IA

<!-- Si usaste un modelo de IA de forma significativa, indica cuál. El programador responde del resultado. -->
Assisted-by:
