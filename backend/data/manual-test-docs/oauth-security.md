# OAuth Redirect Security

The OAuth callback handler validates the redirect URI before exchanging the
authorization code for tokens. Only redirect URIs registered for the client are
accepted.

An unregistered redirect URI is rejected and the token exchange is not attempted.
Validation failures should be logged with the client identifier and request ID,
but never with the authorization code or client secret.
