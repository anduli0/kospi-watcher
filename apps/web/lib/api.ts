/**
 * Typed client for the KOSPI-WATCHER API.
 *
 * The base URL is injected at build time from NEXT_PUBLIC_API_BASE_URL
 * (see next.config.mjs). All calls are analysis/risk only — there is no
 * order-submission endpoint in this phase.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// --- Response types (mirror src/kospi_watcher/api/schemas/responses.py) ---

export interface HealthResponse {
  status: string;
  app: string;
  version: string;
  database: { connected: boolean; backend: string };
  redis: { backend: string; connected: boolean; detail: string };
  trading_mode: string;
  live_trading_enabled: boolean;
  auto_execution_enabled: boolean;
}

export interface SystemStatusResponse {
  app: string;
  version: string;
  environment: string;
  server_time_utc: string;
  server_time_kst: string;
  trading_mode: string;
  feature_flags: Record<string, boolean>;
  data_sources: { name: string; status: string }[];
  agent_count: number;
}

export interface AgentInfo {
  name: string;
  version: string;
  category: string;
  summary: string;
  enabled: boolean;
}

export interface AgentListResponse {
  count: number;
  agents: AgentInfo[];
}

export interface AgentRun {
  run_id: string;
  agent_name: string;
  agent_version: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  model_name: string;
  prompt_version: string;
  findings: AgentFinding[];
  error: string | null;
}

export interface AgentFinding {
  schema_version: string;
  agent_name: string;
  horizon: string;
  direction: string;
  impact: string;
  confidence: number;
  thesis: string;
  affected_sectors: string[];
  affected_symbols: string[];
  invalidation_conditions: string[];
  data_quality: string;
}

export interface RiskCheckResult {
  code: string;
  passed: boolean;
  detail: string;
}

export interface RiskDecision {
  decision_id: string;
  proposal_id: string;
  status: "APPROVED" | "REJECTED";
  created_at: string;
  checks: RiskCheckResult[];
  failed_checks: string[];
  reason: string;
  requires_human: boolean;
}

export interface AuditLogEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  created_at: string;
}

export interface AuditLogPage {
  count: number;
  limit: number;
  offset: number;
  items: AuditLogEntry[];
}

export interface OrderProposalInput {
  symbol: string;
  instrument_type: string;
  side: string;
  order_type: string;
  quantity: number;
  limit_price?: string | null;
  strategy_id: string;
  strategy_version?: string;
  idempotency_key: string;
}

export interface MarketQuote {
  symbol: string;
  price: string;
  currency: string;
  as_of: string;
  source: string;
  stale: boolean;
}

export type Direction = "BULLISH" | "BEARISH" | "NEUTRAL";
export type StanceLabel = "OVERWEIGHT" | "NEUTRAL" | "UNDERWEIGHT" | "AVOID";

export interface DeskView {
  desk: string;
  title: string;
  lean: Direction;
  conviction: number;
  weight: number;
  score: number;
  member_count: number;
  responded: number;
  summary: string;
  top_drivers: string[];
}

export interface InstrumentStance {
  symbol: string;
  name: string;
  kind: string;
  label: StanceLabel;
  rationale: string;
  risk_note: string | null;
}

export interface Scenario {
  name: string;
  probability: number;
  thesis: string;
  triggers: string[];
}

export interface AgentPosition {
  agent: string;
  is_lead: boolean;
  direction: Direction;
  confidence: number;
  note: string;
}

export interface DeskDeliberation {
  desk: string;
  title: string;
  consensus: Direction;
  agreement: number;
  positions: AgentPosition[];
  dissent: string[];
  lead_note: string;
}

export interface ChiefDeliberation {
  overall: Direction;
  aligned_desks: string[];
  conflicted_desks: string[];
  note: string;
}

export interface Deliberation {
  desks: DeskDeliberation[];
  chief: ChiefDeliberation;
}

export interface MarketPrediction {
  prediction_id: string;
  as_of: string;
  subject: string;
  horizon: string;
  horizon_label: string;
  regime: string;
  direction: Direction;
  confidence: number;
  data_quality: string;
  headline: string;
  brief: string;
  desk_views: DeskView[];
  deliberation: Deliberation | null;
  instrument_stances: InstrumentStance[];
  scenarios: Scenario[];
  news_refs: string[];
  generated_by: string;
  agent_count: number;
}

export interface NewsItem {
  id: string;
  title: string;
  url: string;
  source: string;
  topic: string;
  published_at: string;
  date_kst: string;
}

export interface NewsListResponse {
  count: number;
  date: string | null;
  items: NewsItem[];
}

export interface NewsDateCount {
  date: string;
  count: number;
}

export interface NewsDatesResponse {
  dates: NewsDateCount[];
}

export interface ScrapeResponse {
  fetched: number;
  added: number;
  pruned: number;
  topics: string[];
}

export interface BriefStance {
  symbol: string;
  name: string;
  kind: string;
  label: StanceLabel;
  risk_note: string | null;
}

export interface BriefResponse {
  as_of: string;
  generated_by: string;
  agent_count: number;
  direction: Direction;
  confidence: number;
  regime: string;
  headline: string;
  brief: string;
  stances: BriefStance[];
}

export interface OrgDeskInfo {
  key: string;
  title: string;
  tier: string;
  weight: number;
  lead: string;
  members: string[];
}

export interface OrgResponse {
  desks: OrgDeskInfo[];
  tiers: string[];
  agent_count: number;
}

export interface MarketQuotesResponse {
  provider: string;
  count: number;
  quotes: MarketQuote[];
}

export interface FillResponse {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  price: string;
  liquidity: string;
  created_at: string;
}

export interface OrderResponse {
  id: string;
  symbol: string;
  side: string;
  order_type: string;
  quantity: number;
  limit_price: string | null;
  status: string;
  broker_order_id: string | null;
  trading_mode: string;
  filled_quantity: number;
  avg_fill_price: string | null;
  created_at: string;
}

export interface OrderListResponse {
  count: number;
  orders: OrderResponse[];
}

export interface PositionResponse {
  symbol: string;
  quantity: number;
  avg_cost: string;
  realized_pnl: string;
  mark_price: string | null;
  market_value: string | null;
  unrealized_pnl: string | null;
}

export interface AccountResponse {
  account: string;
  as_of: string;
  realized_pnl: string;
  unrealized_pnl: string;
  total_pnl: string;
  gross_exposure: string;
  position_count: number;
  positions: PositionResponse[];
}

export interface SubmitOrderResponse {
  order_id: string;
  status: string;
  message: string;
  reference_price: string | null;
  decision: RiskDecision;
  fill: FillResponse | null;
  position: PositionResponse | null;
}

// --- Fetch helper ---

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch (cause) {
    throw new ApiError(0, `API unreachable at ${API_BASE_URL} (${String(cause)})`);
  }
  if (!resp.ok) {
    const detail = await resp.text().catch(() => resp.statusText);
    throw new ApiError(resp.status, detail || resp.statusText);
  }
  return (await resp.json()) as T;
}

// --- Endpoints (7) ---

export const api = {
  health: () => request<HealthResponse>("/health"),
  systemStatus: () => request<SystemStatusResponse>("/api/v1/system/status"),
  listAgents: () => request<AgentListResponse>("/api/v1/agents"),
  mockRun: (agentName: string, universe: string[] = []) =>
    request<AgentRun>("/api/v1/agents/mock-run", {
      method: "POST",
      body: JSON.stringify({ agent_name: agentName, universe }),
    }),
  runAgent: (agentName: string, universe: string[] = []) =>
    request<AgentRun>("/api/v1/agents/run", {
      method: "POST",
      body: JSON.stringify({ agent_name: agentName, universe }),
    }),
  marketQuotes: (symbols?: string[]) =>
    request<MarketQuotesResponse>(
      "/api/v1/market/quotes" + (symbols?.length ? `?symbols=${symbols.join(",")}` : ""),
    ),
  submitOrder: (proposal: OrderProposalInput, marketOpen = true, lastPrice?: string) =>
    request<SubmitOrderResponse>("/api/v1/orders", {
      method: "POST",
      body: JSON.stringify({
        proposal,
        market_open: marketOpen,
        last_price: lastPrice ?? null,
      }),
    }),
  listOrders: (limit = 50) => request<OrderListResponse>(`/api/v1/orders?limit=${limit}`),
  positions: () => request<PositionResponse[]>("/api/v1/positions"),
  account: () => request<AccountResponse>("/api/v1/account"),
  runPrediction: (universe: string[] = []) =>
    request<MarketPrediction>("/api/v1/prediction/run", {
      method: "POST",
      body: JSON.stringify({ agent_name: "synthesis", universe }),
    }),
  latestPrediction: () => request<MarketPrediction>("/api/v1/prediction/latest"),
  brief: () => request<BriefResponse>("/api/v1/brief"),
  agentsOrg: () => request<OrgResponse>("/api/v1/agents/org"),
  news: (date?: string, limit = 60) =>
    request<NewsListResponse>(
      `/api/v1/news?limit=${limit}` + (date ? `&date=${date}` : ""),
    ),
  newsDates: () => request<NewsDatesResponse>("/api/v1/news/dates"),
  scrapeNews: () => request<ScrapeResponse>("/api/v1/news/scrape", { method: "POST" }),
  validateProposal: (proposal: OrderProposalInput) =>
    request<{ valid: boolean; proposal_id: string; detail: string }>(
      "/api/v1/order-proposals/validate",
      { method: "POST", body: JSON.stringify(proposal) },
    ),
  evaluateRisk: (proposal: OrderProposalInput, marketOpen: boolean, lastPrice?: string) =>
    request<RiskDecision>("/api/v1/risk/evaluate", {
      method: "POST",
      body: JSON.stringify({
        proposal,
        market_open: marketOpen,
        last_price: lastPrice ?? null,
      }),
    }),
  auditLogs: (limit = 25, offset = 0) =>
    request<AuditLogPage>(`/api/v1/audit-logs?limit=${limit}&offset=${offset}`),
};
