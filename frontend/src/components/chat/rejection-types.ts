export type ChatRejectionReason =
  | "image_not_supported"
  | "audio_not_supported"
  | "video_not_supported"
  | "too_large"
  | "unsupported_type"
  | "max_files"
  | "thread_files_full"
  | "thread_images_full"
  | "thread_documents_full"
  | "user_files_full"
  | "user_storage_full"
  | "network";

export interface ChatRejectionEntry {
  filename: string;
  mediaType: string;
  reason: ChatRejectionReason;
}

export interface ChatRejection {
  modelName: string | undefined;
  entries: ChatRejectionEntry[];
}
