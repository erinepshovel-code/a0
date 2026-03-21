import Anthropic from "@anthropic-ai/sdk";

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
 * Translate an OpenAI-style messages array + system prompt into Anthropic's
 * messages.create call and map the response back to a common shape.
 */
export async function callAnthropic(params: SlotCallParams): Promise<SlotCallResult> {
  const { messages, systemPrompt, model, maxTokens, temperature, apiKey } = params;

  const client = new Anthropic({ apiKey });

  const anthropicMessages: Anthropic.MessageParam[] = messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      role: m.role as "user" | "assistant",
      content: m.content,
    }));

  if (anthropicMessages.length === 0) {
    anthropicMessages.push({ role: "user", content: "(no user message)" });
  }

  const createParams: Anthropic.MessageCreateParamsNonStreaming = {
    model,
    max_tokens: maxTokens || 4096,
    messages: anthropicMessages,
    ...(systemPrompt ? { system: systemPrompt } : {}),
    ...(temperature != null ? { temperature } : {}),
  };

  const response = await client.messages.create(createParams);

  const content =
    response.content
      .filter((block) => block.type === "text")
      .map((block) => (block as Anthropic.TextBlock).text)
      .join("") || "";

  const promptTokens = response.usage?.input_tokens || 0;
  const completionTokens = response.usage?.output_tokens || 0;

  return { content, promptTokens, completionTokens };
}
