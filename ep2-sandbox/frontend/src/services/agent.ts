import { auth } from "./firebase";

const AGENT_BASE_URL =
  "https://financial-service-agent-609099553774.us-central1.run.app";

export interface ChatRequest {
  message: string;
  user_id?: string;
  session_id?: string;
  skill?: "chat" | "backend_services";
}

export interface ChatResponse {
  response: string;
  session_id: string;
  skill_used: string;
}

export const AgentType = {
  DAILY_SPENDING: "daily-spending",
  BIG_PURCHASES: "big-purchases",
  TRAVEL: "travel",
  GENERAL: "general",
} as const;

export type AgentType = (typeof AgentType)[keyof typeof AgentType];

class AgentService {
  private sessionId: string | null = null;

  private async getAuthToken(): Promise<string | null> {
    const user = auth.currentUser;
    if (!user) return null;
    return user.getIdToken();
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  async sendMessage(
    message: string,
    agentType: AgentType = AgentType.GENERAL,
    sessionId?: string
  ): Promise<ChatResponse> {
    const token = await this.getAuthToken();

    if (!token) {
      throw new Error("User not authenticated");
    }

    // Use existing session ID or create a new one
    const currentSessionId =
      sessionId || this.sessionId || this.generateSessionId();

    // Store session ID for future use
    if (!this.sessionId) {
      this.sessionId = currentSessionId;
    }

    // Format message based on agent type
    let formattedMessage = message;
    if (agentType === AgentType.DAILY_SPENDING) {
      formattedMessage = `I need help with daily spending. ${message}`;
    } else if (agentType === AgentType.BIG_PURCHASES) {
      formattedMessage = `I need help with a big purchase. ${message}`;
    } else if (agentType === AgentType.TRAVEL) {
      formattedMessage = `I need help with travel planning. ${message}`;
    }

    const payload: ChatRequest = {
      message: formattedMessage,
      user_id: auth.currentUser?.uid || "user-001",
      session_id: currentSessionId,
      skill: "chat",
    };

    try {
      const response = await fetch(`${AGENT_BASE_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Agent API error:", errorText);
        throw new Error(`Agent request failed: ${response.status}`);
      }

      const data: ChatResponse = await response.json();

      // Update session ID if provided in response
      if (data.session_id) {
        this.sessionId = data.session_id;
      }

      return data;
    } catch (error) {
      console.error("Error communicating with agent:", error);
      throw error;
    }
  }

  // Specialized methods for each agent type
  async sendDailySpendingQuery(
    message: string,
    sessionId?: string
  ): Promise<ChatResponse> {
    return this.sendMessage(message, AgentType.DAILY_SPENDING, sessionId);
  }

  async sendBigPurchaseQuery(
    message: string,
    sessionId?: string
  ): Promise<ChatResponse> {
    return this.sendMessage(message, AgentType.BIG_PURCHASES, sessionId);
  }

  async sendTravelQuery(
    message: string,
    sessionId?: string
  ): Promise<ChatResponse> {
    return this.sendMessage(message, AgentType.TRAVEL, sessionId);
  }

  // Extract text from agent response
  extractResponseText(response: ChatResponse): string {
    return response.response || "No response from agent";
  }

  // Get session ID from response or current session
  getSessionId(response: ChatResponse): string | undefined {
    return response.session_id || this.sessionId || undefined;
  }

  // Clear session (for starting new conversations)
  clearSession(): void {
    this.sessionId = null;
  }
}

export const agentService = new AgentService();
