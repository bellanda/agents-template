import { usePromptInputController } from "@/components/ai-elements/prompt-input";
import { useCallback, useEffect, useRef } from "react";

/**
 * Suggestion chip with `action: "attach"`: writes the prompt, opens the file picker and submits
 * the message as soon as a file is attached, so the user does not have to press send.
 *
 * The file picker emits no event when cancelled, so the trigger stays armed. That is harmless:
 * the right text is already in the composer, and the next attachment is what the user meant.
 */
export function useAttachAndSend(): (prompt: string) => void {
  const { textInput, attachments, requestSubmit } = usePromptInputController();
  const armedRef = useRef(false);
  const fileCountRef = useRef(attachments.files.length);

  useEffect(() => {
    const previousCount = fileCountRef.current;
    fileCountRef.current = attachments.files.length;
    if (!armedRef.current || attachments.files.length <= previousCount) return;
    armedRef.current = false;
    requestSubmit();
  }, [attachments.files.length, requestSubmit]);

  return useCallback(
    (prompt: string) => {
      textInput.setInput(prompt);
      armedRef.current = true;
      attachments.openFileDialog();
    },
    [textInput, attachments]
  );
}
