import { CohereClient } from "cohere-ai";

export interface SlotCallParams {
  messages: { role: string; content: string }[];
  systemPrompt: string;
  model: string;
  maxTokens: number;
  temperature?: number;
  apiKey: string;
}

export interface SlotCallResult {
  content: string;
  promptTokens: number;
  completionTokens: number;
}

/**
 * Translate an OpenAI-style messages array + system prompt into Cohere's
 * chat call and map the response back to a common shape.
 *
 * Cohere v2 chat format:
 *   - system prompt → preamble / or first message with role "system"
 *   - message history → chatHistory (role: USER | CHATBOT)
 *   - last user message → message
 */
export async function callCohere(params: SlotCallParams): Promise<SlotCallResult> {
  const { messages, systemPrompt, model, maxTokens, temperature, apiKey } = params;

  const client = new CohereClient({ token: apiKey });

  const allMsgs = [...messages];
  if (systemPrompt) {
    allMsgs.unshift({ role: "system", content: systemPrompt });
  }

  const chatHistory: { role: "USER" | "CHATBOT" | "SYSTEM"; message: string }[] = [];
  let lastUserMessage = "";

  for (const m of allMsgs) {
    if (m.role === "system") {
      chatHistory.push({ role: "SYSTEM", message: m.content });
    } else if (m.role === "user") {
      chatHistory.push({ role: "USER", message: m.content });
      lastUserMessage = m.content;
    } else if (m.role === "assistant") {
      chatHistory.push({ role: "CHATBOT", message: m.content });
    }
  }

  if (!lastUserMessage && chatHistory.length > 0) {
    const lastUser = [...chatHistory].reverse().find((m) => m.role === "USER");
    lastUserMessage = lastUser?.message || "(no message)";
  }

  const historyWithoutLast = lastUserMessage
    ? chatHistory.slice(0, chatHistory.map((m) => m.message).lastIndexOf(lastUserMessage))
    : chatHistory;

  const response = await client.chat({
    model,
    message: lastUserMessage || "(no message)",
    chatHistory: historyWithoutLast as any,
    ...(maxTokens ? { maxTokens } : {}),
    ...(temperature != null ? { temperature } : {}),
  });

  const content = response.text || "";
  const promptTokens = response.meta?.tokens?.inputTokens || 0;
  const completionTokens = response.meta?.tokens?.outputTokens || 0;

  return { content, promptTokens, completionTokens };
}
