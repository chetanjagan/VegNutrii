# VegNutri

Meal planning and nutrition tracking built for Indian vegetarians: Jain, sattvic, vegan, eggetarian, lactose-free and vrat days.

VegNutri plans a week of real Indian meals around each user's calorie and protein targets, budget, cooking time, cuisine and kitchen rules. It then tracks the nutrients vegetarians most often run short on (iron, calcium, B12, zinc) and offers an AI coach that knows what the user has eaten today.

## What's inside

**For users**
- An optimizing meal planner over 118 regional meals (North Indian, South Indian, Gujarati, Maharashtrian, Bengali, pan-Indian, vrat). It typically lands within 1-5% of the calorie target, and it never breaks a diet rule or allergy (this is covered by tests).
- Strict diet modes (Jain excludes onion, garlic, root vegetables, egg and honey), plus allergy filters for peanut, tree nuts, gluten, soy, dairy, sesame and coconut.
- Vrat days, where chosen weekdays switch to sabudana, kuttu, rajgira and samak meals.
- Budget plans that keep each day near a rupee limit.
- One-tap meal swaps and one-tap "Ate this" logging from the plan.
- A grocery list generated from the plan and grouped by aisle.
- A family kitchen: one menu with per-person portions. Children get ICMR-NIN reference values and never a deficit.
- A micronutrient radar that compares the weekly average with ICMR-NIN 2020 reference intakes.
- An AI coach (Groq) that knows the user's targets, today's food, plan and diet rules, with safety rules built in.
- Tracking for food, water, weight, mood, a calendar and milestones, plus custom dishes.
- An installable phone app (PWA), light and dark themes, and full mobile support.

**Growth features**
- A free 7-day Pro trial for every new sign-up (14 days for invited friends). No card needed; it simply ends. Buying during a trial adds the paid time after the trial, so no days are lost.
- Coupon codes for festival offers and partners, created and switched on or off from `/admin`. Prices are rounded to whole rupees, so the price shown is exactly the price charged.
- Referrals: each user gets an invite link and a WhatsApp share button. When an invited friend makes their first payment, the inviter gets 30 days of Pro.
- A weekly progress email every Monday at 9 AM India time: protein days, averages, weight trend, low nutrients and a food tip, with one-click unsubscribe. It's scheduled free through GitHub Actions.

**For you, the operator**
- Free, Pro and Family plans with feature gating, paid through Razorpay with server-side signature checks and a webhook.
- An admin dashboard at `/admin` showing users, weekly actives, paying users, conversion and 30-day revenue.
- Data export and account deletion for India's DPDP Act, 2023, plus privacy, terms, refund and health-disclaimer pages.
- Security: CSRF protection, a strict Content-Security-Policy with nonces, rate limits on login and the coach, secure password hashing, and no third-party fonts or CDNs.
- Postgres-ready with Alembic migrations, Docker, Render blueprint, and GitHub Actions CI with 76 tests.

## Revenue model

| Plan | Price | What it adds |
|---|---|---|
| Free | ₹0 | Tracking, 3-day plans, 5 coach questions a day, iron tracking, 2-day grocery list |
| Pro | ₹99/month or ₹699/year | 7-day plans, budget plans, vrat days, all micronutrients, weekly grocery list, 60 coach questions a day |
| Family | ₹1,199/year | Everything in Pro, up to 4 family members with per-person portions, 100 coach questions a day |

Prices live in one place: `vegnutri/services/plans.py`. Payments are one-time for a fixed period with no auto-debit. That is a selling point in India, and it avoids the extra setup that recurring auto-debits need under RBI's e-mandate rules. Next revenue steps (see Roadmap): dietitian marketplace commissions, condition programmes, grocery partnerships and B2B wellness.

## Run it locally

You need Python 3.12.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env               # then set SECRET_KEY at least
flask --app wsgi db upgrade        # creates the database
flask --app wsgi run --debug
```

Open http://localhost:5000 and create an account.

To try the paywall without real payments, set `FLASK_DEBUG=1` and `DEMO_BILLING=1` in `.env` and leave the Razorpay keys empty. Upgrades are then free and instant. Demo billing refuses to run when debug is off.

To make yourself an admin, either put your email in `ADMIN_EMAILS` or run `flask --app wsgi make-admin you@example.com`.

## Admin access

Admins get **every Pro and Family feature free**, so you can use and check everything without paying. Admin access doesn't change your stored plan, isn't counted as a paying user in the stats, and never touches billing.

To become an admin on Render (the free plan has no shell, so use the environment variable):
1. In Render, open Environment and set `ADMIN_EMAILS` to your email. Separate several with commas.
2. Save, wait for the redeploy, then log out of VegNutri and log back in.
3. "Admin" appears in the sidebar. Open it, or go to `/admin`.

On the admin page:
- **Plans and what they include** lists every feature on Free, Pro and Family, built from the live settings in `vegnutri/services/plans.py`.
- **See the app as a user would** lets you preview as Free, Pro or Family, paywalls included. A bar at the top shows you're previewing; click Stop preview to get full access back. Only your own view changes.

Removing an email from `ADMIN_EMAILS` doesn't revoke an existing admin. To remove one, edit `is_admin` in the database.

## Configuration

Every setting is an environment variable. See `.env.example` for the full list with comments. The ones that matter:

| Variable | Needed for |
|---|---|
| `SECRET_KEY` | Required. A long random string. Sessions break without it. |
| `DATABASE_URL` | Postgres in production. Defaults to a local SQLite file. |
| `GROQ_API_KEY` | The AI coach. Create one at console.groq.com/keys. Run `flask --app wsgi coach-check` to test it. |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Payments. |
| `BREVO_API_KEY`, `MAIL_FROM` | Email (password resets, weekly summary) via Brevo's HTTPS API. Free tier: 300 emails a day. `MAIL_FROM` must be a sender you've verified in Brevo. |
| `MAIL_SERVER` and related | SMTP email instead of Brevo. Some hosts' free tiers block SMTP ports, so Brevo is the safer choice. |
| `TASK_TOKEN` | Secret shared with the weekly-email GitHub Action. Render generates one for you. |
| `TRIAL_DAYS`, `REFERRAL_TRIAL_DAYS`, `REFERRAL_REWARD_DAYS` | Trial and referral lengths (defaults 7, 14 and 30 days). `TRIAL_DAYS=0` turns trials off. |
| `SESSION_COOKIE_SECURE=1` | Set this in production (HTTPS). |
| `APP_URL`, `SUPPORT_EMAIL`, `COMPANY_NAME` | Shown in emails and legal pages. |

## Set up payments (Razorpay)

1. Create a Razorpay account and complete KYC. Razorpay checks that your site shows privacy, terms, refund and contact details; these pages already exist at `/privacy`, `/terms`, `/refunds` and in the footer.
2. Under Account and Settings, then API Keys, generate keys. Start with Test Mode keys.
3. Under Webhooks, add `https://YOUR-DOMAIN/api/billing/webhook` with the events `payment.captured`, `order.paid` and `payment.failed`, and set a secret. Put it in `RAZORPAY_WEBHOOK_SECRET`.
4. Buy Pro with a Razorpay test card, then check that `/account` shows the payment and `/admin` shows the revenue.
5. Swap in Live Mode keys when you launch.

The webhook means a user is upgraded even if they close the tab mid-payment. Activation is idempotent and checks the paid amount.

## Deploy

**Render (simplest).** Push to GitHub, then in Render choose New, then Blueprint, and pick the repo. `render.yaml` creates the web service and a Postgres database in Singapore (closest to India), runs migrations before each deploy, and generates `SECRET_KEY`. Fill in the variables it asks for. Check Render's current plan names and prices; the ones in `render.yaml` may need updating.

**Docker / any VPS.**
```bash
cp .env.example .env    # fill it in
docker compose up --build
```
The container runs `flask db upgrade` and then gunicorn on port 8000. Put it behind HTTPS (Caddy, nginx, or your platform's load balancer).

**Heroku-style platforms (Railway and similar).** The `Procfile` runs migrations on release and gunicorn for web.

With more than one server instance, set `RATELIMIT_STORAGE_URI` to a Redis URL so rate limits are shared.

## Set up the growth features

**APP_URL.** Set it to your live address, for example `https://vegnutri.onrender.com`. Invite links and every link in the weekly email are built from it, so without it they point at `localhost`.

**Email (Brevo).**
1. Create a free account at brevo.com.
2. Under Senders, add and verify the address you'll send from.
3. Under SMTP and API, then API Keys, create a key.
4. In Render, set `BREVO_API_KEY` to the key and `MAIL_FROM` to `VegNutri <the-address-you-verified>`.
5. Test it with "Forgot password?" on your own account.

**Weekly email schedule (GitHub Actions).**
1. In Render, open Environment and copy the value of `TASK_TOKEN`.
2. In GitHub, open the repo's Settings, then Secrets and variables, then Actions. Add two repository secrets: `APP_URL` (your live address) and `TASK_TOKEN` (the value you copied).
3. In the Actions tab, open "Weekly progress email" and click Run workflow to test it now. After that it runs every Monday on its own.

Users can turn the email off from Account or from the link at the bottom of each email. People with no logs in 30 days aren't emailed.

**Coupons.** In `/admin`, scroll to Coupons, enter a code (such as `DIWALI25`), the discount, an optional usage limit and last day, then click Create coupon. Customers type it on the pricing page.

## Moving from the old version (v3)

The old app was a single `app.py` with a SQLite `nutrition.db`. To bring existing users across:

```bash
flask --app wsgi db upgrade
python scripts/import_v3_sqlite.py path/to/nutrition.db --dry-run   # preview
python scripts/import_v3_sqlite.py path/to/nutrition.db
```

Passwords keep working (old SHA-256 hashes are upgraded on first login). Targets are recalculated with the new, safer formula. Allergies written as free text are converted to filters. **Stored Gemini API keys are deliberately not imported.** They were kept in plain text, so treat them as exposed and ask anyone who entered one to revoke it in Google AI Studio.

When updating the GitHub repo, delete the old `app.py`, `templates/` and `static/` folders at the top level. Everything now lives in `vegnutri/`.

## Tests

```bash
pytest -q
```

118 tests cover admin access and preview, trials, coupons, referrals and the weekly email, plus diet-rule compliance for every diet mode, cuisine and allergy; fasting days; calorie accuracy; target safety floors; children's targets; login, reset tokens and open-redirect protection; CSRF and security headers; users being unable to read or delete each other's data; server-side nutrition values; Razorpay signature, webhook, amount and renewal handling; plan gating; coach quotas; and data export and deletion. CI runs them on every push against both SQLite and Postgres, and checks that migrations apply cleanly and match the models. To run them against Postgres locally, set `TEST_DATABASE_URL=postgresql://...`.

## Project layout

```
wsgi.py                     entry point
vegnutri/
  __init__.py               app factory, security headers, error pages, CLI
  config.py  models.py  extensions.py
  data/                     foods.py (components), meals.py (118 meals), recipes.json, tips.json
  services/                 planner, nutrition, billing, coach, plans, tracking, mailer
  blueprints/               main, auth, tracker, planner, coach, billing, account, admin
  templates/  static/       UI (self-hosted fonts and Chart.js)
migrations/                 Alembic migrations
scripts/import_v3_sqlite.py
tests/
```

To change the schema, edit `models.py`, run `flask --app wsgi db migrate -m "what changed"`, review the generated file, then `flask --app wsgi db upgrade`.

To add a meal, add components to `data/foods.py` if needed, then one line in `data/meals.py`. Nutrition, cost, diet tags and grocery needs are derived automatically, and the tests will catch broken references.

## Before you launch: checklist

These need a human; code can't do them.

- **Have a registered dietitian review the food data.** Values in `data/foods.py` are approximate, compiled from IFCT 2017 and similar references. Have them checked against IFCT 2017 and adjusted. "Dietitian-reviewed" is also a strong marketing claim once it's true.
- **Have a lawyer review the legal pages.** Fill in the grievance officer, registered address and jurisdiction in `templates/legal/privacy.html` and `terms.html`, and confirm the refund policy matches what you want.
- **Business setup.** Register the business, ask a chartered accountant about GST registration (for services the turnover threshold is ₹20 lakh in most states), and complete Razorpay live-mode KYC.
- **Email.** Set up a transactional email provider (Amazon SES, Postmark, Zoho ZeptoMail) and a real support inbox.
- **Monitoring.** Add uptime checks on `/healthz` and error tracking (for example Sentry).
- **Backups.** Turn on automated Postgres backups.
- **AI spend and limits.** Watch usage in the Groq console and move to a paid tier before launch; free-tier rate limits are low. Pro quotas cap per-user cost.

## Roadmap

These are the highest-value next steps, roughly in order:

1. **Grow the meal catalogue with a dietitian**, especially sattvic Maharashtrian, Bengali and Rajasthani, plus more vegan options. This is the product's moat.
2. **WhatsApp delivery for the weekly summary.** The email version is built; WhatsApp gets far higher open rates in India.
3. **Photo and voice logging** in Indian languages, using a vision model and Groq's Whisper speech-to-text.
4. **Dietitian marketplace.** Verified dietitians run paid programmes in the app and you take a commission.
5. **Condition programmes** for PCOS, prediabetes and thyroid, built with clinicians.
6. **Grocery partnerships.** Turn the grocery list into a cart through quick-commerce affiliate programmes where available.
7. **B2B.** Gyms, corporate wellness, hostels and tiffin services using the family-kitchen engine.
8. **Native app wrappers** (Capacitor or a Trusted Web Activity) for Play Store presence.

## Licence

Code: choose a licence before making the repo public. Bundled fonts are under the SIL Open Font License and Chart.js under MIT (see `vegnutri/static/fonts` and `vegnutri/static/vendor`).
