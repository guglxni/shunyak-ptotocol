import { createEventStream } from "./sse";
import { sanitizeLiteLLMConfig, type AgentLiteLLMConfig } from "./llm";

export type ConsentRegisterPayload = {
  user_id: string;
  claim_type: "age_over_18" | "indian_citizen";
  enterprise_pubkey: string;
  expiry_days?: number;
  identity_provider?: "digilocker";
  digilocker_request_id?: string;
  digilocker_redirect_url?: string;
  zk_backend?: "algoplonk";
  algoplonk_proof_hex?: string;
  algoplonk_public_inputs_hex?: string;
};

export type ConsentRegisterResponse = {
  ok: boolean;
  status?: "pending_digilocker_consent" | "consent_registered";
  txid?: string;
  explorer_url?: string;
  proof?: string;
  claim_hash?: string;
  user_pubkey?: string;
  enterprise_pubkey?: string;
  expires_at?: number;
  consent_token?: string;
  identity_provider?: "digilocker";
  zk_backend?: "algoplonk";
  zk_verification_mode?: string;
  digilocker?: {
    request_id?: string | null;
    auth_url?: string | null;
    status?: string | null;
    scope?: string[];
    aadhaar_masked_number?: string | null;
  };
  aadhaar?: {
    generated_at?: string | null;
    trace_id?: string | null;
  };
  algoplonk?: {
    proof_chunk_count?: number;
    public_input_chunk_count?: number;
    onchain_verification?: Record<string, unknown> | null;
    onchain_error?: string | null;
    autofilled?: boolean;
    onchain_required?: boolean;
    simulate_only?: boolean;
    verify_app_id?: number | null;
    verify_method?: string;
  };
  tx_mode?: string;
  consent_source?: string;
  confirmed_round?: number | null;
  fallback_reason?: string | null;
  steps: string[];
};

export type ConsentRevokePayload = {
  user_pubkey: string;
  enterprise_pubkey?: string;
};

export type ConsentRevokeResponse = {
  ok: boolean;
  status?: "consent_revoked";
  txid?: string;
  explorer_url?: string;
  confirmed_round?: number;
  local_record_removed?: boolean;
  box_status?: string;
};

export type AgentExecutePayload = {
  prompt: string;
  user_pubkey: string;
  enterprise_pubkey: string;
  amount_microalgo?: number;
  consent_token?: string;
  operator_token?: string;
  llm_config?: AgentLiteLLMConfig;
};

export type AgentEvent = {
  kind: "info" | "success" | "error";
  phase: string;
  message: string;
};

export type AgentExecuteResponse = {
  ok: boolean;
  session_id: string;
  status: "blocked" | "authorized";
  outcome_message: string;
  error_code?: string;
  llm_error?: {
    code: string;
    detail: string;
    hint?: string | null;
    retryable?: boolean;
    provider?: string;
    model?: string;
  };
  events: AgentEvent[];
  settlement?: {
    txid: string;
    confirmed_round: number;
    explorer_url: string;
    mode?: string;
    receiver?: string;
    asset_id?: number;
    fallback_reason?: string | null;
  };
  audit_entries: Array<Record<string, unknown>>;
};

export type AgentStreamEnvelope =
  | {
      type: "event";
      event: AgentEvent;
    }
  | {
      type: "final";
      result: AgentExecuteResponse;
    }
  | {
      type: "error";
      error: string;
    };

type AgentStreamTicketResponse = {
  ok: boolean;
  stream_token?: string;
  expires_at?: number;
  ttl_seconds?: number;
};

export type AuditLogResponse = {
  ok: boolean;
  items: Array<Record<string, unknown>>;
};

export type AlgorandShowcaseResponse = {
  ok: boolean;
  sdk_snapshot: Record<string, unknown>;
  algokit: {
    runtime?: "serverless" | "local";
    cli_expected?: boolean;
    cli_status?: "available" | "unavailable" | "not_applicable";
    cli_available: boolean;
    cli_version: string | null;
    cli_path?: string | null;
    cli_reason?: string | null;
    utils_available: boolean;
    utils_version: string | null;
  };
  sender_account: {
    configured: boolean;
    address: string | null;
    balance_microalgo: number | null;
    warning_threshold_microalgo: number;
    low_balance_warning: boolean;
    warning_message: string | null;
  };
  consent_engine?: {
    source_mode: string;
    app_id: number | null;
  };
  identity_engine?: {
    provider: string;
    digilocker_configured: boolean;
  };
  zk_engine?: {
    backend: string;
    verify_app_id: number | null;
    verify_method: string;
    onchain_required: boolean;
    simulate_only: boolean;
  };
  settlement_engine?: {
    asset_id: number | null;
    asset_mode: "asa" | "algo";
  };
  llm_engine?: {
    enabled: boolean;
    provider: string | null;
    model: string | null;
    api_base: string | null;
    api_version: string | null;
    api_key_configured: boolean;
    temperature?: number | null;
    max_tokens?: number | null;
    litellm_installed?: boolean;
    litellm_version?: string | null;
    error?: string;
  };
};

export type DemoContextResponse = {
  ok: boolean;
  generated_at: number;
  requirements: {
    operator_auth_required: boolean;
    execution_token_required: boolean;
    app_id: number | null;
    identity_provider: string;
    zk_backend: string;
    llm_byok_supported?: boolean;
  };
  llm_defaults?: {
    enabled: boolean;
    provider: string | null;
    model: string | null;
    api_base: string | null;
    api_version: string | null;
    api_key_configured: boolean;
    temperature?: number | null;
    max_tokens?: number | null;
  };
  consent: {
    user_id: string;
    claim_type: "age_over_18" | "indian_citizen";
    enterprise_pubkey: string;
    identity_provider: string;
    zk_backend: string;
    digilocker_redirect_url: string;
    algoplonk_autofill_enabled: boolean;
  };
  blocked: {
    user_id: string;
    user_pubkey: string;
    enterprise_pubkey: string;
    prompt: string;
    consent_token: string | null;
    operator_token: string | null;
    ready: boolean;
    reason: string;
  };
  authorized: {
    user_id: string;
    user_pubkey: string;
    enterprise_pubkey: string;
    prompt: string;
    consent_token: string | null;
    operator_token: string | null;
    onchain_valid: boolean;
    onchain_reason: string;
    ready: boolean;
    reason: string;
  };
  token_warnings: string[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) {
    throw new Error("Empty response from API");
  }

  const payload = JSON.parse(text) as T & { error?: string; detail?: string };
  if (!response.ok) {
    throw new Error(payload.error || payload.detail || text);
  }

  return payload;
}

function buildAgentHeaders(payload: AgentExecutePayload): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
  };

  if (payload.operator_token) {
    headers["X-Shunyak-Operator-Token"] = payload.operator_token;
  }

  return headers;
}

export async function registerConsent(
  payload: ConsentRegisterPayload
): Promise<ConsentRegisterResponse> {
  const response = await fetch(`${API_BASE}/api/consent/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  return parseJson<ConsentRegisterResponse>(response);
}

export async function revokeConsent(
  payload: ConsentRevokePayload
): Promise<ConsentRevokeResponse> {
  const response = await fetch(`${API_BASE}/api/consent/revoke`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  return parseJson<ConsentRevokeResponse>(response);
}

export async function executeAgent(
  payload: AgentExecutePayload
): Promise<AgentExecuteResponse> {
  const response = await fetch(`${API_BASE}/api/agent/execute`, {
    method: "POST",
    headers: buildAgentHeaders(payload),
    body: JSON.stringify(payload),
    cache: "no-store"
  });

  return parseJson<AgentExecuteResponse>(response);
}

export async function openAgentEventStream(
  payload: AgentExecutePayload,
  onEnvelope: (envelope: AgentStreamEnvelope) => void,
  onError?: (error: Event) => void
): Promise<EventSource> {
  const streamInitPayload = {
    prompt: payload.prompt,
    user_pubkey: payload.user_pubkey,
    enterprise_pubkey: payload.enterprise_pubkey,
    amount_microalgo: payload.amount_microalgo ?? 1_000_000,
    consent_token: payload.consent_token,
    llm_config: payload.llm_config
  };

  const initResponse = await fetch(`${API_BASE}/api/agent/stream`, {
    method: "POST",
    headers: buildAgentHeaders(payload),
    body: JSON.stringify(streamInitPayload),
    cache: "no-store"
  });

  const initPayload = await parseJson<AgentStreamTicketResponse>(initResponse);
  if (!initPayload.stream_token) {
    throw new Error("Stream initialization did not return a stream token");
  }

  return createEventStream<AgentStreamEnvelope>(
    `${API_BASE}/api/agent/stream?stream_token=${encodeURIComponent(initPayload.stream_token)}`,
    (message) => {
      onEnvelope(message.data);
    },
    onError
  );
}

export async function fetchAuditLog(limit = 15): Promise<AuditLogResponse> {
  const response = await fetch(`${API_BASE}/api/audit/log?limit=${limit}`, {
    cache: "no-store"
  });

  return parseJson<AuditLogResponse>(response);
}

export async function fetchAlgorandShowcase(
  llmConfig?: AgentLiteLLMConfig
): Promise<AlgorandShowcaseResponse> {
  if (!llmConfig) {
    const response = await fetch(`${API_BASE}/api/algorand/showcase`, {
      cache: "no-store"
    });

    return parseJson<AlgorandShowcaseResponse>(response);
  }

  const sanitized = sanitizeLiteLLMConfig(llmConfig);
  const llmApiKeyConfigured = Boolean(sanitized.api_key);
  const { api_key: _apiKey, ...publicConfig } = sanitized;

  const response = await fetch(`${API_BASE}/api/algorand/showcase`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      llm_config: publicConfig,
      llm_api_key_configured: llmApiKeyConfigured
    }),
    cache: "no-store"
  });

  return parseJson<AlgorandShowcaseResponse>(response);
}

export async function fetchDemoContext(): Promise<DemoContextResponse> {
  const response = await fetch(`${API_BASE}/api/demo/context`, {
    cache: "no-store"
  });

  return parseJson<DemoContextResponse>(response);
}
