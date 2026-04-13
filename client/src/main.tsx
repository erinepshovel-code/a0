// 5:0
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

document.documentElement.classList.add("dark");

createRoot(document.getElementById("root")!).render(<App />);
// 5:0
