// OAuth callback handling for auth-service.
import { Request, Response } from "express";
import { exchangeCodeForTokens } from "./tokens";
import { config } from "../config";

export class InvalidRedirectError extends Error {
  constructor(uri: string) {
    super(`redirect URI is not on the allowlist: ${uri}`);
  }
}

/**
 * Exact-match validation of the redirect URI against AUTH_ALLOWED_REDIRECTS.
 * Runs before token exchange so an untrusted redirect never receives a code.
 */
export function validateRedirectUri(uri: string, allowlist: string[]): void {
  let parsed: URL;
  try {
    parsed = new URL(uri);
  } catch {
    throw new InvalidRedirectError(uri);
  }
  const normalized = `${parsed.protocol}//${parsed.host}${parsed.pathname}`;
  if (!allowlist.includes(normalized)) {
    throw new InvalidRedirectError(uri);
  }
}

export async function handleOAuthCallback(req: Request, res: Response) {
  const { code, state, redirect_uri: redirectUri } = req.query as Record<string, string>;
  if (state !== req.session.oauthState) {
    return res.status(400).json({ error: "state mismatch" });
  }
  try {
    validateRedirectUri(redirectUri, config.AUTH_ALLOWED_REDIRECTS);
  } catch (error) {
    if (error instanceof InvalidRedirectError) {
      return res.status(400).json({ error: "invalid_redirect_uri" });
    }
    throw error;
  }
  const tokens = await exchangeCodeForTokens(code, redirectUri);
  return res.redirect(`${redirectUri}#access_token=${tokens.accessToken}`);
}
