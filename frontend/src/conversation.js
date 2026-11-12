/** Names of the workshop steps, by step number - 1 (the API only sends the number). */
export const STEPS = ["Gathering information", "Concept design"];

/**
 * The images a reply brings: the references when they were just (re)searched, and the
 * concept image when a new version was generated. Compares the progress before and after.
 */
export function newImages(previous, next) {
  const images = [];
  if (!next) return images;
  if (next.reference_count && next.references_revision !== previous?.references_revision) {
    for (let id = 1; id <= next.reference_count; id++) {
      images.push({ kind: "references", id, revision: next.references_revision });
    }
  }
  if (next.latest_version && next.latest_version !== previous?.latest_version) {
    images.push({ kind: "images", id: next.latest_version });
  }
  return images;
}

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
    this.step = null; // number of the workshop step, known after the first reply
    this.concept = null; // concept design progress: { reference_count, latest_version, ... }
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

  /** URL of an image shown in a message (see `newImages`), for an <img>. */
  imageUrl(image) {
    const url = this.api.conceptImageUrl(this.sessionId, image.kind, image.id);
    return image.revision ? `${url}?r=${image.revision}` : url;
  }

  /** False for references that a newer search replaced: the old ones are gone. */
  isCurrent(image) {
    return image.kind !== "references" || image.revision === this.concept?.references_revision;
  }

  // Not a #private method: this object is wrapped in a Vue proxy, which private names reject.
  async _exchange(history) {
    const sessionId = this.sessionId;

    // The API only knows roles and texts: the images of a message stay in the browser.
    const body = await this.api.chat(
      sessionId,
      history.map(({ role, content }) => ({ role, content })),
    );

    if (this.sessionId !== sessionId) return null;
    const images = newImages(this.concept, body.concept);
    this.information = body.information;
    this.step = body.step ?? null;
    this.concept = body.concept ?? null;
    this.messages = [
      ...history,
      { role: "assistant", content: body.reply, ...(images.length && { images }) },
    ];
    return body.reply;
  }
}
