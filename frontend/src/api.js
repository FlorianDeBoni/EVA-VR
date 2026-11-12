/** Error returned by the API (status 0 = the API could not be reached). */
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

const detailOf = (body) =>
  typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);

/** Thin client for the backend routes. `fetchImpl` can be replaced in tests. */
export function createApi(baseUrl, fetchImpl = (...args) => fetch(...args)) {
  const url = (path) => `${baseUrl.replace(/\/$/, "")}${path}`;

  async function call(path, init) {
    let response;
    try {
      response = await fetchImpl(url(path), init);
    } catch {
      throw new ApiError(0, `Cannot reach the API at ${baseUrl}`);
    }
    const body = await response.json().catch(() => null);
    if (!response.ok) throw new ApiError(response.status, detailOf(body));
    return body;
  }

  return {
    /** GET /health/ready -> true when the API is up, never throws. */
    async health() {
      try {
        return (await fetchImpl(url("/health/ready"))).ok;
      } catch {
        return false;
      }
    },

    /** URL of a concept image, for <img>: kind is "references", "images" or "validated". */
    conceptImageUrl(sessionId, kind, id) {
      return url(`/concept/${sessionId}/${kind}${id === undefined ? "" : `/${id}`}`);
    },

    /** POST /chat -> { session_id, step, reply, information, concept } */
    chat(sessionId, messages) {
      return call("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, messages }),
      });
    },

    /** POST /speech/transcribe -> the transcript text */
    async transcribe(blob, filename) {
      const form = new FormData();
      form.append("file", blob, filename);
      return (await call("/speech/transcribe", { method: "POST", body: form })).text;
    },
  };
}
