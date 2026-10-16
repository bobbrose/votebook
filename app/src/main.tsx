import { render } from "preact";
import { AppProvider } from "./state";
import { App } from "./ui/App";
import "./styles.css";

render(<AppProvider><App /></AppProvider>, document.getElementById("app")!);

// Offline support (NFR-03): production only, so development always loads fresh files.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  addEventListener("load", () => { navigator.serviceWorker.register("/sw.js").catch(() => undefined); });
}
