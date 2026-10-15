import { render } from "preact";
import { AppProvider } from "./state";
import { App } from "./ui/App";
import "./styles.css";

render(<AppProvider><App /></AppProvider>, document.getElementById("app")!);
