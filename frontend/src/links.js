/** URLs of the pages of the app that are not the chat. */

/** The page that shows the final picture of a session full screen ("Go to VR"). */
export const vrPageUrl = (sessionId) => `/vr.html?session=${encodeURIComponent(sessionId)}`;

/** The session id carried by the URL of the VR page, or null. */
export const sessionFromSearch = (search) => new URLSearchParams(search).get("session");
