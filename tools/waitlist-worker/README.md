# sota-hack-waitlist

A Cloudflare Worker that stores waitlist sign-ups for the site in a D1 database
(`sota-hack-waitlist`) and serves the public count. Live at
<https://sota-hack-waitlist.amgrobelnik.workers.dev>.

## What it stores

- `signups`: one row per person, keyed by email (lower-cased, spaces removed):
  name, email, organisation, build, variant, and a server timestamp.
- `attempts`: a SHA-256 hash of the sign-up IP with a secret salt, and a time.
  Rows older than an hour are deleted; raw IPs are never stored. Five sign-up
  attempts per IP per hour are allowed.

## Routes

- `GET /` returns `{"count": N}` (cached for 5 seconds).
- `POST /` with JSON `{name, email, organisation, build, variant}` returns
  `{"ok": true, "count": N}`. The same email twice counts once.
- CORS is allowed only for `https://chipin.space`, `https://www.chipin.space`
  and `https://amgrobelnik.github.io`.
- `GET /admin/export` and `DELETE /admin/signup?email=...` need the header
  `Authorization: Bearer <ADMIN_TOKEN>`; anything else answers 404.

There is no public way to list or read sign-ups.

## Export the list

Simplest: Cloudflare dashboard, Storage & Databases, D1, `sota-hack-waitlist`,
Console: `SELECT * FROM signups;` (or `npx wrangler d1 export sota-hack-waitlist --remote --output waitlist.sql`).

The admin token is a Worker secret that nobody holds. To use the admin route,
set your own first (it asks for the value): `npx wrangler secret put ADMIN_TOKEN`.

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://sota-hack-waitlist.amgrobelnik.workers.dev/admin/export > waitlist.csv
```

## Delete one person

```bash
curl -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" \
  "https://sota-hack-waitlist.amgrobelnik.workers.dev/admin/signup?email=person@example.com"
```

Or in the D1 console: `DELETE FROM signups WHERE email = 'person@example.com';`

## Deploy

```bash
npx wrangler d1 create sota-hack-waitlist   # put the id into wrangler.toml
npx wrangler d1 execute sota-hack-waitlist --remote --file schema.sql
npx wrangler secret put ADMIN_TOKEN
npx wrangler secret put IP_SALT
npx wrangler deploy
```

## Remove the whole service

```bash
npx wrangler delete sota-hack-waitlist
npx wrangler d1 delete sota-hack-waitlist
```

Then point `assets/waitlist-config.js` back to an empty endpoint.
