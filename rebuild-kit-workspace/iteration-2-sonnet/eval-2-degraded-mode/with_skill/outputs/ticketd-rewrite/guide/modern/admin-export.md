# Admin / Export (designed-not-built)

**Designed, not built** — `WO-005`, low risk, no gate. Same 3-column CSV shape (`id,title,
status`), implemented with a real CSV writer instead of legacy's unescaped f-string join — a
FREE implementation choice that happens to fix a latent comma-in-title bug as a side effect, not
because anyone reported it as a defect. The route stays even though a legacy comment suggests
it's unused, per the do-not-port evidence bar (see `guide/legacy/admin-export.md`).
