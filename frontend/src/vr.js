import { createApi } from "./api.js";
import { sessionFromSearch } from "./links.js";

// "Go to VR": the final picture of the session, full screen. The session comes from the URL.
const image = document.getElementById("final");
const message = document.getElementById("message");

function fail(text) {
  image.hidden = true;
  message.hidden = false;
  message.textContent = text;
}

const sessionId = sessionFromSearch(window.location.search);
if (!sessionId) {
  fail("No session given: open this page with the Go to VR button.");
} else {
  const api = createApi(import.meta.env.VITE_API_URL);
  image.onload = () => {
    message.hidden = true;
    image.hidden = false;
  };
  image.onerror = () => fail("The final picture is not available yet: validate the design first.");
  image.src = api.conceptImageUrl(sessionId, "final");
}
