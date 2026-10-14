// Questions the indexed evaluation corpus can answer, grouped by what they exercise.
export const EXAMPLE_GROUPS: { label: string; hint: string; prompts: string[] }[] = [
  {
    label: "Incidents",
    hint: "root cause from incident reports and postmortems",
    prompts: [
      "Why did payment-service fail after the v2.14.0 deployment?",
      "Why was a rollback recommended instead of increasing the pool size?",
      "What made search-service slow after v7.4.0?",
      "Why were notifications delayed after notification-service v5.1.0?",
    ],
  },
  {
    label: "Code & config",
    hint: "routes to the code-search tool",
    prompts: [
      "Where is OAuth redirect URI validation implemented in auth-service?",
      "Where is incident severity normalized?",
      "How does payment-service space out retries?",
      "Which environment variable controls the notification worker batch size?",
    ],
  },
  {
    label: "Logs",
    hint: "exact identifiers - where keyword search matters",
    prompts: [
      "Which request IDs hit db.pool.exhausted errors in payment-service?",
      "What error did auth-service log when it failed to sign tokens on 2026-10-05?",
    ],
  },
  {
    label: "Docs & runbooks",
    hint: "paraphrased questions - where vector search matters",
    prompts: [
      "How is the database connection pool size calculated?",
      "How do I check when the auth-service signing certificate expires?",
    ],
  },
  {
    label: "Should refuse",
    hint: "nothing indexed answers these - watch the guardrail",
    prompts: ["What is the capital of Australia?", "How do I configure Kafka consumer group rebalancing?"],
  },
];

export const INCIDENT_EXAMPLES: { service: string; severity: string; query: string }[] = [
  { service: "payment-service", severity: "SEV-1", query: "Card payments failing with 503 right after the v2.14.0 deploy" },
  { service: "auth-service", severity: "SEV-1", query: "Logins failing intermittently after the 4.3.0 deployment" },
  { service: "checkout-service", severity: "SEV-2", query: "Checkout requests hanging for up to 60 seconds" },
];
