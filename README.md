# Gig Credit Passport

A worker-owned, explainable financial passport & credit score for India's gig
workers — built on the Account Aggregator framework, with OCR-based
self-reported income as a supplementary, cross-verifiable signal.

Positioning: not a lender. This is the scoring/passport layer. Real credit
disbursal happens via lenders plugged in through OCEN later — see the
regulatory notes in the project chat history / your own notes for why that
sequencing matters.

## Architecture

```
app/
  main.py              FastAPI app entrypoint, route registration
  core/
    config.py          Settings (loaded from .env)
    security.py        JWT + OTP hashing
  db/
    session.py          Async SQLAlchemy engine/session
  models/
    models.py           All DB models: User, ConsentArtifact, FinancialAccount,
                         Transaction, SelfReportedEarning, OTPChallenge, Score
  services/
    aa_client.py         Account Aggregator client (Mock + real Setu sandbox skeleton)
    consent_service.py   Consent lifecycle (audit trail)
    accounts_service.py  Pulls + categorizes financial data via AA
    ocr_service.py       OCR extraction from uploaded earnings screenshots
    auth_service.py      OTP request/verify, JWT issuance
  scoring/
    features.py           Feature engineering (8 explainable features)
    train.py               Synthetic-data model training script
    model.py               Inference + human-readable reason codes
    artifacts/model.pkl     Trained model (regenerate with `python -m app.scoring.train`)
  api/
    deps.py              Auth dependency (get_current_user_id, require_self)
    routes/               All FastAPI routers: auth, users, consent, accounts,
                           self_reported, score, health
migrations/              Alembic migrations (async)
```

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```
Also needs system packages for OCR: `tesseract-ocr`, `poppler-utils` (for
`pdf2image`). On Ubuntu/Debian:
```bash
apt-get install -y tesseract-ocr poppler-utils
```

### 2. Postgres
```bash
# Install + start Postgres 16, then:
createdb gigpassport
```

### 3. Environment
```bash
cp .env.example .env
# Fill in DATABASE_URL, SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_hex(32))")
```

### 4. Migrate
```bash
alembic upgrade head
```

### 5. Train the scoring model
```bash
python -m app.scoring.train
```

### 6. Run the backend
```bash
uvicorn app.main:app --reload
```
API docs: `http://localhost:8000/docs`

### 7. Run the frontend
```bash
cd frontend
npm install
cp .env.example .env   # points at http://localhost:8000/api/v1 by default
npm run dev
```
Opens at `http://localhost:5173`. Login uses phone + OTP — since no SMS
gateway is wired up yet, the OTP is shown directly on the login screen in
dev mode (small amber banner) so you can test without a real phone.

## Frontend

React (Vite) + Tailwind v4 + React Router. Structure:
```
frontend/src/
  api/client.js         Axios instance, attaches JWT from localStorage,
                         auto-redirects to /login on 401
  context/AuthContext.jsx  OTP request/verify, login state
  pages/
    Login.jsx            Phone -> OTP -> dashboard flow
    Dashboard.jsx         Wires all components to real API calls
  components/
    ScoreCard.jsx         Score gauge + reason codes
    ConsentPanel.jsx       Link/sync/revoke accounts — the audit trail UI
    UploadEarnings.jsx     OCR screenshot upload, clearly labeled unverified
    TransactionsList.jsx   Recent transaction feed
```

Every API call was cross-checked against the actual backend route
definitions (path, method, and payload shape) to make sure the two sides
actually agree — not just "should work in theory."

## Auth flow

Phone + OTP (no email/password — matches how gig workers already
authenticate everywhere else):

1. `POST /api/v1/auth/otp/request {phone_number}` — in DEBUG mode, the OTP
   is returned in the response as `debug_otp` since no real SMS gateway is
   wired up yet. **This must be removed before production** — see the TODO
   in `auth_service.py`. Rate limited per phone number: a 30-second cooldown
   between requests, and a cap of 5 requests per rolling hour (both verified
   working with real HTTP tests, not just implemented).
2. `POST /api/v1/auth/otp/verify {phone_number, otp, full_name}` — creates
   the user on first verification, returns a JWT.
3. All other endpoints require `Authorization: Bearer <token>`. Every route
   derives `user_id` from the token — never trust one passed in the URL/body.

## Account Aggregator integration

`app/services/aa_client.py` has two implementations behind one interface:
- **MockAAClient** (default): generates realistic gig-worker transaction
  data locally. No credentials needed — this is what runs today.
- **SetuAAClient**: real Setu sandbox/production integration. Activates
  automatically once `AA_CLIENT_ID` / `AA_CLIENT_SECRET` are set in `.env`.
  The consent + fetch flow is structured to match Setu's real API, but the
  FI-data response parser needs finishing once you can see actual sandbox
  payloads (register at https://setu.co for sandbox access).

## OCR (self-reported earnings)

Supplementary signal only — never conflated with AA-verified data. A worker
can upload a gig-platform earnings screenshot (`POST
/api/v1/self-reported/upload`); it's OCR'd, structured, and stored in a
separate table (`self_reported_earnings`), always starting `is_verified =
False`. The scoring pipeline cross-checks self-reported totals against real
AA transaction data per platform/month (`self_reported_confirmation_ratio`
feature) — this is what lets it contribute to the score without being
spoofable by just uploading a doctored screenshot.

## Scoring model

**XGBoost** (gradient-boosted trees), trained on **synthetic data** for
now (see the reasoning in `train.py`'s docstring — no real repayment-
outcome data exists yet since no real loans have been disbursed through
this product). Retraining on real outcomes later is a drop-in
replacement; nothing about the API changes.

Score scale: 300–900 (CIBIL-like, familiar to Indian users/lenders). Every
score comes with **narrative reason codes** derived from real SHAP
(Shapley value) attribution — the actual industry-standard explainability
technique for credit scoring, correctly accounting for feature
interactions (e.g. income consistency mattering more when a worker has
fewer platforms) that a linear coefficient could never capture.

### Honest evaluation (not just a headline number)

Run `python -m app.scoring.train` to see the full breakdown. As of this
session:

- **AUC 0.72** (held-out test set) — real discrimination ability, but
  moderate, not strong. Worth being upfront about: production credit
  models typically target 0.75-0.85+.
- **Brier score 0.10** (calibration) — genuinely good. When the model
  says "88% chance of good repayment," that number is honest, not just a
  ranking — checked by bucketing predictions and comparing to actual
  outcome rates.
- **A real trap this caught, not shipped**: the training population is
  realistically imbalanced (~87% "good", consistent with published gig/
  microfinance repayment research), so plain accuracy at the default 0.5
  classification threshold is misleading — a model that always predicts
  "good" would already score ~87% without learning anything. Balanced
  accuracy at 0.5 was 0.51 (no better than guessing) once actually
  checked. Two tempting fixes were tried and **rejected** after testing:
  `scale_pos_weight` reweighting fixed recall but wrecked calibration
  (Brier 0.10 → 0.21); isotonic calibration on top of that restored
  calibration but erased the recall fix entirely. The correct fix, with
  **zero tradeoff**, was choosing a better decision threshold (0.884,
  found via the ROC curve) instead of distorting the model's probabilities
  — balanced accuracy went from 0.51 to 0.67 with the calibration
  completely untouched. This threshold is saved in the model artifact
  (`optimal_decision_threshold`) but isn't used anywhere yet, since the
  app serves a continuous score, not a binary decision — it matters the
  moment a future approve/deny feature gets built, so nobody reaches for
  the default 0.5 and silently reintroduces the recall collapse.
- **Still true no matter how good these numbers look**: every metric here
  is measured against a formula I wrote (see `generate_synthetic_dataset`
  in `train.py`), not real human repayment behavior. That caveat doesn't
  go away until real user outcomes exist to retrain against.

## Frontend

React (Vite) + Tailwind v4 + React Router + Recharts + lucide-react icons.
Rebuilt this session with a deliberate visual identity: deep teal ink and
warm cream paper tones, IBM Plex Sans/Mono typography, no purple, no
gradients, no pill-shaped buttons, no emoji, no em dashes anywhere in
user-facing copy (checked programmatically, not just by eye). Structure:
```
frontend/src/
  api/client.js            Axios instance, attaches JWT, redirects to
                            /login on 401
  context/
    AuthContext.jsx          OTP request/verify, login state
    DataContext.jsx           Single source of truth for score, consents,
                               transactions, passports, events — fetched
                               once, shared across every page via context
                               so navigating doesn't refetch or lose state
  components/
    Layout.jsx                Sidebar nav (desktop) / bottom nav (mobile)
    ScoreCard.jsx              Score gauge + narrative reason codes
    IncomeTimeline.jsx          Stacked bar chart, income by platform by
                                 month — the visual proof of the
                                 fragmentation thesis this product is
                                 built on
    SimulatorPanel.jsx          The what-if planner
    PassportPanel.jsx           Issue/list/revoke, copy a shareable link
    ConsentPanel.jsx             Link/sync/revoke accounts
    EventsFeed.jsx                Score change history
    TransactionsList.jsx          Recent transaction feed
    UploadEarnings.jsx            OCR screenshot upload
    WhatsAppDemo.jsx               In-app chat widget hitting the real
                                    webhook
  pages/
    Login.jsx, Home.jsx, Insights.jsx, PassportPage.jsx, ActivityPage.jsx,
    AssistantPage.jsx, PassportVerify.jsx (public, no login),
    PrivacyPolicy.jsx, TermsAndConditions.jsx
```

Every API call was cross-checked against the actual backend response
shapes (field-by-field, via curl) before being wired into components.

### Connecting a custom domain

This is a real-world deployment step I cannot do from here — it needs
your own hosting account and domain registrar access, not something
achievable inside this project's code. Once you deploy the built
frontend (`npm run build` produces `dist/`) to a host — Vercel, Netlify,
Render, or similar all support this the same way — the general steps
are:
1. Buy/own a domain through any registrar (Google Domains successor,
   Namecheap, GoDaddy, etc.).
2. In your hosting provider's dashboard, add your domain as a "custom
   domain" for this project.
3. The host gives you DNS records (usually a `CNAME` or `A` record) to
   add at your domain registrar.
4. Add those records in your registrar's DNS settings. Propagation
   typically takes anywhere from a few minutes to 24 hours.
5. Most hosts (Vercel, Netlify) provision an SSL certificate for the
   domain automatically once DNS resolves correctly — no separate
   certificate purchase needed.

Also update `CORS_ALLOWED_ORIGINS` in the backend's `.env` to include
your real domain once this is live — see the Security posture section
above.

## What's built and tested end-to-end (as of this session)

- User signup/login via OTP → JWT, with rate limiting (30s cooldown + 5/hour
  cap per phone number, verified with real requests)
- Consent lifecycle: initiate, check status, revoke (revocation verified to
  actually block further data sync)
- Account sync via mock AA → categorized transactions in Postgres
- OCR upload → structured, cross-verifiable self-reported earnings
- Score computation with reason codes, persisted history
- Cross-user access protection (one worker cannot touch another's data —
  verified with two real accounts)
- Frontend confirmed working in a real browser (login → dashboard → score
  → link account → compute score), run by the user themselves via WSL

## Advanced features (added this session, differentiators vs. existing
## alternative-data scoring platforms like FinBox/Karza/Certus)

- **Verifiable, shareable passport** (`/api/v1/passport/*`) — a worker can
  issue a passport from any of their scores and share a link; anyone can
  verify it's real via `GET /passport/verify/{id}` with **zero
  authentication**. Signed with HMAC-SHA256 (`app/services/passport_service.py`)
  — genuinely tamper-evident (verified: directly editing a passport's score
  in the database was caught via signature mismatch), revocable, and
  expiring. Honest limitation, documented in the code: HMAC requires
  calling our API to verify — true offline/self-sovereign verification
  would need asymmetric signing (RSA/EdDSA) instead, a contained future
  upgrade, not a redesign.
- **Tamper-evident score history** (`app/scoring/hash_chain.py`) — every
  score hash-chains off the previous one. `GET /score/verify-integrity`
  recomputes the whole chain and flags exactly which record was altered if
  anything was. Verified by directly editing a score's value in Postgres
  and confirming it was caught.
- **Score simulator** (`POST /score/simulate`) — "what if I file my ITR /
  get N more months of history / add N more platforms" — projects a score
  without touching real data. `itr_filed` is a genuinely trained model
  feature (not a hardcoded number) added specifically to back this claim
  honestly; verified the simulated prediction matched the real outcome
  exactly once actually declared via `PATCH /users/me/itr-status`.
- **Event-driven auto-rescoring** (`app/services/scoring_service.py`) — a
  single shared function recomputes and persists a score from any trigger
  (manual click, account sync, ITR status change), logging every change to
  `score_change_events` with a real delta. Verified: syncing new data alone
  (zero manual "compute" clicks) produces a real, hash-chained score.
- **WhatsApp-style command interface** (`/api/v1/whatsapp/webhook`) — real
  command-parsing and business logic (`score`, `simulate itr`, `passport`,
  `help`), identified by phone number the same way a real WhatsApp
  Business integration would be. Only the actual message-delivery hop is
  mocked (same pattern as the OTP SMS gateway) — swapping in a real
  WhatsApp Business API/Twilio webhook later doesn't change this logic.

## Frontend additions this session

- `PassportPanel.jsx` — issue/list/revoke passports, copy a shareable
  verify link
- `SimulatorPanel.jsx` — sliders/checkbox for the what-if planner
- `EventsFeed.jsx` — "your score just moved, and why" feed
- `WhatsAppDemo.jsx` — in-app chat widget hitting the real webhook
- `pages/PassportVerify.jsx` at `/verify/:passportId` — the public,
  no-login page a lender/landlord would actually open from a shared link
- Every new API call cross-checked against the real backend response
  shapes (field-by-field, via curl) before being wired into components

## Testing

Real automated test suite (`tests/`), not manual curl checks — 23 tests
covering every trust-critical claim made in this README: OTP auth and
rate limiting, consent revocation genuinely blocking access, hash-chain
tamper detection (including a direct database edit, bypassing the API
entirely), passport signature tamper detection, cross-user isolation, and
the ITR-fairness bug regression-tested so it can't silently return.

Runs against a fully separate `gigpassport_test` database — never touches
real dev data. Run with:
```bash
python -m pytest tests/ -v
```

## Security posture

- **Separate signing keys**: `SECRET_KEY` (JWT auth) and
  `PASSPORT_SIGNING_KEY` (passport HMAC) are deliberately independent —
  reusing one secret for both purposes would mean a leak of either
  compromises both. The app refuses to start in production
  (`ENV=production`) if they're identical, still set to their placeholder
  values, `DEBUG` is left on, or `CORS_ALLOWED_ORIGINS` isn't set — see
  `Settings.validate_production_safety()` in `app/core/config.py`.
- **CORS**: explicit allow-list (`CORS_ALLOWED_ORIGINS`) takes priority
  whenever set; falls back to wide-open only when `DEBUG=true`; blocks
  everything by default otherwise.
- **Passport verification audit log**: every check against the public,
  no-auth `/passport/verify/{id}` endpoint is logged (passport ID,
  requester IP, outcome) — this is the one endpoint in the system
  deliberately reachable with zero authentication, so logging is the only
  way to notice abuse (e.g. one IP enumerating passport IDs).
- **Dependency vulnerability scan**: run via `pip-audit -r requirements.txt`.
  As of this session, down from 10+ vulnerable packages across 5
  libraries to one unresolved item: `ecdsa` (a transitive dependency of
  `python-jose`) has a known, publicly-documented timing-attack issue
  (PYSEC-2026-1325) that its maintainers have declined to fix — there is
  no patched version to upgrade to. Worth revisiting by switching JWT
  libraries (e.g. to `pyjwt`) if this becomes a real concern before
  production.

## CI

`.github/workflows/tests.yml` runs the full test suite automatically on
every push and PR — spins up a real Postgres service container, trains
the model, runs all 23 tests. A test suite nobody re-runs automatically
is just documentation with extra steps; this closes that gap.

## Secrets handling — local dev vs. real deployment

**Local dev** (what this README has you doing): a plaintext `.env` file,
gitignored, is completely fine. Nobody else can read your laptop's
filesystem.

**Real deployment — plaintext `.env` files are not acceptable.** Concretely:

- Use your host's actual secrets manager: AWS Secrets Manager / Parameter
  Store, HashiCorp Vault, or even just properly configured environment
  variables injected by your deployment platform (Render, Railway, Fly.io
  all support this natively) — never a `.env` file sitting on disk in
  production.
- **Rotate `SECRET_KEY` and `PASSPORT_SIGNING_KEY` independently** if
  either is ever suspected of leaking — this is the whole reason they're
  separate now (see Security posture above). Rotating `SECRET_KEY`
  invalidates all outstanding JWTs (forces re-login); rotating
  `PASSPORT_SIGNING_KEY` invalidates all outstanding passport signatures
  (issued passports would need reissuing) — know that tradeoff before
  rotating either.
- **Never commit a real `.env`** — `.gitignore` already excludes it, but
  double-check before your first real push (`git status` should never
  show `.env`, only `.env.example`).
- The startup safety check (`validate_production_safety()`) is a backstop
  for exactly this category of mistake — it refuses to boot with
  placeholder secrets in `ENV=production`, but it can't catch a real
  secret accidentally committed to git history. If that ever happens,
  rotating the leaked secret is not optional — assume it's compromised
  the moment it's pushed, even if you delete the commit afterward (git
  history isn't reliably erasable after a push).

## Known gaps / next steps

- **SMS gateway**: OTP is only returned in DEBUG mode right now. Needs a
  real provider (MSG91, Twilio) before any real user can log in. The same
  gateway would also carry real WhatsApp messages once that's wired up.
- **Setu sandbox real integration**: client is scaffolded but not hooked up
  to a live sandbox account yet (needs registration + credentials).
- **Real AA sandbox redirect flow**: the mock client activates consent
  instantly; Setu's real flow requires redirecting the user to an approval
  URL and polling/webhooking for status — the frontend doesn't handle that
  redirect yet.
- **Passport asymmetric signing**: current HMAC signing proves the passport
  came from this backend and hasn't been altered, but verification still
  requires calling our API. True self-sovereign verification (no API call
  needed) requires swapping in a real signing keypair — noted in
  `passport_service.py`, not yet built.
- **Group credit circles** (digitized chit fund) — deliberately not built
  yet; needs real lender-partnership thinking to be more than a UI mockup,
  not a today problem.
- **Frontend redesign not yet clicked through in a real browser** — the
  full navigation, chart, and every component build cleanly, and every
  API call was checked against real backend responses field by field, but
  I have no browser access in this sandbox to visually confirm layout and
  interactions myself. Run `npm run dev` and walk through: compute a
  score, view the income timeline chart on Insights, issue a passport,
  copy the verify link and open it in an incognito tab, try the
  simulator, try the assistant.
- No CI pipeline: done this session, see the CI section above.
