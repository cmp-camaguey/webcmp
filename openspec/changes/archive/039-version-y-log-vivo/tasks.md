# 039-version-y-log-vivo — tareas

- [x] 1. Tests RED: `_ls_remote()` con `refs/tags/*` + peeled, `_version_for()`
       (preferencia `v*` y estable sobre prerelease, tag exacto o `None`) y
       `build_state()` con `deployed_version`/`version`. (S1, S2)
- [x] 2. `apps/dashboard/views/dashboard/update.py`: ampliar `_ls_remote()`,
       añadir `_version_for()` y los dos campos en `build_state()`. (S1, S2)
- [x] 3. `templates/includes/dashboard/update_navbar.html`: nodo
       `update-navbar-version`. (S3)
- [x] 4. `static/dist/js/dashboard-update.js`: render del chip, label del
       botón «Actualizar a vX.Y.Z», detalle «Instala vX.Y.Z (sha)…», log en
       vivo (relectura en el polling con modal abierto + `running`, última
       al terminar, autoscroll condicional). (S3, S4)
- [x] 5. `deploy/README-deploy.md`: párrafo de chip y log en vivo. (S6)
- [x] 6. Suite + ruff + djlint en verde. (todas)
- [x] 7. PR a `dev` con squash. (todas) — #250, squash `931a9cd`.
- [x] 8. Tras merge: promover `dev`→`main` (merge commit) + tag/release
       v0.7.4 (solo versión) → el usuario pulsa «Actualizar» en el panel. (S7)
       Merge #251 (`a15f174`), tag `v0.7.4` con cuerpo; deploy validado en el
       panel: chip con la versión y log en vivo actualizándose solo.
