# Feed curation + domain + reader redesign
Objective: curate custom feeds by hand (picks + rules, no duplicates), serve /peruinformado.xml on feed-rss.ntv-app.com, redesign the reader UI.
Branch: master · Delivery: ask-on-risk · Runner: `poetry run pytest tests`

## Specs
- S1: "Lo elegido más lo manual, pero sin duplicados, o sea descartar si ya está en el feed" — a custom feed serves manual picks plus rule matches, deduplicated; picks are never dropped by max_items.
- S2: "usemos las skills de desing como /impeccable o /design-taste-frontend /hallmark para mejorar notablemente este feedly personal"
- S3: "debemos usar dominio propio feed-rss.ntv-app.com y para peru informado feed-rss.ntv-app.com/peruinformado.xml"
- S4: explicit `manual` flag on a feed ignores rules and serves only picks (added after browser test showed a rule-less feed served everything).

## Tasks
- T1 (S1,S3,S4) backend: feed_picks table, merge, picks API, /<slug>.xml alias — inline — done (verified vs temp Postgres)
- T2 (S3) domain config + docs (APP_URL default); Coolify/DNS are the user's — inline — done (APP_URL base + compose default; Coolify/DNS pending, user)
- T3 (S2) frontend redesign with "add to feed" per entry — inline — done (verified in browser 1440/390 vs temp Postgres; no JS errors)

## Log
- L1 (2026-10-30): "Lo elegido más lo manual, pero sin duplicados, o sea descartar si ya está en el feed, además usemos las skills de desing como /impeccable  o /design-taste-frontend /hallmark  para mejorar notablemente este feedly personal, además debemos usar dominio propio feed-rss.ntv-app.com y para peru informado feed-rss.ntv-app.com/peruinformado.xml"
