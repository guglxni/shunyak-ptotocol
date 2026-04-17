export type AgentLiteLLMConfig = {
  enabled: boolean;
  provider: string;
  model: string;
  api_key: string;
  api_base: string;
  api_version: string;
  temperature?: number;
  max_tokens?: number;
};

export const LITELLM_STORAGE_KEY = "shunyak:llm-byok";

const DEFAULT_CONFIG: AgentLiteLLMConfig = {
  enabled: false,
  provider: "openai",
  model: "openai/gpt-4o-mini",
  api_key: "",
  api_base: "",
  api_version: ""
};

function normalizeModelForProvider(provider: string, model: string): string {
  if (provider === "groq" && model.startsWith("groq/")) {
    return model.slice("groq/".length);
  }
  return model;
}

function parseOptionalNumber(value: unknown): number | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return undefined;
  return parsed;
}

export function sanitizeLiteLLMConfig(value: unknown): AgentLiteLLMConfig {
  const raw = (value ?? {}) as Record<string, unknown>;

  const model = typeof raw.model === "string" && raw.model.trim() ? raw.model.trim() : DEFAULT_CONFIG.model;
  const provider =
    typeof raw.provider === "string" && raw.provider.trim()
      ? raw.provider.trim().toLowerCase()
      : model.includes("/")
        ? model.split("/", 1)[0].toLowerCase()
        : DEFAULT_CONFIG.provider;
  const normalizedModel = normalizeModelForProvider(provider, model);

  const temperature = parseOptionalNumber(raw.temperature);
  const maxTokens = parseOptionalNumber(raw.max_tokens);

  return {
    enabled: Boolean(raw.enabled),
    provider,
    model: normalizedModel,
    api_key: typeof raw.api_key === "string" ? raw.api_key.trim() : "",
    api_base: typeof raw.api_base === "string" ? raw.api_base.trim() : "",
    api_version: typeof raw.api_version === "string" ? raw.api_version.trim() : "",
    temperature,
    max_tokens: maxTokens ? Math.trunc(maxTokens) : undefined
  };
}

export function loadLiteLLMConfigFromStorage(): AgentLiteLLMConfig {
  if (typeof window === "undefined") {
    return DEFAULT_CONFIG;
  }
  const raw = window.localStorage.getItem(LITELLM_STORAGE_KEY);
  if (!raw) return DEFAULT_CONFIG;
  try {
    return sanitizeLiteLLMConfig(JSON.parse(raw));
  } catch {
    window.localStorage.removeItem(LITELLM_STORAGE_KEY);
    return DEFAULT_CONFIG;
  }
}

export function saveLiteLLMConfigToStorage(config: AgentLiteLLMConfig): AgentLiteLLMConfig {
  const sanitized = sanitizeLiteLLMConfig(config);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(LITELLM_STORAGE_KEY, JSON.stringify(sanitized));
  }
  return sanitized;
}

export function clearLiteLLMConfigStorage(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(LITELLM_STORAGE_KEY);
  }
}

export function liteLLMConfigSummary(config: AgentLiteLLMConfig): string {
  if (!config.enabled) return "disabled";
  const route = `${config.provider}/${config.model}`;
  return config.api_key ? `${route} (BYOK set)` : `${route} (no key)`;
}
