# Cómo contribuir

Gracias por el interés. Este proyecto es pequeño y valora más la evidencia que
el volumen: un cambio con una prueba de aceptación verificable vale más que diez
sin ella.

## Preparar el entorno

```bash
python3 -m pip install --require-hashes -r requirements.lock
make hook          # instala el hook pre-commit (ruff, secretos, tests, holdout…)
```

Python **3.11+**. Los tests son offline y deterministas: no necesitas claves ni
red (`MockLLM`/`MockSearchAPI` están declarados como simulados).

## Antes de abrir un pull request

```bash
make check         # lint + preflight + docs-check + tests + secretos + CI local + hook
make doctor        # autodiagnóstico del entorno si algo falla
make verify-install  # instalación limpia del paquete en un venv temporal
```

`make check` debe quedar en verde. La verificación es **local por diseño**:
no se depende de GitHub ni de CI en la nube (regla 12).

## Reglas que no se negocian

Resumen de `AGENTS.md` (el documento completo manda):

1. **No afirmar sin evidencia**: lo no verificado se declara como no verificado.
2. **Sin secretos ni datos personales** en código, tests, docs o commits.
3. **Sin fallbacks silenciosos**: los errores se elevan y se reportan.
4. **Tests reales**: un test que no puede fallar no es un test. Lo simulado se
   declara como simulado.
5. **Cambios pequeños y verificables**: un cambio por razón, con su prueba.
6. **Documentación al día**: si cambias una cifra de estado, actualiza todos los
   sitios que la citan (`make docs-check` lo comprueba).
7. **Dogfooding**: usa componentes del propio proyecto en las mejoras y deja
   constancia de qué aportaron (regla 14 de `AGENTS.md`).
8. **Licencias**: el proyecto es GPL-3.0-only; toda dependencia nueva debe ser
   compatible y declararse en `requirements.txt` (P0.18).

## Commits y autoría

- Mensajes claros, en español, con el alcance del cambio.
- Si usaste un modelo de IA de forma significativa, añade el trailer
  `Assisted-by: <herramienta>` (regla P1.14). El programador responde del
  resultado; no se atribuye co-autoría a modelos.
- No se usa la CLI `gh` ni GitHub Releases como parte del flujo: la publicación
  se hace con git estándar y PyPI (`docs/PUBLICACION.md`).

## Reportes de seguridad

No abras un issue público: usa el reporte privado descrito en `SECURITY.md`.

## Conducta

Al participar aceptas el `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1).
