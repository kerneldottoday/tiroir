# Security

## Reporting a flaw

Please do not open a public issue. Use GitHub's private report instead:
**Security → Report a vulnerability** on this repository. You will get an answer within a week.

Useful details: version (`tiroir version`), how Tiroir is exposed (direct, reverse proxy, tunnel), steps to reproduce.

## What Tiroir protects

- The admin password is never stored in clear: `password.json` holds a scrypt hash and a version number.
  Changing the password ends every admin session.
- Sessions are stored as SHA-256 hashes of the cookie. The cookie is HttpOnly and SameSite=Strict, and Secure over https.
- Login: five attempts per address (per /64 for IPv6) every fifteen minutes, one hundred in total, and at most two scrypt checks at once.
- Every write needs the `X-Tiroir` header and a same-origin request (`Sec-Fetch-Site`).
- Strict Content-Security-Policy: no inline script, no third-party resource, fonts are bundled.
- Proxy headers (`X-Forwarded-For`, `CF-Connecting-IP`, `X-Forwarded-Proto`) are ignored unless the request
  comes from a proxy listed in `TIROIR_TRUST_PROXY`.
- Agent files are read-only, symlinks are refused, each file is capped at 200 kB (6 kB read), and the text is displayed, never executed.
- Guests can never delete, and the server checks every right; the interface only hides what you cannot do.

## Known limits

- One admin, one password. Guests come through invitation links.
- Invitation tokens are stored in clear in `invites.json` so the admin can copy a link again. Protect the data folder (it is created with `0600` files).
- Tiroir speaks plain HTTP. Put it behind HTTPS before exposing it to the internet.
