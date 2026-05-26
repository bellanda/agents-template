const API_BASE = "/api/v1/agents";

// ── Suggestions ────────────────────────────────────────────────────────────────

export type AgentSuggestionSection = "direct" | "template" | "follow_up";

export interface AgentSuggestionInstant {
	kind: "instant";
	label: string;
	prompt: string;
	section: Exclude<AgentSuggestionSection, "template">;
	emoji: string;
}

export interface AgentSuggestionTemplate {
	kind: "template";
	label: string;
	template: string;
	placeholders: string[];
	section: "template" | "follow_up";
	emoji: string;
}

export type AgentSuggestion = AgentSuggestionInstant | AgentSuggestionTemplate;

const SUGGESTION_LABEL_MAX_CHARS = 56;

function parseInstantSection(raw: unknown): Exclude<AgentSuggestionSection, "template"> {
	return raw === "follow_up" ? "follow_up" : "direct";
}

function parseTemplateSection(raw: unknown): "template" | "follow_up" {
	return raw === "follow_up" ? "follow_up" : "template";
}

export function normalizeAgentSuggestions(raw: unknown): AgentSuggestion[] {
	if (!Array.isArray(raw)) return [];
	const out: AgentSuggestion[] = [];
	for (const item of raw) {
		if (typeof item === "string") {
			const label =
				item.length <= SUGGESTION_LABEL_MAX_CHARS
					? item
					: `${item.slice(0, SUGGESTION_LABEL_MAX_CHARS - 3)}...`;
			out.push({
				kind: "instant",
				label,
				prompt: item,
				section: "direct",
				emoji: "",
			});
			continue;
		}
		if (item && typeof item === "object" && "kind" in item) {
			const kind = (item as { kind: unknown }).kind;
			if (kind === "instant" && "label" in item && "prompt" in item) {
				out.push({
					kind: "instant",
					label: String((item as { label: unknown }).label),
					prompt: String((item as { prompt: unknown }).prompt),
					section: parseInstantSection((item as { section?: unknown }).section),
					emoji: String((item as { emoji?: unknown }).emoji ?? ""),
				});
				continue;
			}
			if (
				kind === "template" &&
				"label" in item &&
				"template" in item &&
				"placeholders" in item
			) {
				const placeholdersRaw = (item as { placeholders: unknown }).placeholders;
				const placeholders = Array.isArray(placeholdersRaw)
					? placeholdersRaw.map((p) => String(p))
					: [];
				out.push({
					kind: "template",
					label: String((item as { label: unknown }).label),
					template: String((item as { template: unknown }).template),
					placeholders,
					section: parseTemplateSection((item as { section?: unknown }).section),
					emoji: String((item as { emoji?: unknown }).emoji ?? ""),
				});
			}
		}
	}
	return out;
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface AgentCapabilities {
	image_input: boolean;
	pdf_input: boolean;
	audio_input: boolean;
	video_input: boolean;
	reasoning: boolean;
}

const DEFAULT_CAPABILITIES: AgentCapabilities = {
	image_input: false,
	pdf_input: false,
	audio_input: false,
	video_input: false,
	reasoning: false,
};

export interface AgentModel {
	id: string;
	name: string;
	description: string;
	save_to_db: boolean;
	suggestions: AgentSuggestion[];
	capabilities: AgentCapabilities;
	provider?: string;
	providers?: string[];
	chef?: string;
	chefSlug?: string;
}

export interface Thread {
	thread_id: string;
	agent_id: string;
	preview: string;
	message_count: number;
	created_at: string;
}

export interface ThreadMessagePart {
	type: string;
	text?: string;
	reasoning?: string;
	url?: string;
	mediaType?: string;
	filename?: string;
	toolName?: string;
	toolCallId?: string;
	state?: string;
	input?: unknown;
	output?: unknown;
	errorText?: string;
}

export interface ThreadMessage {
	role: string;
	content: string;
	id?: string;
	reasoning?: string;
	parts?: ThreadMessagePart[];
}

// ── API Functions ──────────────────────────────────────────────────────────────

/**
 * Identity header consumed by the backend `get_auth_context` seam.
 * Replace `useUserId` with real auth and this carries the resolved id; with a
 * real token backend, send `Authorization: Bearer` here instead.
 */
function userHeaders(userId?: string): Record<string, string> {
	return userId ? { "X-User-Id": userId } : {};
}

interface RawAgentModel
	extends Omit<AgentModel, "suggestions" | "capabilities"> {
	suggestions?: unknown;
	capabilities?: Partial<AgentCapabilities>;
}

export async function fetchAgents(): Promise<AgentModel[]> {
	const res = await fetch(`${API_BASE}`);
	if (!res.ok) throw new Error("Failed to fetch agents");
	const data = (await res.json()) as { data?: RawAgentModel[] };
	const rows = data.data ?? [];
	return rows.map((m) => ({
		...m,
		suggestions: normalizeAgentSuggestions(m.suggestions),
		capabilities: { ...DEFAULT_CAPABILITIES, ...(m.capabilities ?? {}) },
	}));
}

export async function fetchThreads(agentId?: string, userId?: string): Promise<Thread[]> {
	const params = new URLSearchParams();
	if (agentId) params.append("agent_id", agentId);
	const queryString = params.toString();
	const res = await fetch(`${API_BASE}/threads${queryString ? `?${queryString}` : ""}`, {
		headers: userHeaders(userId),
	});
	if (!res.ok) throw new Error("Failed to fetch threads");
	const data = await res.json();
	return data.threads ?? [];
}

export async function fetchThreadMessages(
	threadId: string,
	userId?: string
): Promise<ThreadMessage[]> {
	const res = await fetch(`${API_BASE}/threads/${threadId}`, {
		headers: userHeaders(userId),
	});
	if (!res.ok) throw new Error("Failed to fetch thread messages");
	const data = await res.json();
	return data.messages ?? [];
}

/** Prefetch and cache thread messages. Call on sidebar thread hover for instant switch on click. */
export async function prefetchThreadMessages(threadId: string, userId?: string): Promise<void> {
	const { getCachedMessages, cacheThreadMessages } = await import("./thread-messages-cache");
	if (getCachedMessages(threadId)) return;
	const data = await fetchThreadMessages(threadId, userId);
	cacheThreadMessages(threadId, data);
}

export async function deleteThread(threadId: string, userId?: string): Promise<void> {
	const res = await fetch(`${API_BASE}/threads/${threadId}`, {
		method: "DELETE",
		headers: userHeaders(userId),
	});
	if (!res.ok) throw new Error("Failed to delete thread");
}

// ── Uploads ────────────────────────────────────────────────────────────────────

const UPLOADS_BASE_URL = "/api/v1/uploads";

export type UploadErrorCode =
	| "image_not_supported"
	| "audio_not_supported"
	| "video_not_supported"
	| "too_large"
	| "unsupported_type"
	| "model_not_found"
	| "thread_files_full"
	| "thread_images_full"
	| "thread_documents_full"
	| "user_files_full"
	| "user_storage_full"
	| "network";

export interface UploadedFile {
	url: string;
	filename: string;
	mediaType: string;
	size: number;
}

export class UploadError extends Error {
	readonly code: UploadErrorCode;
	readonly filename: string;
	readonly mediaType: string;
	readonly maxBytes?: number;
	readonly modelId?: string;

	constructor(opts: {
		code: UploadErrorCode;
		filename: string;
		mediaType: string;
		message: string;
		maxBytes?: number;
		modelId?: string;
	}) {
		super(opts.message);
		this.name = "UploadError";
		this.code = opts.code;
		this.filename = opts.filename;
		this.mediaType = opts.mediaType;
		this.maxBytes = opts.maxBytes;
		this.modelId = opts.modelId;
	}
}

interface BackendErrorDetail {
	code?: string;
	filename?: string;
	media_type?: string;
	max_bytes?: number;
	model_id?: string;
	limit?: number;
	current?: number;
	incoming?: number;
}

const KNOWN_UPLOAD_CODES: ReadonlySet<UploadErrorCode> = new Set([
	"image_not_supported",
	"audio_not_supported",
	"video_not_supported",
	"too_large",
	"thread_files_full",
	"thread_images_full",
	"thread_documents_full",
	"user_files_full",
	"user_storage_full",
] as const);

function normalizeUploadCode(raw: unknown): UploadErrorCode | null {
	if (typeof raw !== "string") return null;
	if (KNOWN_UPLOAD_CODES.has(raw as UploadErrorCode)) {
		return raw as UploadErrorCode;
	}
	return null;
}

function defaultUploadMessage(
	code: UploadErrorCode,
	detail: BackendErrorDetail,
	fallbackName: string
): string {
	const filename = detail.filename || fallbackName;
	if (code === "image_not_supported") {
		return `This model does not accept images (${filename}).`;
	}
	if (code === "audio_not_supported") {
		return `This model does not accept audio (${filename}).`;
	}
	if (code === "video_not_supported") {
		return `This model does not accept video (${filename}).`;
	}
	if (code === "too_large") {
		const limit = detail.max_bytes
			? `${Math.round(detail.max_bytes / (1024 * 1024))} MB`
			: "limit";
		return `${filename} exceeds the maximum size (${limit}).`;
	}
	if (code === "thread_files_full") {
		return `Per-conversation file limit reached (${detail.limit ?? 10}).`;
	}
	if (code === "thread_images_full") {
		return `Per-conversation image limit reached (${detail.limit ?? 6}).`;
	}
	if (code === "thread_documents_full") {
		return `Per-conversation document limit reached (${detail.limit ?? 8}).`;
	}
	if (code === "user_files_full") {
		return `Total file limit reached (${detail.limit ?? 200}).`;
	}
	if (code === "user_storage_full") {
		const limitMb = detail.limit ? `${Math.round(detail.limit / (1024 * 1024))} MB` : "limit";
		return `Storage quota exhausted (${limitMb}).`;
	}
	return `Could not upload ${filename}.`;
}

export async function uploadFile(
	file: File,
	modelId?: string,
	userId?: string,
	sessionId?: string
): Promise<UploadedFile> {
	const formData = new FormData();
	formData.append("file", file);

	// Owner vem da sessão (header X-User-Id / Bearer), nunca de param do cliente.
	const params = new URLSearchParams();
	if (modelId) params.set("model_id", modelId);
	if (sessionId) params.set("session_id", sessionId);
	const queryString = params.toString();
	const url = queryString ? `${UPLOADS_BASE_URL}?${queryString}` : UPLOADS_BASE_URL;

	let response: Response;
	try {
		response = await fetch(url, {
			method: "POST",
			body: formData,
			headers: userHeaders(userId),
		});
	} catch (cause) {
		throw new UploadError({
			code: "network",
			filename: file.name,
			mediaType: file.type || "application/octet-stream",
			message: cause instanceof Error ? cause.message : "Network error while uploading file.",
		});
	}

	if (!response.ok) {
		let detail: BackendErrorDetail | string | undefined;
		try {
			const body = (await response.json()) as { detail?: BackendErrorDetail | string };
			detail = body.detail;
		} catch {
			detail = undefined;
		}

		if (detail && typeof detail === "object") {
			const code =
				normalizeUploadCode(detail.code) ??
				(response.status === 413 ? "too_large" : "unsupported_type");
			throw new UploadError({
				code,
				filename: detail.filename || file.name,
				mediaType: detail.media_type || file.type || "application/octet-stream",
				maxBytes: detail.max_bytes,
				modelId: detail.model_id || modelId,
				message: defaultUploadMessage(code, detail, file.name),
			});
		}

		const fallbackCode: UploadErrorCode =
			response.status === 413
				? "too_large"
				: response.status === 415
					? "unsupported_type"
					: "network";
		throw new UploadError({
			code: fallbackCode,
			filename: file.name,
			mediaType: file.type || "application/octet-stream",
			message:
				typeof detail === "string"
					? detail
					: `Upload failed (HTTP ${response.status}).`,
		});
	}

	const data = (await response.json()) as {
		url: string;
		filename: string;
		media_type: string;
		size: number;
	};
	return {
		url: data.url,
		filename: data.filename,
		mediaType: data.media_type,
		size: data.size,
	};
}
