// Hash routes keep everything on the device: the part after # is never sent to the server.
import { useEffect, useState } from "preact/hooks";
import { useApp } from "../state";
import { Ballot } from "./Ballot";
import { Home } from "./Home";
import { ItemDetail } from "./ItemDetail";
import { Basics, Privacy, YourData } from "./Pages";
import { WriteOut } from "./WriteOut";

function useRoute(): string {
  const [route, setRoute] = useState(location.hash.slice(1) || "/");
  useEffect(() => {
    const on = () => { setRoute(location.hash.slice(1) || "/"); window.scrollTo(0, 0); };
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  return route;
}

export function App() {
  const route = useRoute();
  const { user } = useApp();
  // Screens that need a ballot go Home when there is none (first visit, after Clear everything,
  // or after reloading a private session, which keeps nothing).
  const needsBallot = route.startsWith("/item/") || route === "/ballot" || route === "/write-out";
  if (needsBallot && !user.scope.zip) return <Home />;
  if (route.startsWith("/item/")) return <ItemDetail id={decodeURIComponent(route.slice(6))} />;
  switch (route) {
    case "/ballot": return <Ballot />;
    case "/write-out": return <WriteOut />;
    case "/data": return <YourData />;
    case "/privacy": return <Privacy />;
    case "/basics": return <Basics />;
    default: return <Home />;
  }
}
