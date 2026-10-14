# Runbook: Rotate the auth-service Signing Certificate

The auth-service JWT signing certificate is valid for 90 days.

1. Check the current expiry: `openssl x509 -enddate -noout -in /etc/auth/signing.pem`.
2. Generate a new key pair and certificate from the internal CA.
3. Publish the new public key to the JWKS endpoint first, so tokens signed with the
   new key verify before any instance starts using it.
4. Roll out the new certificate to auth-service.
5. Keep the old public key in JWKS for 24 hours until existing tokens expire.

The deployment pipeline must fail if the certificate expires in fewer than 30 days.
This check was added after INC-2026-2017, where v4.3.0 shipped an expired certificate.
