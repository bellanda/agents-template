import {
	PromptInput,
	PromptInputActionAddAttachments,
	PromptInputActionMenu,
	PromptInputActionMenuContent,
	PromptInputActionMenuTrigger,
	PromptInputBody,
	PromptInputFooter,
	PromptInputHeader,
	PromptInputSubmit,
	PromptInputTextarea,
	PromptInputTools,
	usePromptInputAttachments,
	type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";
import { ChatDragDropOverlay } from "@/components/chat/ChatDragDropOverlay";
import { ChatModelPicker } from "@/components/chat/ChatModelPicker";
import type { ChatRejectionEntry } from "@/components/chat/rejection-types";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { AgentModel } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ChatStatus } from "ai";
import { FileIcon, FileSpreadsheetIcon, FileTextIcon, FileTypeIcon, XIcon } from "lucide-react";
import { useCallback, useMemo } from "react";

function buildAcceptAttribute(caps: AgentModel["capabilities"] | undefined): string | undefined {
	if (!caps) return undefined;
	const accept: string[] = [
		// Documents always pass (extracted via MarkItDown on the backend).
		".pdf",
		".docx",
		".doc",
		".xlsx",
		".xls",
		".csv",
		".txt",
		".md",
		".html",
		".pptx",
	];
	if (caps.image_input) accept.push("image/*");
	if (caps.audio_input) accept.push("audio/*");
	if (caps.video_input) accept.push("video/*");
	return accept.join(",");
}

interface AttachmentTypeStyle {
	Icon: typeof FileTextIcon;
	badge: string;
	iconColor: string;
	label: string;
}

function attachmentTypeStyle(filename: string, mediaType: string): AttachmentTypeStyle {
	const name = filename.toLowerCase();
	const mt = mediaType.toLowerCase();
	const ext = name.includes(".") ? name.slice(name.lastIndexOf(".") + 1) : "";

	if (ext === "pdf" || mt === "application/pdf") {
		return {
			Icon: FileTextIcon,
			badge: "bg-red-500/10 dark:bg-red-500/15 border-red-500/30",
			iconColor: "text-red-600 dark:text-red-400",
			label: "PDF",
		};
	}
	if (ext === "doc" || ext === "docx" || mt.includes("wordprocessingml") || mt === "application/msword") {
		return {
			Icon: FileTypeIcon,
			badge: "bg-blue-500/10 dark:bg-blue-500/15 border-blue-500/30",
			iconColor: "text-blue-600 dark:text-blue-400",
			label: ext === "docx" ? "DOCX" : "DOC",
		};
	}
	if (
		ext === "xls" ||
		ext === "xlsx" ||
		ext === "csv" ||
		mt.includes("spreadsheetml") ||
		mt === "application/vnd.ms-excel" ||
		mt === "text/csv"
	) {
		return {
			Icon: FileSpreadsheetIcon,
			badge: "bg-emerald-500/10 dark:bg-emerald-500/15 border-emerald-500/30",
			iconColor: "text-emerald-600 dark:text-emerald-400",
			label: ext.toUpperCase() || "XLS",
		};
	}
	if (ext === "txt" || ext === "md" || mt.startsWith("text/")) {
		return {
			Icon: FileTextIcon,
			badge: "bg-slate-500/10 dark:bg-slate-500/15 border-slate-500/30",
			iconColor: "text-slate-600 dark:text-slate-400",
			label: ext.toUpperCase() || "TXT",
		};
	}
	return {
		Icon: FileIcon,
		badge: "bg-muted/50 border-border",
		iconColor: "text-muted-foreground",
		label: (ext || "FILE").toUpperCase().slice(0, 4),
	};
}

interface AttachmentChipProps {
	filename: string;
	mediaType: string;
	url: string;
	onRemove?: () => void;
}

function ImageAttachmentChip({ filename, url, onRemove }: AttachmentChipProps) {
	return (
		<div className="group relative size-20 overflow-hidden rounded-xl border">
			<img src={url} alt={filename || "Image"} className="size-full object-cover" />
			{onRemove && (
				<button
					type="button"
					onClick={onRemove}
					className="bg-background/85 hover:bg-background absolute right-1 top-1 flex size-5 items-center justify-center rounded-full opacity-0 transition-opacity group-hover:opacity-100"
					aria-label="Remove attachment"
				>
					<XIcon className="size-3" />
				</button>
			)}
		</div>
	);
}

function DocAttachmentChip({ filename, mediaType, onRemove }: AttachmentChipProps) {
	const { Icon, badge, iconColor, label } = attachmentTypeStyle(filename, mediaType);
	return (
		<div
			className={cn(
				"group relative flex w-56 items-center gap-3 rounded-xl border px-3 py-2.5",
				badge
			)}
		>
			<div className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg bg-background/60", iconColor)}>
				<Icon className="size-5" />
			</div>
			<div className="min-w-0 flex-1">
				<p className="truncate text-sm font-medium" title={filename}>
					{filename || "File"}
				</p>
				<p className={cn("truncate text-[11px] font-medium uppercase tracking-wider", iconColor)}>
					{label}
				</p>
			</div>
			{onRemove && (
				<button
					type="button"
					onClick={onRemove}
					className="bg-background/70 hover:bg-background absolute -right-1.5 -top-1.5 flex size-5 items-center justify-center rounded-full border opacity-0 transition-opacity group-hover:opacity-100"
					aria-label="Remove attachment"
				>
					<XIcon className="size-3" />
				</button>
			)}
		</div>
	);
}

function PromptAttachmentsDisplay() {
	const attachments = usePromptInputAttachments();

	const handleRemove = useCallback((id: string) => attachments.remove(id), [attachments]);

	if (attachments.files.length === 0) return null;

	return (
		<div className="flex flex-wrap items-start gap-2">
			{attachments.files.map((attachment) => {
				const filename = attachment.filename || "File";
				const mediaType = attachment.mediaType ?? "application/octet-stream";
				const url = attachment.url || "";
				const onRemove = () => handleRemove(attachment.id);
				if (mediaType.startsWith("image/")) {
					return (
						<ImageAttachmentChip
							key={attachment.id}
							filename={filename}
							mediaType={mediaType}
							url={url}
							onRemove={onRemove}
						/>
					);
				}
				return (
					<DocAttachmentChip
						key={attachment.id}
						filename={filename}
						mediaType={mediaType}
						url={url}
						onRemove={onRemove}
					/>
				);
			})}
		</div>
	);
}

interface ChatComposerProps {
	status: ChatStatus;
	onStop: () => void;
	onSubmit: (message: PromptInputMessage) => void;
	chatError: Error | undefined;
	onClearError: () => void;
	selectedAgent: AgentModel | undefined;
	selectedAgentId: string;
	agentsByChef: Record<string, AgentModel[]>;
	onModelSelect: (id: string) => void;
	modelSelectorOpen: boolean;
	onModelSelectorOpenChange: (open: boolean) => void;
	showModelPicker: boolean;
	isUploading: boolean;
	onLocalReject: (entries: ChatRejectionEntry[]) => void;
}

export function ChatComposer({
	status,
	onStop,
	onSubmit,
	chatError,
	onClearError,
	selectedAgent,
	selectedAgentId,
	agentsByChef,
	onModelSelect,
	modelSelectorOpen,
	onModelSelectorOpenChange,
	showModelPicker,
	isUploading,
	onLocalReject,
}: ChatComposerProps) {
	const caps = selectedAgent?.capabilities;
	const acceptAttribute = useMemo(() => buildAcceptAttribute(caps), [caps]);
	const supportsImage = Boolean(caps?.image_input);
	const restrictedHint = supportsImage
		? "Attach images or documents. Documents (PDF/DOC/XLSX/etc) are extracted as text and sent to the model."
		: `${selectedAgent?.name ?? "This model"} only accepts documents (PDF/DOC/XLSX/etc) — extracted as text. Images are blocked.`;

	const effectiveStatus: ChatStatus = isUploading ? "submitted" : status;

	const handlePromptInputError = useCallback(
		(err: { code: "max_files" | "max_file_size" | "accept"; message: string }) => {
			const reason =
				err.code === "max_files"
					? "max_files"
					: err.code === "max_file_size"
						? "too_large"
						: "unsupported_type";
			onLocalReject([
				{
					filename: "Selected file",
					mediaType: "",
					reason,
				},
			]);
		},
		[onLocalReject]
	);

	return (
		<div className="shrink-0">
			<ChatDragDropOverlay
				accept={acceptAttribute}
				modelName={selectedAgent?.name}
				onReject={onLocalReject}
			/>
			<div className="before:from-background relative mx-auto w-full max-w-4xl px-3 pt-2 pb-4 before:pointer-events-none before:absolute before:-top-6 before:right-0 before:left-0 before:h-6 before:bg-gradient-to-t before:to-transparent sm:px-4 lg:max-w-5xl xl:max-w-6xl">
				{chatError && (
					<Alert variant="destructive" className="mb-3">
						<AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
							<span className="min-w-0 wrap-break-word">{chatError.message}</span>
							<Button
								type="button"
								variant="outline"
								size="sm"
								className="border-destructive/40 shrink-0"
								onClick={onClearError}
							>
								Dismiss
							</Button>
						</AlertDescription>
					</Alert>
				)}
				<PromptInput
					className="border-border/70 focus-within:border-primary/40 bg-background rounded-3xl border shadow-[0_2px_12px_-4px_rgba(0,0,0,0.08)] transition-colors dark:shadow-[0_2px_12px_-4px_rgba(0,0,0,0.4)]"
					globalDrop
					multiple
					accept={acceptAttribute}
					onError={handlePromptInputError}
					onSubmit={onSubmit}
				>
					<PromptInputHeader className="px-2 pt-2">
						<PromptAttachmentsDisplay />
					</PromptInputHeader>
					<PromptInputBody>
						<PromptInputTextarea
							placeholder="Ask anything..."
							className="placeholder:text-muted-foreground/70 max-h-48 min-h-9 resize-none px-3 py-2 text-base leading-snug"
							rows={1}
						/>
					</PromptInputBody>
					<PromptInputFooter className="px-2 pb-2">
						<PromptInputTools className="gap-1">
							<PromptInputActionMenu>
								<Tooltip>
									<TooltipTrigger asChild>
										<PromptInputActionMenuTrigger className="size-9 [&_svg]:size-4" />
									</TooltipTrigger>
									<TooltipContent side="top" className="max-w-xs">
										{restrictedHint}
									</TooltipContent>
								</Tooltip>
								<PromptInputActionMenuContent side="top">
									<PromptInputActionAddAttachments
										label={supportsImage ? "Add photo or file" : "Add file"}
									/>
								</PromptInputActionMenuContent>
							</PromptInputActionMenu>
							{showModelPicker && (
								<ChatModelPicker
									open={modelSelectorOpen}
									onOpenChange={onModelSelectorOpenChange}
									selectedAgent={selectedAgent}
									selectedAgentId={selectedAgentId}
									agentsByChef={agentsByChef}
									onSelect={onModelSelect}
								/>
							)}
						</PromptInputTools>
						<PromptInputSubmit
							className="size-9 rounded-full [&_svg]:size-5"
							status={effectiveStatus}
							onStop={onStop}
						/>
					</PromptInputFooter>
				</PromptInput>
			</div>
		</div>
	);
}
