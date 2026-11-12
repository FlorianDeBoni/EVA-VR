/**
 * The conversation, owned by the frontend: the API keeps no history, so the whole
 * message list is sent on every turn. A new conversation gets a new session id.
 */
export class Conversation {
  constructor(api, newId = () => crypto.randomUUID()) {
    this.api = api;
    this.newId = newId;
    this.reset();
  }

  /** Start a new conversation with a fresh session id and an empty history. */
  reset() {
    this.sessionId = this.newId();
    this.messages = []; // [{ role: "user" | "assistant", content }]
    this.information = null; // what the agent has gathered so far
  }

  /**
   * Ask the assistant to open the conversation: an empty query makes it send its
   * welcome message. Returns the message, or null if the conversation was reset
   * while waiting.
   */
  start() {
    return this._exchange([]);
  }

  /**
   * Send a user message. Returns the assistant's reply, or null if the conversation
   * was reset while waiting. On error nothing is added to the history, so the
   * message can be sent again.
   */
  send(text) {
    return this._exchange([...this.messages, { role: "user", content: text }]);
  }

  // Not a #private method: this object is wrapped in a Vue proxy, which private names reject.
  async _exchange(history) {
    const sessionId = this.sessionId;

    const body = await this.api.chat(sessionId, history);

    if (this.sessionId !== sessionId) return null;
    this.information = body.information;
    this.messages = [...history, { role: "assistant", content: body.reply }];
    return body.reply;
  }
}
