# OAuth Login Flow (auth-service)

Service: auth-service

auth-service implements the OAuth 2.0 authorization-code flow for all first-party
web and mobile clients.

## Callback handling

The provider redirects the browser to `GET /oauth/callback?code=...&state=...`.
The callback handler lives in `src/auth/redirect.ts` (`handleOAuthCallback`).

Before the authorization code is exchanged for tokens, the redirect URI is
validated against the allowlist in the `AUTH_ALLOWED_REDIRECTS` setting. The match
is exact: scheme, host, port and path must be identical and wildcards are not
supported. A redirect URI that is not on the allowlist is rejected with HTTP 400
and the token exchange never happens. This prevents open-redirect attacks that
would leak the authorization code to an attacker-controlled site.

The `state` parameter is compared with the value stored in the session to block
CSRF on the callback.

## Token signing

Access tokens are JWTs signed with RS256. The signing certificate is loaded at
startup from `/etc/auth/signing.pem`. Certificates are valid for 90 days and must
be rotated before expiry; see runbooks/certificate-rotation.md.
